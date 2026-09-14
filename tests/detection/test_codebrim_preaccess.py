"""Metadata and synthetic detections only; no model inference or benchmark reads."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from detection.generalization.manifest import file_hash, object_hash, reserve, validate_bundle
from detection.generalization.preaccess import INFERENCE, METRICS, PROVENANCE, validate_preaccess
from detection.generalization.prediction_export import (
    assemble_bundle, normalize_predictions, serialize_predictions, validate_prediction_export)
from detection.generalization.schema import CLASSES, validate_manifest, validate_records
from detection.generalization.taxonomy import map_region_labels, shared_classes, validate_crosswalk


def manifest():
    return json.loads((ROOT/'configs/generalization/experiments/GEN-CODEBRIM-ZS-001.json').read_text())


def ontology():
    return json.loads((ROOT/'configs/generalization/ontology_crosswalk.yaml').read_text())


def results(rows=None):
    rows = rows if rows is not None else [([1, 2, 30, 40], 4., 0.8), ([2, 3, 20, 30], 5., 0.002)]
    return SimpleNamespace(orig_shape=(80, 100), names=CLASSES.copy(),
        boxes=SimpleNamespace(xyxy=[r[0] for r in rows], cls=[r[1] for r in rows], conf=[r[2] for r in rows]))


@pytest.mark.parametrize('key', list(PROVENANCE))
def test_corrected_provenance_and_checkpoint_binding(key):
    m = manifest()
    assert m[key] == PROVENANCE[key]
    validate_preaccess(m)
    m[key] = 'wrong'
    with pytest.raises(ValueError):
        validate_preaccess(m)


@pytest.mark.parametrize('key', list(INFERENCE))
def test_exact_frozen_inference_roundtrip_and_drift(key):
    m = json.loads(json.dumps(manifest()))
    assert m['resolved_inference_config'] == INFERENCE
    m['resolved_inference_config'][key] = 'changed'
    with pytest.raises(ValueError, match='inference'):
        validate_preaccess(m)


def test_thresholds_remain_distinct():
    m = manifest()
    assert m['ap_confidence_floor'] == 0.001
    assert m['operating_confidence'] == 0.18618618618618618
    assert m['resolved_inference_config']['iou'] == 0.7
    assert m['ap_ious'] == [0.5,0.55,0.6,0.65,0.7,0.75,0.8,0.85,0.9,0.95]
    assert m['matching_iou'] == 0.5
    assert (m['confusion_matrix_comparison'], m['confusion_matrix_iou']) == ('>',0.45)
    assert m['nms_mode'] == 'none' and m['resolved_inference_config']['nms'] is False
    for key in METRICS:
        altered = deepcopy(m)
        altered[key] = None
        with pytest.raises(ValueError):
            validate_preaccess(altered)


def test_byte_and_canonical_hash_bindings():
    m = manifest()
    for kind in ('ontology','protocol'):
        path = ROOT/m[kind+'_path']
        value = json.loads(path.read_text())
        assert file_hash(path) == m[kind+'_file_sha256']
        assert object_hash(value) == m[kind+'_sha256']
        assert value['version'] == m[kind+'_version']
    protocol = json.loads((ROOT/m['protocol_path']).read_text())
    assert protocol['resolved_inference_config'] == INFERENCE
    assert all(protocol[k] == m[k] for k in METRICS)


def test_approved_shared_classes_and_aggregate_label():
    c = ontology()
    validate_crosswalk(c)
    assert shared_classes(c) == [0,1,4]
    assert map_region_labels(['Crack','Spallation','ExposedBars','Efflorescence','CorrosionStain'], c) == (
        [0,1,4], ['CorrosionStain','Efflorescence'])
    assert c['excluded_gyu'] == ['Honeycombing','Hole','Seepage']
    assert c['external_aggregate_label'] == manifest()['external_aggregate_label'] == 'shared-class CODEBRIM mAP'


def test_only_shared_classes_enter_synthetic_report(tmp_path):
    from detection.generalization.metrics import evaluate
    from detection.generalization.reporting import write_report
    m = manifest()
    fragment = normalize_predictions([('a.jpg', results())], m)
    regions = [dict(id='r1', image_id='a.jpg', box=[1,2,30,40], labels=[4,5])]
    result = evaluate(fragment['images'], fragment['predictions'], regions, shared_classes(ontology()),
        ap_floor=0.001, operating_confidence=m['operating_confidence'], matching_iou=0.5, ap_ious=m['ap_ious'])
    assert result['summary']['scored_classes'] == [0,1,4]
    assert {r['class_id'] for r in result['per_class']} == {0,1,4}
    write_report(tmp_path, m, result)
    assert json.loads((tmp_path/'results.json').read_text())['summary']['aggregate_label'] == 'shared-class CODEBRIM mAP'
    assert 'shared-class CODEBRIM mAP' in (tmp_path/'domain_comparison.csv').read_text()


@pytest.mark.parametrize('gyu_id,label', [(5,'Efflorescence'),(2,'Crack'),(3,'Spallation'),(0,'ExposedBars')])
def test_unapproved_mapping_rejected(gyu_id, label):
    c = ontology()
    c['mappings'][gyu_id].update(external_label=label,status='approved',approval='synthetic')
    with pytest.raises(ValueError):
        validate_crosswalk(c)


def test_normalized_serialization_and_all_six_classes_retained():
    m = manifest()
    row = results([([0,0,10,10], float(c), 0.1 + c/10) for c in CLASSES])
    fragment = normalize_predictions([('bridge/a.jpg',row),('bridge/empty.jpg',results([]))],m)
    decoded = json.loads(serialize_predictions(fragment,m))
    assert decoded == fragment
    assert decoded['images'] == ['bridge/a.jpg','bridge/empty.jpg']
    assert [p['class_id'] for p in decoded['predictions']] == list(CLASSES)
    assert decoded['predictions'][5]['class_name'] == 'Seepage'
    assert decoded['predictions'][0]['box'] == [0,0,10,10]
    assert decoded['image_metadata'][0]['original_width'] == 100
    assert decoded['image_metadata'][0]['original_height'] == 80
    assert decoded['model_provenance']['checkpoint_sha256'] == PROVENANCE['checkpoint_sha256']
    validate_records(decoded['images'], decoded['predictions'], [])


def test_deterministic_prediction_order_and_duplicate_boxes():
    m = manifest()
    rows = [([1,2,3,4], 0., 0.2),([2,3,4,5], 1., 0.9),([1,2,3,4], 0., 0.2)]
    a = normalize_predictions([('z.jpg',results(rows)),('a.jpg',results([]))],m)
    b = normalize_predictions([('a.jpg',results([])),('z.jpg',results(list(reversed(rows))))],m)
    assert serialize_predictions(a,m) == serialize_predictions(b,m)
    assert len(a['predictions']) == 3


@pytest.mark.parametrize('rows', [
    [([0,0,1,1],0.5,0.3)], [([0,0,1,1],True,0.3)], [([0,0,1,1],9,0.3)],
    [([0,0,1,1],0,float('nan'))], [([-1,0,1,1],0,0.3)], [([0,0,101,1],0,0.3)],
    [([0,0,0,1],0,0.3)]])
def test_malformed_result_rejected(rows):
    with pytest.raises(ValueError):
        normalize_predictions([('a.jpg',results(rows))],manifest())


@pytest.mark.parametrize('identity', ['../a.jpg','C:/a.jpg','/a.jpg','a\\b.jpg','a/./b.jpg'])
def test_unsafe_identity_rejected(identity):
    with pytest.raises(ValueError):
        normalize_predictions([(identity,results())],manifest())


def test_malformed_export_rejected():
    m = manifest()
    good = normalize_predictions([('a.jpg',results())],m)
    for key in good:
        bad = deepcopy(good)
        del bad[key]
        with pytest.raises(ValueError):
            validate_prediction_export(bad,m)
    bad = deepcopy(good)
    bad['predictions'][0]['class_name'] = 'wrong'
    with pytest.raises(ValueError):
        serialize_predictions(bad,m)


def test_existing_evaluator_bundle_contract():
    m = manifest()
    m['experiment_id'] = 'synthetic-adapter-bundle'
    regions = [dict(id='r1',image_id='a.jpg',box=[1,2,30,40],labels=[0,4])]
    # Synthetic identity hash is constructed, never recorded as CODEBRIM evidence.
    m['dataset']['sha256'] = object_hash(dict(images=['a.jpg'],regions=regions))
    fragment = normalize_predictions([('a.jpg',results())],m)
    bundle = assemble_bundle(fragment,regions,m)
    validate_bundle(bundle,m)
    assert bundle['regions'] == regions
    with pytest.raises(ValueError):
        assemble_bundle(fragment,[],m)


def test_adapter_has_no_payload_io_metric_or_inference_calls():
    m, r = manifest(), results()
    import detection.generalization.metrics as metrics
    with patch('builtins.open',side_effect=AssertionError('file access')), \
         patch.object(Path,'open',side_effect=AssertionError('path access')), \
         patch('socket.socket',side_effect=AssertionError('network')), \
         patch.object(metrics,'evaluate',side_effect=AssertionError('metric computation')):
        fragment = normalize_predictions([('constructed/never-created.jpg',r)],m)
        assert json.loads(serialize_predictions(fragment,m))['predictions'][1]['confidence'] == 0.002
    import ast
    import detection.generalization.prediction_export as adapter
    tree = ast.parse(Path(adapter.__file__).read_text())
    imported = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(name and ('metrics' in name or 'ultralytics' in name or 'torch' in name) for name in imported)


def test_acquisition_is_unexecuted_and_scientific_gate_closed():
    a = json.loads((ROOT/'data/manifests/codebrim_acquisition.json').read_text())
    for key in ('accessed','downloaded','extracted','inference_executed','acquisition_authorized'):
        assert a[key] is False
    assert a['local_checksum'] is a['download_timestamp'] is a['extraction_timestamp'] is None
    assert a['original_payload_immutable'] is True
    assert a['canonical_ignored_destination'] == 'data/raw/codebrim'
    with pytest.raises(ValueError):
        validate_manifest(manifest(),scientific=True)


def test_exact_experiment_overwrite_protection(tmp_path):
    m = manifest()
    reserve(tmp_path,m)
    m['status'] = 'changed manifest cannot bypass reservation'
    with pytest.raises(FileExistsError):
        reserve(tmp_path,m)


def test_environment_provenance():
    m = manifest()
    assert m['environment']['python'] == '3.12.14'
    assert m['environment']['packages']['ultralytics'] == '8.4.145'
    evidence = json.loads((ROOT/m['environment']['reference']).read_text())
    assert evidence['after']['python'] == '3.12.14'
    assert evidence['after']['packages']['ultralytics'] == '8.4.145'
    assert evidence['after']['packages']['torch'] == '2.14.0+cu130'
    assert evidence['inference_executed'] is False
