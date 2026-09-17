"""Strict baseline configuration and approved train/validation membership."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import yaml

from data.validators.gyu_baseline_v1 import LIST_DIR, MANIFEST_DIR, YAML_PATH, resolve_label, resolve_list_entry, yaml_data
from detection.data.raw_guard import inside, mutable_path, sha256
from detection.data.readonly_verifier import CLASSES, read_csv

PROJECT = Path('outputs/training/defect_detection')
APPROVED_HASHES = {
    YAML_PATH.as_posix(): 'b78bb6f68d51e9a2d98bb18fcce32162d4c15e05ff999dfaf36a0c4d221b639c',
    (LIST_DIR/'train.txt').as_posix(): '7608451e1e2c3b4a3f54398a50cc6e3687024873f9255fc9b838d0abf719258f',
    (LIST_DIR/'valid.txt').as_posix(): '949df7d3ba34166f596dc179897b2c70a242a1a05b136ec48502673e54af4bdf',
    (MANIFEST_DIR/'train.csv').as_posix(): '1a1437aa703ebc9225db58d0c78798ac31f9b913be9c04a568915836c10ade61',
    (MANIFEST_DIR/'valid.csv').as_posix(): '617dacf909fa990b6e807c17eb346e8b4e80010dfe3e068d744cadcc18945b06',
}
REQUIRED = {
    'experiment': 'id description', 'model': 'family size checkpoint pretrained task cache_dir',
    'data': 'yaml identity train_split validation_split test_policy',
    'training': 'imgsz batch epochs optimizer lr0 lrf momentum weight_decay warmup_epochs warmup_momentum warmup_bias_lr nbs cos_lr seed deterministic device workers patience amp cache save save_period resume single_cls cls_remap rect compile channels_last freeze time fraction profile box cls cls_pw dfl',
    'augmentation': 'hsv_h hsv_s hsv_v degrees translate scale shear perspective flipud fliplr bgr mosaic close_mosaic mixup cutmix copy_paste copy_paste_mode multi_scale auto_augment erasing albumentations',
    'output': 'project name exist_ok best_and_last',
    'validation': 'val split plots save_json conf iou max_det nms augment',
    'reproducibility': 'git environment requested_config resolved_config',
}


def load_config(path: Path, root: Path) -> dict:
    """Load a complete config or the narrowly scoped explicit smoke overlay."""
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Training configuration not found: {path}')
    requested = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(requested, dict):
        raise ValueError('Configuration must be a mapping')
    if 'extends' in requested:
        if set(requested) != {'extends', 'smoke'} or requested['extends'] != 'det_baseline.yaml':
            raise ValueError('Smoke config must extend det_baseline.yaml with smoke fields only')
        config = load_config(path.parent/'det_baseline.yaml', root)
        smoke = requested['smoke']
        keys = {'name', 'epochs', 'train_images', 'valid_images', 'selection', 'warmup_epochs', 'close_mosaic', 'save_period'}
        if not isinstance(smoke, dict) or set(smoke) != keys:
            raise ValueError('Missing or unknown smoke fields')
        if (smoke['epochs'] not in (1, 2) or not 64 <= smoke['train_images'] <= 256
                or not 8 <= smoke['valid_images'] <= 64
                or smoke['selection'] != 'sha256(seed:split:relative_path)'
                or smoke['name'] != 'SMOKE-DET-BASELINE'
                or (smoke['warmup_epochs'], smoke['close_mosaic'], smoke['save_period']) != (0, 0, 1)):
            raise ValueError('Smoke restrictions must remain deliberately small and deterministic')
        config['smoke'] = deepcopy(smoke)
        config['experiment']['id'] = config['output']['name'] = smoke['name']
        for key in ('epochs', 'warmup_epochs', 'save_period'):
            config['training'][key] = smoke[key]
        config['augmentation']['close_mosaic'] = smoke['close_mosaic']
    else:
        config = deepcopy(requested)
    validate_config(config, root)
    return config


def validate_config(config: dict, root: Path) -> None:
    """Reject unsafe paths, split substitution, implicit critical values and unsupported modes."""
    if config.get('schema_version') != 1 or set(config) - (set(REQUIRED) | {'schema_version', 'smoke'}):
        raise ValueError('Unknown config fields or schema_version')
    for section, fields in REQUIRED.items():
        if not isinstance(config.get(section), dict) or set(config[section]) != set(fields.split()):
            raise ValueError(f'{section}: missing required fields or unknown fields')
    data, model, train, out = (config[k] for k in ('data', 'model', 'training', 'output'))
    if data != dict(yaml=YAML_PATH.as_posix(), identity='GYU-DET V3 baseline-v1',
                    train_split='train', validation_split='valid', test_policy='prohibited'):
        raise ValueError('Only approved train/valid data permitted; test and CODEBRIM prohibited')
    if model != dict(family='YOLO26', size='s', checkpoint='yolo26s.pt', pretrained=True,
                     task='detect', cache_dir='outputs/cache/models/ultralytics/v8.4.0'):
        raise ValueError('Unsupported model/checkpoint; baseline requires official yolo26s.pt')
    for key in ('imgsz', 'batch', 'epochs', 'nbs', 'patience', 'save_period'):
        if type(train[key]) is not int or train[key] <= 0:
            raise ValueError(f'training.{key} must be a positive integer')
    if train['batch'] > 4 or train['epochs'] > 100:
        raise ValueError('Unapproved detector capacity; use batch <=4, epochs<=100')
    experiment_id = config['experiment']['id']
    approved_imgsz = {
        'DET-BASELINE': 640,
        'SMOKE-DET-BASELINE': 640,
        'DET-IMPROVED-01': 800,
    }
    if experiment_id not in approved_imgsz:
        raise ValueError('Unapproved detector experiment identity')
    if train['imgsz'] != approved_imgsz[experiment_id]:
        raise ValueError(
            f'{experiment_id} requires imgsz={approved_imgsz[experiment_id]}'
        )
    if type(train['seed']) is not int or train['seed'] < 0 or train['workers'] != 0:
        raise ValueError('Use an integer seed and workers=0 for the in-process raw guard')
    if any(train[k] is not False for k in ('cache', 'resume', 'single_cls', 'compile', 'profile', 'rect', 'channels_last')):
        raise ValueError('Disk/RAM image cache, resume, altered classes, compile, profile and rect are disabled')
    if (train['deterministic'] is not True or train['device'] != '0' or train['amp'] != 'bf16'
            or train['optimizer'] != 'SGD' or train['freeze'] is not None or train['time'] is not None
            or train['fraction'] != 1.0 or train['save'] is not True or train['cls_pw'] != 0.0):
        raise ValueError('Unsupported baseline training policy')
    # The installed cfg validator subsequently validates every numeric Ultralytics argument.
    for key in ('lr0', 'lrf', 'momentum', 'weight_decay', 'warmup_epochs', 'warmup_momentum', 'warmup_bias_lr'):
        value = train[key]
        if type(value) not in (int, float) or not 0 <= value < float('inf'):
            raise ValueError(f'Invalid training.{key}')
    if config['validation']['split'] != 'val' or config['validation']['val'] is not True:
        raise ValueError('Development validation must use val; test is prohibited')
    if config['augmentation']['albumentations'] != 'disabled':
        raise ValueError('Implicit optional Albumentations transforms are prohibited')
    if any(value is not True for value in config['reproducibility'].values()):
        raise ValueError('All reproducibility capture is required')
    project = mutable_path(root/out['project'], root/'data/raw')
    if project != (root/PROJECT).resolve():
        raise ValueError('Output must use the controlled training project root')
    if (not re.fullmatch(r'[A-Z0-9][A-Z0-9-]*', out['name']) or out['name'] != config['experiment']['id']
            or out['exist_ok'] is not False or out['best_and_last'] is not True):
        raise ValueError('Invalid run name or checkpoint/output policy')
    run_directory(config, root)


def run_directory(config: dict, root: Path) -> Path:
    """Resolve a fresh run path, following junctions before checking containment."""
    path = mutable_path(root/config['output']['project']/config['output']['name'], root/'data/raw')
    if not inside(path, root/PROJECT):
        raise ValueError('Run path escapes controlled output root')
    return path


def load_development_data(root: Path, dataset: str = YAML_PATH.as_posix()) -> tuple[dict, dict[str, list[dict]]]:
    """Read only approved train/valid lists and manifests; never open test data or lists."""
    if dataset != YAML_PATH.as_posix():
        raise ValueError('Unapproved dataset YAML')
    path = root/dataset
    if not path.is_file():
        raise FileNotFoundError(f'Approved dataset configuration missing: {path}')
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    if data != yaml_data() or data.get('names') != {str(i): name for i, name in enumerate(CLASSES)}:
        raise ValueError('Dataset YAML must retain exact approved class mapping and split paths')
    for rel, digest in APPROVED_HASHES.items():
        if sha256(root/rel) != digest:
            raise ValueError(f'Approved data identity changed: {rel}')
    splits = {}
    seen = set()
    for split, count in (('train', 8305), ('valid', 1040)):
        listing = root/LIST_DIR/f'{split}.txt'
        rows = read_csv(root/MANIFEST_DIR/f'{split}.csv')
        lines = listing.read_text(encoding='utf-8').splitlines()
        if len(rows) != count or len(lines) != count:
            raise ValueError(f'{split}: wrong approved count')
        by_image = {str((root/r['image_relative_path']).resolve()): r for r in rows}
        selected = []
        for line in lines:
            image = resolve_list_entry(listing, line)
            row = by_image.get(str(image))
            if row is None or row['processed_split'] != split or row['raw_split'] != split or str(image) in seen:
                raise ValueError('Unapproved, cross-split or duplicate image')
            label = resolve_label(image)
            if label != (root/row['label_relative_path']).resolve():
                raise ValueError('Image-label association mismatch')
            split_root = root/'data/raw/gyu_det/v3/extracted'/split/split
            if not inside(image, split_root/'images') or not inside(label, split_root/'labels'):
                raise ValueError('Source path escapes approved development split')
            if not image.is_file() or not label.is_file():
                raise FileNotFoundError(f'Missing approved image/label: {image}')
            seen.add(str(image))
            selected.append(dict(row, split=split, image=image, label=label))
        splits[split] = selected
    return data, splits


def select_records(splits: dict[str, list[dict]], config: dict) -> dict[str, list[dict]]:
    """Select a stable smoke subset by seed/path hash, without changing approved lists."""
    if 'smoke' not in config:
        return splits
    seed = config['training']['seed']
    result = {}
    for split, rows in splits.items():
        key = lambda r: hashlib.sha256(f'{seed}:{split}:{r["image_relative_path"]}'.encode()).hexdigest()
        result[split] = sorted(rows, key=key)[:config['smoke'][f'{split}_images']]
    return result
