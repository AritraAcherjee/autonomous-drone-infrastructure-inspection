"""Strict provenance and normalized detection contracts."""
import math
import re


CLASSES = {0: 'Crack', 1: 'Breakage', 2: 'Honeycombing', 3: 'Hole',
           4: 'Exposed Reinforcement', 5: 'Seepage'}
AP_IOUS = [round(0.5 + i * 0.05, 2) for i in range(10)]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def digest(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value) is not None


def probability(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def validate_manifest(m, scientific=False):
    require(isinstance(m, dict), 'Manifest must be an object')
    require(m.get('schema_version') == 1, 'Unsupported manifest schema')
    require(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', str(m.get('experiment_id', ''))) is not None,
            'Unsafe experiment ID')
    require(m.get('phase') in ('pre_freeze', 'frozen'), 'Unknown phase')
    if not scientific and m['phase'] == 'pre_freeze':
        require(m.get('frozen') is False, 'Pre-freeze manifest cannot be frozen')
        if m.get('experiment_id') == 'GEN-CODEBRIM-ZS-001':
            from .preaccess import validate_preaccess
            validate_preaccess(m)
        elif m.get('experiment_id') == 'GEN-DAMSEGMENT-ZS-001':
            from .damsegment_preaccess import validate_preaccess
            validate_preaccess(m)
        return m
    require(m['phase'] == 'frozen' and m.get('frozen') is True, 'Scientific scoring requires a frozen baseline')
    for key in ('architecture', 'architecture_version', 'checkpoint_path', 'ontology_version', 'freeze_approval'):
        require(nonempty(m.get(key)), 'Missing ' + key)
    for key in ('checkpoint_sha256', 'ontology_sha256', 'protocol_sha256'):
        require(digest(m.get(key)), 'Invalid ' + key)
    for key in ('training_git_sha', 'evaluation_git_sha'):
        require(digest(m.get(key), 40), 'Invalid ' + key)
    for key in ('training_config', 'resolved_inference_config', 'validation_evidence'):
        require(isinstance(m.get(key), dict) and bool(m[key]), 'Missing ' + key)
    ds = m.get('dataset', {})
    require(isinstance(ds, dict) and all(nonempty(ds.get(k)) for k in ('identity', 'version', 'split'))
            and digest(ds.get('sha256')), 'Incomplete dataset identity/version/split/hash')
    require(ds['identity'] in ('GYU-DET', 'CODEBRIM', 'DamSegment'), 'Unknown scientific dataset')
    if ds['identity'] == 'GYU-DET':
        require(ds['version'] == 'v3/baseline-v1' and ds['split'] == 'test', 'Require approved GYU baseline-v1 test')
        require(digest(ds.get('source_manifest_sha256')), 'GYU source split manifest hash required')
    else:
        if ds['identity'] == 'DamSegment':
            require(ds['version'] == 'v1' and ds['split'] == 'Damage Detection',
                    'Require approved DamSegment v1 Damage Detection subset')
        require(m.get('external_review', {}).get('taxonomy_approved') is True
                and m.get('external_review', {}).get('leakage_audit_passed') is True
                and nonempty(m.get('external_review', {}).get('evidence')), 'External review evidence required')
    require(m.get('class_mapping') == {str(k): v for k, v in CLASSES.items()}, 'Class mapping differs from baseline')
    size = m.get('image_size')
    require(isinstance(size, list) and len(size) == 2 and all(type(v) is int and v > 0 for v in size), 'Invalid image size')
    for key in ('ap_confidence_floor', 'operating_confidence', 'nms_iou', 'matching_iou'):
        require(probability(m.get(key)), 'Invalid ' + key)
    require(m['matching_iou'] > 0, 'Matching IoU must be positive')
    require(m['ap_confidence_floor'] <= m['operating_confidence'], 'AP floor exceeds operating confidence')
    require(m.get('ap_ious') in ([0.5], AP_IOUS), 'AP IoUs must be 0.5 or 0.5:0.95')
    require(m.get('nms_mode') in ('class_aware', 'class_agnostic', 'none'), 'Invalid NMS mode')
    require(type(m.get('max_detections')) is int and m['max_detections'] > 0, 'Invalid max detections')
    require(type(m.get('seed')) is int and m['seed'] >= 0, 'Explicit nonnegative seed required')
    env = m.get('environment', {})
    require(isinstance(env, dict) and nonempty(env.get('python')) and nonempty(env.get('platform'))
            and isinstance(env.get('packages'), dict) and bool(env['packages'])
            and all(nonempty(v) for v in env['packages'].values()), 'Incomplete environment/package versions')
    for key in ('image_size', 'ap_confidence_floor', 'operating_confidence', 'nms_iou', 'nms_mode', 'max_detections', 'seed'):
        require(m['resolved_inference_config'].get(key) == m[key], 'Inference configuration disagrees: ' + key)
    return m


def validate_records(images, predictions, regions):
    require(isinstance(images, list) and images and all(nonempty(i) for i in images)
            and len(set(images)) == len(images), 'Unique image inventory required, including empty images')
    for records, prediction in ((predictions, True), (regions, False)):
        require(isinstance(records, list), 'Records must be a list')
        ids = set()
        for r in records:
            require(isinstance(r, dict) and nonempty(r.get('id')) and r['id'] not in ids, 'Duplicate/missing record ID')
            ids.add(r['id'])
            require(r.get('image_id') in images, 'Unknown image')
            box = r.get('box')
            require(isinstance(box, list) and len(box) == 4 and all(type(x) in (int, float) and math.isfinite(x) for x in box)
                    and 0 <= box[0] < box[2] and 0 <= box[1] < box[3], 'Invalid pixel xyxy box')
            if prediction:
                require(type(r.get('class_id')) is int and r['class_id'] in CLASSES and probability(r.get('confidence')), 'Invalid prediction')
            else:
                labels = r.get('labels')
                require(isinstance(labels, list) and labels and len(set(labels)) == len(labels)
                        and all(type(c) is int and c in CLASSES for c in labels), 'Invalid region labels')
