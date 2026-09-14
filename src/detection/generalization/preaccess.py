"""GEN-CODEBRIM-ZS-001 metadata contract; never reads a benchmark payload."""
from .manifest import canonical
from .schema import AP_IOUS, CLASSES, digest, require

EXPERIMENT = 'GEN-CODEBRIM-ZS-001'
PROVENANCE = dict(
    training_git_sha='8ee410771c8be794d366e5e014f14f748edca97f',
    freeze_commit_sha='d9cd2f5b58559d45e5d4a42ce702c595345e292b',
    evaluation_main_sha='7ed9160d08876b748754919efd7bba770fb20a87',
    checkpoint_path='outputs/training/defect_detection/DET-BASELINE/weights/best.pt',
    checkpoint_sha256='4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3',
    model_id='DET-FINAL-v1', architecture='YOLO26s', framework='Ultralytics',
    framework_version='8.4.145', best_epoch=62)
INFERENCE = dict(imgsz=640, batch=8, device='CUDA:0', workers=0, rect=True, pad=0.5,
                 FP16=True, conf=0.001, iou=0.7, max_det=300, nms=False, augment=False,
                 agnostic_nms=False, single_cls=False, cache=False, compile=False,
                 shuffle=False, drop_last=False, end2end=True)
METRICS = dict(ap_confidence_floor=0.001, operating_confidence=0.18618618618618618,
               matching_iou=0.50, ap_ious=AP_IOUS, nms_iou=0.7, nms_mode='none',
               max_detections=300, confusion_matrix_iou=0.45,
               confusion_matrix_comparison='>', external_aggregate_label='shared-class CODEBRIM mAP')


def validate_preaccess(m):
    require(m.get('experiment_id') == EXPERIMENT, 'Wrong experiment ID')
    for key, value in PROVENANCE.items():
        require(m.get(key) == value, 'Frozen provenance differs: ' + key)
    # Canonical equality rejects bool/int substitutions as well as extra fields.
    require(canonical(m.get('resolved_inference_config')) == canonical(INFERENCE), 'Frozen inference differs')
    for key, value in METRICS.items():
        require(canonical(m.get(key)) == canonical(value), 'Frozen metric differs: ' + key)
    require(m.get('class_mapping') == {str(k): v for k, v in CLASSES.items()}, 'Class mapping differs')
    for key in ('ontology_sha256', 'ontology_file_sha256', 'protocol_sha256', 'protocol_file_sha256'):
        require(digest(m.get(key)), 'Invalid ' + key)
    require(m.get('phase') == 'pre_freeze' and m.get('frozen') is False
            and m.get('preaccess_config_frozen') is True, 'Pre-access is not scientific authorization')
    require(m.get('dataset', {}).get('role') == 'protected external benchmark'
            and m['dataset'].get('sha256') is None, 'Dataset must remain unacquired')
    require(m.get('environment', {}).get('python') == '3.12.14'
            and m['environment'].get('packages', {}).get('ultralytics') == '8.4.145', 'Environment differs')
    return m
