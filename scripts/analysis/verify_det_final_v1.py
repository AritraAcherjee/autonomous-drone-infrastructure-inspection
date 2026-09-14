"""Offline DET-FINAL-v1 package verification. No training or inference entry point."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath

CHECKPOINT = 'outputs/training/defect_detection/DET-BASELINE/weights/best.pt'
CHECKPOINT_SHA = '4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3'
TRAINING_SHA = '8ee410771c8be794d366e5e014f14f748edca97f'
DATA = 'outputs/training/defect_detection/DET-BASELINE/development_data.yaml'
CLASSES = dict(enumerate(['Crack', 'Breakage', 'Honeycombing', 'Hole', 'Exposed Reinforcement', 'Seepage']))
DIAGNOSTIC_CONF = 0.18618618618618618
MANIFEST = 'configs/detection/det_final_v1.yaml'
RECEIPT = 'outputs/analysis/defect_detection/DET-FINAL-v1/manifest.sha256'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def safe_reference(root, relative):
    """Reject raw/test content and path escapes before opening a reference."""
    require(isinstance(relative, str) and '\\' not in relative, 'Use repository-relative POSIX paths')
    p = PurePosixPath(relative)
    require(not p.is_absolute() and '..' not in p.parts and ':' not in relative, 'Path escape prohibited')
    lower = relative.lower()
    require(not lower.startswith('data/raw/') and 'codebrim' not in lower, 'Raw/CODEBRIM content prohibited')
    require(p.stem.lower() not in ('test', 'test_manifest'), 'Held-out list/manifest prohibited')
    root = Path(root).resolve()
    candidate = root.joinpath(*p.parts)
    require(candidate.resolve().is_relative_to(root), 'Resolved path escapes repository')
    for component in (candidate, *candidate.parents):
        if component == root:
            break
        require(not component.is_symlink() and not getattr(component, 'is_junction', lambda: False)(), 'Aliased reference prohibited')
    return candidate


def validate_manifest(m):
    required = dict(schema_version=1, version='DET-FINAL-v1', status='PREPARED_PENDING_CONTROL_CENTER_APPROVAL',
                    source_experiment='DET-BASELINE', selection_basis='training and validation evidence only',
                    training_git_sha=TRAINING_SHA, freeze_git_base_sha=TRAINING_SHA,
                    checkpoint_path=CHECKPOINT, checkpoint_sha256=CHECKPOINT_SHA, checkpoint_size_bytes=20301573,
                    best_epoch=62, architecture='YOLO26s', framework='Ultralytics', framework_version='8.4.145',
                    task='detect', input_size=640, class_count=6, train_count=8305, validation_count=1040,
                    heldout_test_count=1053, seed=42, deterministic=True, test_accessed=False, codebrim_accessed=False)
    for key, value in required.items():
        require(m.get(key) == value and type(m.get(key)) is type(value), f'Invalid frozen identity: {key}')
    require(m.get('class_mapping') == {str(k): v for k,v in CLASSES.items()}, 'Class mapping must be exactly IDs 0-5')
    expected = dict(mode='val', task='detect', model=CHECKPOINT, imgsz=640, batch=8, device='0', workers=0,
                    rect=True, pad=0.5, stride=32, quantize=16, conf=0.001, iou=0.7, max_det=300,
                    nms=False, end2end=True, augment=False, agnostic_nms=False, single_cls=False,
                    classes=None, fraction=1.0, cache=False, compile=False, channels_last=False, dnn=False,
                    plots=True, visualize=False, save_json=False, save_txt=False, shuffle=False,
                    drop_last=False, pin_memory=True, rank=-1, seed=42, deterministic=True)
    for key, value in expected.items():
        require(m['evaluation_config'].get(key) == value, f'Invalid evaluation setting: {key}')
    require(m['evaluation_config']['replay_split'] == 'val', 'Only validation replay is available')
    require(m['evaluation_config']['data_reference'] == DATA, 'Unapproved data reference')
    require(m['ap_collection_policy']['confidence_floor'] == 0.001, 'AP collection floor changed')
    require(m['ap_collection_policy']['confusion_iou'] == 0.45, 'Confusion IoU changed')
    require(m['threshold_policy']['validation_diagnostic_confidence'] == DIAGNOSTIC_CONF, 'Diagnostic threshold changed')
    require(m['threshold_policy']['grid_index'] == 186, 'Diagnostic index changed')
    require(m['threshold_policy']['heldout_threshold_optimization'] is False, 'Test optimization prohibited')
    require(m['threshold_policy']['deployment_confidence'] is None, 'Deployment threshold unresolved')
    require(m['det_improved_status']['status'] == 'DEFERRED', 'Improved experiment must remain deferred')
    require(m['det_improved_status']['training_executed'] is False, 'No improved training permitted')
    require(m['authorization']['freeze_approved'] is False and m['authorization']['test_authorized'] is False,
            'Preparation is not freeze approval or test authorization')


def validate_development_request(m, root, split='val', data_path=DATA):
    """Fail before file access if an invocation substitutes a held-out split/path."""
    validate_manifest(m)
    require(split == 'val' and data_path == DATA, 'Only exact validation replay binding is permitted')
    path = safe_reference(root, data_path)
    data = read_json(path)
    require(set(data) == {'path', 'train', 'val', 'names', 'nc', 'channels'}, 'Implicit/test/download dataset keys prohibited')
    require(data['nc'] == 6 and data['channels'] == 3, 'Dataset dimensions changed')
    require({str(k):v for k,v in data['names'].items()} == m['class_mapping'], 'Dataset class order changed')
    require(Path(data['path']).resolve() == Path(root).resolve(), 'Dataset root changed')
    for key, name in (('train', 'train.txt'), ('val', 'valid.txt')):
        expected = safe_reference(root, 'outputs/training/defect_detection/DET-BASELINE/'+name)
        require(Path(data[key]).resolve() == expected.resolve(), 'Dataset split path changed')
    return data


def fixed_diagnostic_pr(p_curve, r_curve, class_ids):
    """Select the already-frozen validation grid index; never maximize held-out F1.

    Inputs are the installed evaluator's 1000-point confidence curves (IoU 0.5).
    Missing ground-truth classes remain absent, following Ultralytics AP classes.
    This consumes arrays supplied by a separately authorized caller, not images.
    """
    require(len(p_curve) == len(r_curve) == len(class_ids) > 0, 'Curve/class dimensions differ')
    require(len(set(class_ids)) == len(class_ids) and all(c in CLASSES for c in class_ids), 'Invalid class IDs')
    rows = []
    for c, ps, rs in zip(class_ids, p_curve, r_curve):
        require(len(ps) == len(rs) == 1000, 'Expected installed 1000-point curves')
        p, r = float(ps[186]), float(rs[186])
        require(all(math.isfinite(v) and 0 <= v <= 1 for v in (p,r)), 'Invalid diagnostic values')
        rows.append(dict(class_id=int(c), precision=p, recall=r, f1=2*p*r/(p+r+1e-16)))
    return dict(label='VALIDATION DIAGNOSTIC THRESHOLD', confidence=DIAGNOSTIC_CONF, grid_index=186,
                precision=sum(x['precision'] for x in rows)/len(rows), recall=sum(x['recall'] for x in rows)/len(rows),
                f1=sum(x['f1'] for x in rows)/len(rows), per_class=rows, threshold_optimized=False)


def verify_package(root, package_root=None):
    root = Path(root).resolve()
    package_root = Path(package_root or root).resolve()
    manifest_path = safe_reference(package_root, MANIFEST)
    m = read_json(manifest_path)
    validate_manifest(m)
    receipt = safe_reference(package_root, RECEIPT).read_text().split()
    require(receipt == [sha256(manifest_path), MANIFEST], 'Manifest receipt mismatch')
    index_ref = m['evidence_index']
    index_path = safe_reference(package_root, index_ref['path'])
    require(sha256(index_path) == index_ref['sha256'], 'Evidence index mismatch')
    index = read_json(index_path)
    for item in index['references']:
        rel = item['path']
        package_path = safe_reference(package_root, rel)
        p = package_path if package_path.is_file() else safe_reference(root, rel)
        require(p.is_file() and sha256(p) == item['sha256'] and p.stat().st_size == item['size_bytes'], f'Evidence mismatch: {rel}')
    checkpoint = safe_reference(root, CHECKPOINT)
    require(checkpoint.stat().st_size == m['checkpoint_size_bytes'] and sha256(checkpoint) == CHECKPOINT_SHA,
            'Checkpoint mismatch')
    validate_development_request(m, root)
    return dict(status='PASS', version=m['version'], manifest_sha256=sha256(manifest_path),
                checkpoint_sha256=CHECKPOINT_SHA, verified_references=len(index['references']),
                test_accessed=False, codebrim_accessed=False, inference_executed=False, training_executed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--package-root', type=Path, help='Prepared overlay for pre-placement verification')
    args = parser.parse_args()
    print(json.dumps(verify_package(args.root, args.package_root), indent=2))
