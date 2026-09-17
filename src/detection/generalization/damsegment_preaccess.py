"""GEN-DAMSEGMENT-ZS-001 pre-access contract; never runs model inference."""
from .manifest import canonical
from .schema import AP_IOUS, CLASSES, digest, require


EXPERIMENT = 'GEN-DAMSEGMENT-ZS-001'

PROVENANCE = dict(
    training_git_sha='8ee410771c8be794d366e5e014f14f748edca97f',
    freeze_commit_sha='d9cd2f5b58559d45e5d4a42ce702c595345e292b',
    evaluation_base_sha='3fc6ac001e71c1ab56b2b810cd2d595358a55e28',
    checkpoint_path='outputs/training/defect_detection/DET-BASELINE/weights/best.pt',
    checkpoint_sha256='4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3',
    model_id='DET-FINAL-v1',
    architecture='YOLO26s',
    framework='Ultralytics',
    framework_version='8.4.145',
    best_epoch=62,
)

INFERENCE = dict(
    imgsz=640,
    batch=8,
    device='CUDA:0',
    workers=0,
    rect=True,
    pad=0.5,
    FP16=True,
    conf=0.001,
    iou=0.7,
    max_det=300,
    nms=False,
    augment=False,
    agnostic_nms=False,
    single_cls=False,
    cache=False,
    compile=False,
    shuffle=False,
    drop_last=False,
    end2end=True,
)

METRICS = dict(
    ap_confidence_floor=0.001,
    operating_confidence=0.18618618618618618,
    matching_iou=0.50,
    ap_ious=AP_IOUS,
    nms_iou=0.7,
    nms_mode='none',
    max_detections=300,
    confusion_matrix_iou=0.45,
    confusion_matrix_comparison='>',
    external_aggregate_label='shared-class DamSegment mAP',
)

DATASET = dict(
    identity='DamSegment',
    version='v1',
    split='Damage Detection',
    role='protected external benchmark',

    # Canonical object hash of the prepared 03 images+regions contract.
    sha256='a75a29496ba8bb76f49db5a36b64a9920911b5e4c420f634a4390deb418e14df',

    doi='10.17632/z5z6gtt5t4.1',
    license='CC BY 4.0',

    outer_archive_filename='DamSegment.zip',
    outer_archive_size_bytes=445519020,
    outer_archive_sha256='f195ba0730f12a68e6e7b1d685b555fe2872b870a0686ffa3a5c397200fd63e6',

    detection_archive_filename='Damage Detection.zip',
    detection_archive_sha256='2423567183c584568efd45a2f4521c5d5f3f65106f2d2ff1311ed99b7adba1a9',

    image_count=1500,
    yolo_annotation_files=1500,
    pascal_voc_style_json_files=1500,
    annotation_instances=19710,

    annotation_formats=[
        'YOLO TXT normalized bounding boxes',
        'Pascal VOC-style JSON pixel bounding boxes',
    ],

    image_geometry=[640, 640],

    source_class_ids={
        '0': 'Crack',
        '1': 'Spalling',
    },

    approved_crosswalk={
        '0': {
            'source_label': 'Crack',
            'aegis_id': 0,
            'aegis_label': 'Crack',
        },
        '1': {
            'source_label': 'Spalling',
            'aegis_id': 1,
            'aegis_label': 'Breakage',
        },
    },

    excluded_aegis_classes={
        '2': 'Honeycombing',
        '3': 'Hole',
        '4': 'Exposed Reinforcement',
        '5': 'Seepage',
    },

    prepared_inventory_sha256='a75a29496ba8bb76f49db5a36b64a9920911b5e4c420f634a4390deb418e14df',
    prepared_artifact_file_sha256='dabc0bb394127d7dc5d90b8441bdb64f91e7b6606c07994e300b4a6aeb124f70',

    prepared_image_count=1500,
    prepared_region_count=19710,

    prepared_regions_per_aegis_class={
        '0': 19229,
        '1': 481,
    },

    prepared_empty_image_count=3,

    external_use_policy={
        'used_for_training': False,
        'used_for_tuning': False,
        'used_for_model_selection': False,
        'replacement_for_gyu_locked_test': False,
    },
)

LEAKAGE = dict(
    gate_status='PASS_NO_CANDIDATES',
    exact_sha_overlap_count=0,
    near_duplicate_candidate_count=0,
    locked_gyu_test_raw_accessed=False,
    fingerprint_csv_sha256='acdad437124f5940ce23e94d82996e87cd5fe5562b2870fc89c92ff7feaaa85d',
    summary_sha256='3f7a3633fa16b83add219796f63801731ca79ad47c6abecfadaae29728e1d3f5',
    exact_overlap_csv_sha256='2414cbc40ec805e39037d3b04786290a96c160ac28150a3392b92379cbf8db67',
    near_candidate_csv_sha256='10a369867900b0fbbf4a65f115498c8bdc3e08917b3a4a008ca9f50b0a3f2e40',
)


def validate_preaccess(m):
    require(
        m.get('experiment_id') == EXPERIMENT,
        'Wrong experiment ID',
    )

    for key, value in PROVENANCE.items():
        require(
            m.get(key) == value,
            'Frozen provenance differs: ' + key,
        )

    require(
        canonical(m.get('resolved_inference_config'))
        == canonical(INFERENCE),
        'Frozen inference differs',
    )

    for key, value in METRICS.items():
        require(
            canonical(m.get(key)) == canonical(value),
            'Frozen metric differs: ' + key,
        )

    require(
        m.get('class_mapping')
        == {str(k): v for k, v in CLASSES.items()},
        'Class mapping differs',
    )

    for key in (
        'ontology_sha256',
        'ontology_file_sha256',
        'protocol_sha256',
        'protocol_file_sha256',
    ):
        require(
            digest(m.get(key)),
            'Invalid ' + key,
        )

    require(
        m.get('phase') == 'pre_freeze'
        and m.get('frozen') is False
        and m.get('preaccess_config_frozen') is True,
        'Pre-access is not scientific authorization',
    )

    dataset = m.get('dataset', {})

    require(
        canonical(dataset) == canonical(DATASET),
        'DamSegment dataset identity/provenance differs',
    )

    review = m.get('external_review', {})

    require(
        review.get('taxonomy_approved') is True
        and review.get('leakage_audit_passed') is True
        and review.get('leakage_gate_status') == 'PASS_NO_CANDIDATES'
        and review.get('locked_gyu_test_raw_accessed') is False,
        'DamSegment external review is incomplete',
    )

    require(
        canonical(m.get('leakage_evidence'))
        == canonical(LEAKAGE),
        'Leakage evidence differs',
    )

    require(
        m.get('scientific_execution_authorized') is False,
        'Scientific execution must remain unauthorized',
    )

    env = m.get('environment', {})

    require(
        env.get('python') == '3.11.15',
        'Unexpected Python environment',
    )

    packages = env.get('packages', {})

    require(
        packages.get('ultralytics') == '8.4.145'
        and packages.get('torch') == '2.14.0+cu130'
        and packages.get('torchvision') == '0.29.0+cu130',
        'Unexpected detector package environment',
    )

    return m
