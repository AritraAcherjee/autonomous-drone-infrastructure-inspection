"""No-training reader gate. No YOLO/model/dataset constructors are called."""
from __future__ import annotations

from collections import Counter
import csv
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from detection.data.raw_guard import compare, mutable_path, readonly_raw, sha256, snapshot
from detection.data.readonly_verifier import CLASSES, decode, load_approved, read_csv, verify_label
from data.validators.gyu_m1_documentation import check_approved

SECTIONS = ('environment', 'dataset_counts', 'class_mapping', 'image_reader', 'mpo_reader', 'label_reader', 'raw_immutability')


def aggregate(sections: dict) -> dict:
    return dict(status='PASS' if not sections.get('execution_error') and all(sections.get(k, {}).get('status') == 'PASS' for k in SECTIONS) else 'FAIL', **sections)


def write_json(path: Path, value: dict, raw: Path):
    path = mutable_path(path, raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path: Path, rows: list[dict], fields: list[str], raw: Path):
    path = mutable_path(path, raw)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n', extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row[k]) if isinstance(row.get(k), (dict, list)) else row.get(k, '') for k in fields})


def command(args: list[str]) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f'Unavailable: {exc}'


def environment() -> dict:
    report = dict(operating_system=platform.platform(), python=platform.python_version(),
                  python_executable=sys.executable, environment_path=sys.prefix,
                  active_venv=os.environ.get('VIRTUAL_ENV'), active_conda=os.environ.get('CONDA_PREFIX'),
                  isolated=sys.prefix != sys.base_prefix)
    for name in ('pip', 'torch', 'torchvision', 'ultralytics', 'numpy', 'opencv-python', 'Pillow'):
        try:
            report[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report[name] = None
    report['nvidia_smi'] = command(['nvidia-smi'])
    report['nvidia_driver_gpu'] = command(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,compute_cap', '--format=csv'])
    report['nvcc'] = command(['nvcc', '--version']) if shutil.which('nvcc') else 'Not found on PATH'
    report.update(torch_cuda_runtime=None, cuda_available=False, gpu_count=0, gpus=[], cudnn=None)
    try:
        import torch
        import torchvision
        import cv2
        import PIL
        import numpy
        report.update(torch_cuda_runtime=torch.version.cuda, cuda_available=torch.cuda.is_available(),
                      gpu_count=torch.cuda.device_count(), cudnn=torch.backends.cudnn.version(),
                      opencv=cv2.__version__, pillow=PIL.__version__, numpy=numpy.__version__)
        for index in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(index)
            report['gpus'].append(dict(name=props.name, compute_capability=list(torch.cuda.get_device_capability(index)),
                                       total_memory_bytes=props.total_memory))
        # A small CUDA operation validates the binary/driver pairing; no model.
        if report['cuda_available']:
            report['cuda_tensor_check'] = (torch.ones(1, device='cuda') + 1).item() == 2
    except Exception as exc:
        report['import_error'] = f'{type(exc).__name__}: {exc}'
    report['status'] = 'PASS' if (report['ultralytics'] == '8.4.145' and report['isolated']
                                 and report['cuda_available'] and report.get('cuda_tensor_check')
                                 and not report.get('import_error')) else 'FAIL'
    return report


def runtime_reader() -> tuple:
    from ultralytics.data import base
    from ultralytics.utils import patches
    if base.imread is not patches.imread:
        raise ValueError('Installed BaseDataset reader differs from reviewed Ultralytics patches.imread')
    source = inspect.getsource(base.BaseDataset.load_image)
    if 'imread' not in source:
        raise ValueError('Installed BaseDataset.load_image no longer calls reviewed reader')
    return base.imread, f'ultralytics {importlib.metadata.version("ultralytics")}: ultralytics.data.base.imread -> ultralytics.utils.patches.imread / OpenCV'


def run(root: Path) -> dict:
    with readonly_raw(root / 'data/raw'):
        return _run(root)


def _run(root: Path) -> dict:
    root = root.resolve()
    raw = root / 'data/raw'
    out = mutable_path(root / 'outputs/validation/defect_detection/pretraining_gate', raw)
    cache = mutable_path(root / 'outputs/cache/ultralytics/gyu_det_v3_baseline_v1', raw)
    out.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    # Ultralytics checks whether this parent already exists before creating its
    # own subdirectory; without it, get_user_config_dir can fall back to CWD.
    mutable_path(cache / 'settings/Ultralytics', raw).mkdir(parents=True, exist_ok=True)
    os.environ['YOLO_CONFIG_DIR'] = str(mutable_path(cache / 'settings', raw))
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    os.environ['YOLO_OFFLINE'] = 'true'
    os.environ['MPLCONFIGDIR'] = str(mutable_path(cache / 'matplotlib', raw))
    sections = {k: {'status': 'FAIL', 'reason': 'Not completed'} for k in SECTIONS}
    image_rows, mpo_rows, label_rows = [], [], []
    sections['environment'] = environment()
    write_json(out / 'dependency_versions.json', sections['environment'], raw)
    before = None
    baseline = set()
    try:
        check_approved(root)  # Read-only retained M1 hash/association checks.
        config, records = load_approved(root)
        counts = dict(Counter(r['split'] for r in records))
        sections['dataset_counts'] = dict(status='PASS', **counts, total=len(records))
        sections['class_mapping'] = dict(status='PASS', names=config['names'], nc=config['nc'])
        evidence_path = root / 'outputs/validation/gyu_det_v3/full_validation/image_validation.csv'
        evidence = read_csv(evidence_path)
        population = {r['image_relative_path']: r for r in evidence
                      if any(i['issue_code'] == 'auxiliary_frame_decode_failure' for i in json.loads(r['issues']))}
        if len(population) != 565:
            raise ValueError(f'M1 auxiliary MPO-warning population differs: {len(population)}')
        baseline = {r[k] for r in records for k in ('image', 'label')}
        print('Snapshotting all raw metadata and hashing baseline images/labels...', flush=True)
        before = snapshot(raw, baseline)
        write_json(out / 'raw_snapshot_before.json', before, raw)
        mismatches = [r['image_relative_path'] for r in records
                      if before[r['image'].relative_to(raw).as_posix()]['sha256'] != r['image_sha256']]
        if mismatches:
            sections['dataset_counts'].update(status='FAIL', source_hash_mismatches=mismatches)
        reader, backend = runtime_reader()
        for index, record in enumerate(records, 1):
            common = dict(split=record['split'], image_identifier=record['image'].name,
                          image_path=record['image_relative_path'])
            image_rows.append(dict(common, **decode(record['image'], reader, backend)))
            if record['image_relative_path'] in population:
                # Deliberately decode again with the same reader, retaining a
                # separate audit of the actual included warning population.
                mpo_rows.append(dict(common, source_evidence='outputs/validation/gyu_det_v3/full_validation/image_validation.csv',
                                     evidence_identifier=record['image_relative_path'], **decode(record['image'], reader, backend)))
            label_rows.append(verify_label(record))
            if index % 500 == 0 or index == len(records):
                print(f'Read {index}/{len(records)} approved image-label pairs', flush=True)
        failures = sum(not r['decode_success'] for r in image_rows)
        sections['image_reader'] = dict(status='PASS' if len(image_rows) == 10398 and failures == 0 else 'FAIL',
            attempted=len(image_rows), successful=len(image_rows)-failures, failures=failures, backend=backend,
            unique_resolutions=len({(r['width'], r['height']) for r in image_rows if r['decode_success']}))
        mpo_failures = sum(not r['decode_success'] for r in mpo_rows)
        intersection = sum(r['image_relative_path'] in population for r in records)
        sections['mpo_reader'] = dict(status='PASS' if len(mpo_rows) == intersection and mpo_failures == 0 else 'FAIL',
            source_population=len(population), baseline_intersection=intersection, tested=len(mpo_rows),
            successes=len(mpo_rows)-mpo_failures, failures=mpo_failures, evidence_sha256=sha256(evidence_path))
        label_failures = sum(not r['success'] for r in label_rows)
        annotations = sum(r['annotations'] for r in label_rows)
        classes = sorted({c for r in label_rows for c in r['class_ids']})
        sections['label_reader'] = dict(status='PASS' if len(label_rows) == 10398 and annotations == 48392
            and label_failures == 0 and classes == list(range(6)) else 'FAIL', associations=len(label_rows),
            failures=label_failures, annotations=annotations, class_ids=classes,
            warning_count=sum(len(r['warnings']) for r in label_rows))
    except Exception as exc:
        sections['execution_error'] = f'{type(exc).__name__}: {exc}'
        print(sections['execution_error'], flush=True)
    finally:
        if before is not None:
            print('Taking post-read raw snapshot and comparing content hashes...', flush=True)
            after = snapshot(raw, baseline)
            write_json(out / 'raw_snapshot_after.json', after, raw)
            sections['raw_immutability'] = compare(before, after)
            sections['raw_immutability'].update(files_observed=len(before), hashed_baseline_files=sum('sha256' in r for r in before.values()))
        write_json(out / 'raw_immutability_check.json', sections['raw_immutability'], raw)
        image_fields = ['split', 'image_identifier', 'image_path', 'decode_success', 'width', 'height', 'channels', 'reader_backend', 'error']
        write_csv(out / 'reader_decode_results.csv', image_rows, image_fields, raw)
        write_csv(out / 'mpo_reader_results.csv', mpo_rows, ['source_evidence', 'evidence_identifier'] + image_fields, raw)
        write_csv(out / 'label_loader_results.csv', label_rows,
                  ['split', 'image_path', 'label_path', 'success', 'annotations', 'class_ids', 'warnings', 'errors', 'label_sha256'], raw)
    report = aggregate(sections)
    report['cache_strategy'] = dict(image_cache=False, label_cache='None: read-only metadata consumer; stock YOLODataset not constructed',
                                    controlled_cache_path=str(cache), raw_adjacent_npy='Never created or loaded by this gate')
    report['training_executed'] = False
    report['weights_downloaded'] = False
    report['git_sha'] = command(['git', '-C', str(root), 'rev-parse', 'HEAD'])
    return finalize_report(root, report)


def finalize_report(root: Path, runtime_report: dict) -> dict:
    """Combine measured reader evidence with required regression-test evidence.

    Can be called after tests finish without repeating image reads or changing
    raw snapshots. A reader PASS cannot override a failed or absent test gate.
    """
    raw = root / 'data/raw'
    out = mutable_path(root / 'outputs/validation/defect_detection/pretraining_gate', raw)
    report = dict(runtime_report)
    test_evidence = out / 'test_results.json'
    try:
        report['tests'] = json.loads(test_evidence.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        report['tests'] = {'status': 'FAIL', 'reason': f'Required test evidence unavailable: {exc}'}
    report['status'] = 'PASS' if (all(report.get(k, {}).get('status') == 'PASS' for k in SECTIONS)
                                and report['tests'].get('status') == 'PASS'
                                and not report.get('execution_error')) else 'FAIL'
    write_json(out / 'pretraining_gate.json', report, raw)
    summary = '# Pre-training gate\n\nPRETRAINING GATE = ' + report['status'] + '\n\n'
    summary += '\n'.join(f'- {k}: {report[k]["status"]}' for k in SECTIONS)
    summary += '\n- tests: ' + report['tests']['status']
    summary += '\n\nNo model was constructed, trained or downloaded. Detailed results: pretraining_gate.json and per-image CSV files.\n'
    if 'execution_error' in report:
        summary += '\nExecution error: ' + report['execution_error'] + '\n'
    mutable_path(out / 'PRETRAINING_GATE_REPORT.md', raw).write_text(summary, encoding='utf-8')
    return report
