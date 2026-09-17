"""Serialize already-produced detections. No model, file-reader or metric backend."""
from copy import deepcopy
from pathlib import PurePosixPath

from .manifest import canonical, object_hash, validate_bundle
from .schema import CLASSES, nonempty, require, validate_manifest, validate_records


def _list(value):
    # Tensor-like objects are detached without importing torch or Ultralytics.
    if hasattr(value, 'detach'):
        value = value.detach().cpu()
    return value.tolist() if hasattr(value, 'tolist') else value


def _relative(value):
    require(nonempty(value) and '\\' not in value and ':' not in value,
            'Expected source-relative POSIX identity')
    path = PurePosixPath(value)
    require(not path.is_absolute() and '..' not in path.parts and str(path) == value
            and value != '.', 'Unsafe source-relative identity')
    return value


def _provenance_keys(manifest):
    common = (
        'model_id',
        'architecture',
        'framework',
        'framework_version',
        'checkpoint_path',
        'checkpoint_sha256',
        'training_git_sha',
        'freeze_commit_sha',
        'protocol_sha256',
        'protocol_file_sha256',
        'ontology_sha256',
        'ontology_file_sha256',
    )

    if (
        manifest.get('manifest_kind')
        == 'runtime_scientific_manifest'
    ):
        return common + (
            'evaluation_git_sha',
            'portable_contract_sha256',
            'portable_contract_file_sha256',
        )

    return common + ('evaluation_main_sha',)


def normalize_predictions(entries, manifest):
    """Entries: (source-relative identity, Ultralytics-style Results), including empty images.

    Results.boxes.xyxy must already be in the original image coordinate frame,
    as in 02's scale_boxes export. No resizing, remapping, filtering or clipping
    is performed. result.path/orig_img are deliberately never accessed.
    """
    validate_manifest(manifest)
    images, metadata, predictions = [], [], []
    for identity, result in entries:
        image_id = _relative(identity)
        require(image_id not in images, 'Duplicate image identity')
        shape = _list(result.orig_shape)
        require(isinstance(shape, (list, tuple)) and len(shape) == 2
                and all(type(n) is int and n > 0 for n in shape), 'Invalid original shape')
        height, width = shape
        require(result.names == CLASSES, 'Result class mapping differs from baseline')
        boxes, classes, scores = (_list(result.boxes.xyxy), _list(result.boxes.cls), _list(result.boxes.conf))
        require(all(isinstance(v, list) for v in (boxes, classes, scores))
                and len(boxes) == len(classes) == len(scores), 'Mismatched box arrays')
        images.append(image_id)
        metadata.append(dict(image_id=image_id, source_relative_path=image_id,
                             original_width=width, original_height=height))
        for box, class_id, confidence in zip(boxes, classes, scores):
            require(type(class_id) in (int, float) and class_id in CLASSES, 'Invalid class ID')
            row = dict(id='temporary', image_id=image_id, source_relative_path=image_id,
                       class_id=int(class_id), class_name=CLASSES[int(class_id)],
                       confidence=confidence, box=box, original_width=width, original_height=height)
            validate_records([image_id], [row], [])
            require(box[2] <= width and box[3] <= height, 'Box exceeds original shape')
            predictions.append(row)
    images.sort()
    metadata.sort(key=lambda r: r['image_id'])
    predictions.sort(key=lambda r: (r['image_id'], r['class_id'], -r['confidence'], tuple(r['box'])))
    for index, row in enumerate(predictions):
        row['id'] = f'prediction-{index:09d}'
    validate_records(images, predictions, [])
    provenance_keys = _provenance_keys(manifest)
    require(all(manifest.get(k) is not None for k in provenance_keys), 'Missing export provenance')
    return dict(images=images, image_metadata=metadata, predictions=predictions,
                manifest_sha256=object_hash(manifest),
                inference_config=deepcopy(manifest['resolved_inference_config']),
                inference_config_sha256=object_hash(manifest['resolved_inference_config']),
                model_provenance={k: deepcopy(manifest[k]) for k in provenance_keys})


def assemble_bundle(fragment, regions, manifest):
    """Join separately approved, already ontology-normalized regions in memory.

    Future acquisition must supply a dataset identity/hash. This cannot turn the
    unacquired pre-access manifest into a scientific scoring authorization.
    """
    validate_prediction_export(fragment, manifest)
    bundle = deepcopy(fragment)
    bundle.update(regions=deepcopy(regions), dataset=deepcopy(manifest['dataset']))
    validate_records(bundle['images'], bundle['predictions'], bundle['regions'])
    validate_bundle(bundle, manifest)
    return bundle


def validate_prediction_export(fragment, manifest):
    require(isinstance(fragment, dict), 'Export must be an object')
    validate_records(fragment.get('images'), fragment.get('predictions'), [])
    require(fragment.get('manifest_sha256') == object_hash(manifest), 'Manifest binding differs')
    require(fragment.get('inference_config') == manifest['resolved_inference_config']
            and fragment.get('inference_config_sha256') == object_hash(manifest['resolved_inference_config']),
            'Inference binding differs')
    provenance = fragment.get('model_provenance', {})
    keys = _provenance_keys(manifest)
    require(set(provenance) == set(keys) and all(provenance[k] == manifest[k] for k in keys),
            'Model provenance differs')
    metadata = fragment.get('image_metadata')
    require(isinstance(metadata, list) and len(metadata) == len(fragment['images']), 'Missing image metadata')
    require([r.get('image_id') for r in metadata] == fragment['images'], 'Image metadata differs')
    by_id = {}
    for row in metadata:
        require(row.get('source_relative_path') == _relative(row['image_id']), 'Image identity differs')
        require(all(type(row.get(k)) is int and row[k] > 0 for k in ('original_width', 'original_height')),
                'Invalid original dimensions')
        by_id[row['image_id']] = row
    for row in fragment['predictions']:
        require(row.get('class_name') == CLASSES[row['class_id']], 'Class name differs')
        require(all(row.get(k) == by_id[row['image_id']][k]
                    for k in ('source_relative_path', 'original_width', 'original_height')), 'Prediction image differs')
        require(row['box'][2] <= row['original_width'] and row['box'][3] <= row['original_height'],
                'Box exceeds original shape')
    return fragment


def serialize_predictions(fragment, manifest):
    """Return deterministic UTF-8 JSON bytes for the caller's approved writer."""
    validate_prediction_export(fragment, manifest)
    return canonical(fragment) + b'\n'
