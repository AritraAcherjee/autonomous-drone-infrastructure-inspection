"""Controlled Ultralytics training orchestration with mandatory provenance and guards."""
from __future__ import annotations

from copy import copy
import json
import logging
import math
from pathlib import Path
import shutil
import time
from unittest.mock import patch
import urllib.request

from detection.data.raw_guard import compare, sha256, snapshot
from detection.training.config import APPROVED_HASHES, load_config, load_development_data, run_directory, select_records
from detection.training.provenance import capture, configure_runtime, development_access, write_json

LOGGER = logging.getLogger(__name__)
CHECKPOINT_URL = 'https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26s.pt'


def implementation_identity(root: Path) -> dict:
    """Bind required test evidence to all current implementation and test files."""
    paths = [p for folder in ('src/detection/training', 'configs/detection', 'tests/detection')
             for p in (root/folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.yaml')]
    paths.extend(root/'scripts'/name for name in ('train_detector.py', 'verify_detector_exif.py', 'check_detector_training.py'))
    return {p.relative_to(root).as_posix(): sha256(p) for p in sorted(paths)}


def require_tests(root: Path) -> dict:
    """Refuse acquisition/training without passing tests for the current implementation."""
    path = root/'outputs/validation/defect_detection/training_pipeline/before/ready.json'
    if not path.is_file():
        raise ValueError('Run scripts/check_detector_training.py --stage before before downloading/training')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('status') != 'PASS' or record.get('implementation') != implementation_identity(root):
        raise ValueError('Required test evidence failed or is stale')
    for rel, digest in record['evidence_sha256'].items():
        if sha256(root/rel) != digest:
            raise ValueError(f'Test evidence changed: {rel}')
    return record


def checkpoint(config: dict, root: Path, acquire: bool) -> tuple[Path, dict]:
    """Acquire only the selected official checkpoint, or require a verified local receipt."""
    path = (root/config['model']['cache_dir']/config['model']['checkpoint']).resolve()
    receipt = path.with_suffix('.json')
    if not path.exists():
        if not acquire:
            raise FileNotFoundError(f'Pretrained checkpoint missing: {path}; use --download-pretrained only at the prepared smoke run')
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix('.partial')
        if partial.exists():
            raise FileExistsError(f'Previous incomplete download retained for inspection: {partial}')
        LOGGER.info('Acquiring official yolo26s.pt: %s', CHECKPOINT_URL)
        request = urllib.request.Request(CHECKPOINT_URL, headers={'User-Agent': 'AegisInspect-training/1'})
        with urllib.request.urlopen(request, timeout=120) as response, partial.open('xb') as stream:
            shutil.copyfileobj(response, stream)
        if partial.stat().st_size < 1_000_000:
            raise ValueError('Official checkpoint response is unexpectedly small')
        partial.rename(path)
        info = dict(filename=path.name, model_id='yolo26s', source=CHECKPOINT_URL,
                    acquisition='HTTPS download from official ultralytics/assets v8.4.0 release',
                    local_path=str(path), size_bytes=path.stat().st_size, sha256=sha256(path))
        write_json(receipt, info, root)
    if not receipt.is_file():
        raise ValueError(f'Checkpoint has no acquisition receipt: {path}')
    info = json.loads(receipt.read_text(encoding='utf-8'))
    if info.get('source') != CHECKPOINT_URL or info.get('sha256') != sha256(path):
        raise ValueError('Checkpoint receipt/hash mismatch')
    return path, info


def training_arguments(config: dict, root: Path, weights: Path, data_path: Path) -> dict:
    """Translate recorded baseline values into explicit Ultralytics arguments."""
    augmentation = {k: v for k, v in config['augmentation'].items() if k != 'albumentations'}
    return dict(config['training'], **augmentation, **config['validation'], task='detect', mode='train',
                model=str(weights), pretrained=True, data=str(data_path),
                project=str((root/config['output']['project']).resolve()), name=config['output']['name'],
                exist_ok=True, verbose=True)


def trainer_class():
    """Build the integration lazily so configuration errors never load/download a model."""
    import torch
    from ultralytics.models.yolo.detect import DetectionTrainer
    from ultralytics.utils.torch_utils import unwrap_model
    from detection.training.dataset import ReadOnlyDetectionDataset

    class GuardedDetectionTrainer(DetectionTrainer):
        def __init__(self, *, records, development_data, expected_output, evidence, **kwargs):
            self.records = records
            self.development_data = development_data
            self.expected_output = expected_output.resolve()
            self.evidence = evidence
            super().__init__(**kwargs)
            if self.save_dir.resolve() != self.expected_output or self.device.type != 'cuda':
                raise ValueError('Trainer output/device differs from requested controlled CUDA run')

        def get_dataset(self):
            return self.development_data.copy()

        def build_dataset(self, img_path, mode='train', batch=None):
            if mode not in ('train', 'val') or str(img_path) != self.data[mode]:
                raise ValueError('Only exact approved train/validation lists are permitted')
            split = 'valid' if mode == 'val' else 'train'
            return ReadOnlyDetectionDataset(records=self.records[split], img_path=img_path,
                imgsz=self.args.imgsz, batch_size=batch, augment=mode == 'train', hyp=copy(self.args),
                rect=mode == 'val', cache=False, single_cls=False,
                stride=max(int(unwrap_model(self.model).stride.max()), 32), pad=0.0 if mode == 'train' else 0.5,
                prefix=f'{mode}: ', task='detect', classes=None, data=self.data, fraction=1.0)

        def _build_train_pipeline(self):
            if self.args.batch != self.evidence['requested_batch']:
                raise RuntimeError('OOM/batch auto-reduction detected; fixed-batch run stopped')
            return super()._build_train_pipeline()

        def optimizer_step(self):
            gradients = [p for p in self.model.parameters() if p.grad is not None]
            if not gradients or not all(torch.isfinite(p.grad).all().item() for p in gradients):
                raise FloatingPointError('Nonfinite/missing gradients; optimizer step refused')
            active = next((p for p in gradients if torch.count_nonzero(p.grad).item()), None)
            if active is None:
                raise FloatingPointError('All gradients zero')
            before = active.detach().clone()
            super().optimizer_step()
            self.evidence['optimizer_steps'] += 1
            self.evidence['parameter_updates'] += int(not torch.equal(before, active.detach()))

        def _handle_nan_recovery(self, epoch):
            if not all(math.isfinite(float(v)) for v in self.metrics.values()):
                raise FloatingPointError('Nonfinite validation metric; automatic recovery prohibited')
            return False

    return GuardedDetectionTrainer


def run(root: Path, config_path: Path, *, acquire: bool = False, check_only: bool = False) -> dict:
    """Run one requested experiment and prove raw immutability even after failure."""
    config = load_config(config_path, root)
    configure_runtime(root)
    from detection.training.exif import require_pass
    from ultralytics.utils import SETTINGS, LOGGER as ultra_logger, callbacks
    from ultralytics.utils.downloads import GITHUB_ASSETS_NAMES
    import torch
    import ultralytics
    if ultralytics.__version__ != '8.4.145' or config['model']['checkpoint'] not in GITHUB_ASSETS_NAMES:
        raise ValueError('Installed model/API version differs from reviewed 8.4.145')
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise ValueError('CUDA device 0 with native BF16 support is required')
    with development_access(root):
        _, all_records = load_development_data(root, config['data']['yaml'])
        geometry = require_pass(root)
        tests = require_tests(root)
        if check_only:
            return dict(status='READY', run=config['experiment']['id'], geometry=geometry['status'], tests=tests['status'])
        records = select_records(all_records, config)
        out = run_directory(config, root)
        if out.exists():
            raise FileExistsError(f'Run directory already exists; refuse overwrite or implicit suffix: {out}')
        if not acquire:
            checkpoint(config, root, acquire=False)  # fail before creating run outputs
        out.mkdir(parents=True, exist_ok=False)
        handler = logging.FileHandler(out/'trainer.log', encoding='utf-8')
        ultra_logger.addHandler(handler)
        LOGGER.addHandler(handler)
        evidence = dict(status='FAIL', engineering_smoke='smoke' in config, test_accessed=False,
                        requested_batch=config['training']['batch'], optimizer_steps=0, parameter_updates=0,
                        batches=0, epochs=0, finite_losses=True, validation_calls=0, loss_history=[])
        write_json(out/'requested_config.json', config, root)
        provenance = capture(root, config)
        write_json(out/'provenance.json', provenance, root)
        write_json(out/'dataset_identity.json', dict(identity=config['data']['identity'], hashes=APPROVED_HASHES,
            selected={split: [r['image_relative_path'] for r in rows] for split, rows in records.items()},
            counts={k: len(v) for k, v in records.items()}, policy=config['data']), root)
        for split, rows in records.items():
            (out/f'{split}.txt').write_text(''.join(str(r['image'])+'\n' for r in rows), encoding='utf-8')
        from detection.data.readonly_verifier import CLASSES
        data = dict(path=str(root), train=str(out/'train.txt'), val=str(out/'valid.txt'),
                    names={i: name for i, name in enumerate(CLASSES)}, nc=6, channels=3)
        data_path = out/'development_data.yaml'
        write_json(data_path, data, root)  # JSON is valid YAML; no test key and no download directive.
        hashed = {r[k] for rows in records.values() for r in rows for k in ('image', 'label')}
        LOGGER.info('Snapshotting all raw metadata and hashing %d selected source files', len(hashed))
        before = snapshot(root/'data/raw', hashed)
        write_json(out/'raw_before.json', before, root)
        started = time.perf_counter()
        trainer = None
        try:
            for rows in records.values():
                for row in rows:
                    if before[row['image'].relative_to(root/'data/raw').as_posix()]['sha256'] != row['image_sha256']:
                        raise ValueError(f'Approved source content changed: {row["image"]}')
            weights, receipt = checkpoint(config, root, acquire)
            write_json(out/'checkpoint_acquisition.json', receipt, root)
            # Native BF16 avoids the stock FP16 AMP-check's unrelated yolo26n download.
            font = Path('C:/Windows/Fonts/arial.ttf')
            if font.is_file():
                shutil.copyfile(font, root/'outputs/cache/detection_training/settings/Ultralytics/Arial.ttf')
            SETTINGS.update({k: False for k in ('sync', 'wandb', 'comet', 'clearml', 'mlflow', 'neptune', 'raytune', 'tensorboard', 'dvc') if k in SETTINGS})
            args = training_arguments(config, root, weights, data_path)
            torch.cuda.reset_peak_memory_stats(0)
            callback_map = callbacks.get_default_callbacks()
            train_started = [None]

            def ready(t):
                if t.data['nc'] != 6 or t.batch_size != config['training']['batch']:
                    raise ValueError('Runtime classes or fixed batch differs')
                resolved = dict(ultralytics=vars(t.args), optimizer=type(t.optimizer).__name__,
                    optimizer_groups=[{k: v for k, v in g.items() if k != 'params'} for g in t.optimizer.param_groups],
                    accumulate=t.accumulate, parameter_count=sum(p.numel() for p in t.model.parameters()),
                    train_images=len(t.train_loader.dataset), valid_images=len(t.test_loader.dataset),
                    validation_batch=t.test_loader.batch_size, albumentations='disabled',
                    image_cache=False, label_disk_cache=False, initialization=receipt)
                write_json(out/'resolved_config.json', resolved, root)
                evidence.update(device=str(t.device), gpu=torch.cuda.get_device_name(t.device), classes=t.data['names'],
                                resolved_batch=t.batch_size, resolved_optimizer=type(t.optimizer).__name__)

            def train_start(t):
                train_started[0] = time.perf_counter()

            def batch_end(t):
                loss = {k: float(v.detach().cpu()) for k, v in t.loss_items.items()}
                if not all(math.isfinite(v) for v in loss.values()) or not torch.isfinite(t.loss).item():
                    evidence['finite_losses'] = False
                    raise FloatingPointError('Nonfinite training loss; stopping')
                evidence['batches'] += 1
                if 'smoke' in config:
                    evidence['loss_history'].append(loss)

            def epoch_end(t):
                evidence['epochs'] += 1
                evidence['mean_train_losses'] = {k: float(v.detach().cpu()) for k, v in t.tloss.items()}

            def val_end(v):
                evidence['validation_calls'] += 1

            for event, fn in (('on_pretrain_routine_end', ready), ('on_train_start', train_start),
                              ('on_train_batch_end', batch_end), ('on_train_epoch_end', epoch_end), ('on_val_end', val_end)):
                callback_map[event].append(fn)
            # Keep all optional integrations and implicit download paths out of this run.
            with patch.object(callbacks, 'add_integration_callbacks', lambda _: None), patch(
                    'ultralytics.utils.downloads.safe_download', side_effect=RuntimeError('Implicit download prohibited')):
                trainer = trainer_class()(records=records, development_data=data, expected_output=out,
                    evidence=evidence, overrides=args, _callbacks=callback_map)
                fit_started = time.perf_counter()
                trainer.train()
                torch.cuda.synchronize(0)
                evidence['fit_seconds'] = time.perf_counter()-fit_started
            evidence.update(train_validation_seconds=time.perf_counter()-train_started[0],
                gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
                gpu_peak_reserved_bytes=torch.cuda.max_memory_reserved(0),
                metrics=trainer.metrics,
                checkpoints={name: dict(path=str(out/'weights'/name), size_bytes=(out/'weights'/name).stat().st_size,
                    sha256=sha256(out/'weights'/name)) for name in ('best.pt', 'last.pt')})
            if not (evidence['optimizer_steps'] and evidence['parameter_updates'] and evidence['validation_calls'] and evidence['epochs']):
                raise RuntimeError('Required training/validation/checkpoint proof incomplete')
            if 'smoke' in config and evidence['epochs'] != config['training']['epochs']:
                raise RuntimeError('Smoke epochs did not complete')
            evidence['status'] = 'PASS'
            return evidence
        except BaseException as exc:
            evidence.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
            raise
        finally:
            evidence['total_seconds_excluding_snapshot'] = time.perf_counter()-started
            LOGGER.info('Comparing raw inventory immediately after training/acquisition')
            after = snapshot(root/'data/raw', hashed)
            raw_result = compare(before, after)
            raw_result.update(files_observed=len(after), content_hashed_development_files=len(hashed),
                cache_files=[p for p in after if p.lower().endswith('.cache')],
                npy_files=[p for p in after if p.lower().endswith('.npy')])
            if raw_result['cache_files'] or raw_result['npy_files']:
                raw_result['status'] = 'FAIL'
            evidence['raw_immutability'] = raw_result
            if raw_result['status'] != 'PASS':
                evidence['status'] = 'FAIL'
            write_json(out/'raw_after.json', after, root)
            write_json(out/'raw_immutability.json', raw_result, root)
            write_json(out/'run_evidence.json', evidence, root)
            ultra_logger.removeHandler(handler)
            LOGGER.removeHandler(handler)
            handler.close()
            if raw_result['status'] != 'PASS':
                raise RuntimeError('RAW IMMUTABILITY = FAIL; evidence retained, do not clean raw')
