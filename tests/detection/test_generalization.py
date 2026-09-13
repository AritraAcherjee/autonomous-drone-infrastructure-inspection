"""Generalization tests use only constructed synthetic boxes and metadata."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from detection.generalization.schema import AP_IOUS, CLASSES, validate_manifest, validate_records
from detection.generalization.manifest import experiment_name, frozen_gate, object_hash, reserve, validate_bundle
from detection.generalization.manifest import read_json_with_hash
from detection.generalization.taxonomy import map_region_labels, shared_classes, validate_crosswalk
from detection.generalization.matching import match_class
from detection.generalization.metrics import average_precision, counts, evaluate
from detection.generalization.calibration import reliability
from detection.generalization.failures import FailureCategory, category_counts, failure_record
from detection.generalization.reporting import TABLES, write_report, write_tables


def crosswalk():
    return dict(version='synthetic-v1', gyu_classes={str(k): v for k, v in CLASSES.items()},
                mappings=[dict(gyu_id=c, external_label={0: 'Crack', 1: 'Spallation', 4: 'Exposed reinforcement bar'}.get(c),
                               status='approved' if c in (0, 1, 4) else 'unmapped', approval='synthetic review') for c in CLASSES],
                external_only=['Efflorescence', 'Corrosion/stain'])


def manifest():
    m = dict(schema_version=1, experiment_id='synthetic-01', phase='frozen', frozen=True,
             architecture='synthetic-detector', architecture_version='1', checkpoint_path=str(ROOT / 'synthetic.pt'),
             checkpoint_sha256='a'*64, training_git_sha='b'*40, evaluation_git_sha='c'*40,
             training_config={'synthetic': True}, ontology_version='synthetic-v1', ontology_sha256=object_hash(crosswalk()),
             protocol_sha256=object_hash({'synthetic': True}), image_size=[100, 100], ap_confidence_floor=0.01,
             operating_confidence=0.5, matching_iou=0.5, ap_ious=AP_IOUS, nms_iou=0.5, nms_mode='class_aware',
             max_detections=100, seed=0, class_mapping={str(k): v for k, v in CLASSES.items()},
             environment={'python': 'synthetic', 'platform': 'synthetic', 'packages': {'synthetic': '1'}},
             validation_evidence={'reference': 'synthetic'}, freeze_approval='synthetic-review',
             dataset={'identity': 'GYU-DET', 'version': 'v3/baseline-v1', 'split': 'test', 'sha256': 'd'*64,
                      'source_manifest_sha256': 'e'*64})
    m['resolved_inference_config'] = {k: m[k] for k in ('image_size', 'ap_confidence_floor', 'operating_confidence',
                                                      'nms_iou', 'nms_mode', 'max_detections', 'seed')}
    return m


def prediction(id='p', c=0, confidence=0.9, box=None):
    return dict(id=id, image_id='image', class_id=c, confidence=confidence, box=box or [0, 0, 10, 10])


def region(id='r', labels=None):
    return dict(id=id, image_id='image', labels=labels or [0], box=[0, 0, 10, 10])


class ManifestTests(unittest.TestCase):
    def test_valid_frozen_manifest(self):
        validate_manifest(manifest(), scientific=True)

    def test_every_mandatory_field_missing_rejected(self):
        for key in manifest():
            m = manifest()
            del m[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_manifest(m, scientific=True)

    def test_unfrozen_rejected(self):
        m = manifest()
        m.update(phase='pre_freeze', frozen=False)
        validate_manifest(m)
        with self.assertRaises(ValueError):
            validate_manifest(m, scientific=True)

    def test_malformed_fields(self):
        for key, value in [('checkpoint_sha256', 'TBD'), ('frozen', 'true'), ('image_size', [0, 1]),
                           ('seed', True), ('nms_mode', 'unknown'), ('matching_iou', 0),
                           ('operating_confidence', float('nan')), ('ap_ious', [0.6]), ('dataset', {})]:
            m = manifest()
            m[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_manifest(m, scientific=True)

    def test_resolved_config_disagreement(self):
        m = manifest()
        m['resolved_inference_config'] = copy.deepcopy(m['resolved_inference_config'])
        m['resolved_inference_config']['seed'] = 2
        with self.assertRaises(ValueError):
            validate_manifest(m, scientific=True)

    def test_external_requires_review(self):
        m = manifest()
        m['dataset']['identity'] = 'CODEBRIM'
        with self.assertRaises(ValueError):
            validate_manifest(m, scientific=True)
        m['external_review'] = dict(taxonomy_approved=True, leakage_audit_passed=True, evidence='synthetic')
        validate_manifest(m, scientific=True)

    def test_gate_before_checkpoint_read(self):
        with patch('detection.generalization.manifest.file_hash') as reader:
            with self.assertRaises(ValueError):
                frozen_gate({}, ROOT, {}, {})
            reader.assert_not_called()

    def test_checkpoint_mismatch(self):
        m = manifest()
        with patch('detection.generalization.manifest.subprocess.check_output', side_effect=['c'*40, '', '']), \
             patch('detection.generalization.manifest.read_json', return_value={'manifest_sha256': {'test': 'e'*64}}), \
             patch('detection.generalization.manifest.file_hash', return_value='f'*64):
            with self.assertRaisesRegex(ValueError, 'Checkpoint hash'):
                frozen_gate(m, ROOT, crosswalk(), {'synthetic': True})

    def test_full_gate_accepts_and_rejects_git_or_ontology_drift(self):
        m = manifest()
        for outputs, passes in [(['c'*40, '', ''], True), (['b'*40], False),
                                (['c'*40, ' M source.py'], False), (['c'*40, '', '?? source.py'], False)]:
            with self.subTest(outputs=outputs), \
                 patch('detection.generalization.manifest.subprocess.check_output', side_effect=outputs), \
                 patch('detection.generalization.manifest.read_json', return_value={'manifest_sha256': {'test': 'e'*64}}), \
                 patch('detection.generalization.manifest.file_hash', return_value='a'*64):
                if passes:
                    frozen_gate(m, ROOT, crosswalk(), {'synthetic': True})
                else:
                    with self.assertRaises(ValueError):
                        frozen_gate(m, ROOT, crosswalk(), {'synthetic': True})
        with self.assertRaises(ValueError):
            frozen_gate(m, ROOT, crosswalk(), {'changed': True})

    def test_cli_rejects_before_bundle_read(self):
        spec = importlib.util.spec_from_file_location('evaluate_generalization', ROOT / 'scripts/evaluate_generalization.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module, 'read_json', return_value={}) as reader, \
             patch.object(module, 'read_json_with_hash') as export_reader:
            with self.assertRaises(ValueError):
                module.run('manifest', 'NEVER_READ_PAYLOAD', 'ontology', 'protocol')
            reader.assert_called_once_with('manifest')
            export_reader.assert_not_called()

    def test_bundle_binding(self):
        m = manifest()
        b = dict(images=['image'], regions=[region()], predictions=[prediction()])
        m['dataset']['sha256'] = object_hash({k: b[k] for k in ('images', 'regions')})
        b.update(manifest_sha256=object_hash(m), dataset=m['dataset'], inference_config=m['resolved_inference_config'])
        validate_bundle(b, m)
        b['regions'] = []
        with self.assertRaises(ValueError):
            validate_bundle(b, m)

    def test_export_hash_binds_exact_bytes_parsed(self):
        import hashlib
        original = b'{"predictions": []}\n'
        changed = b'{"predictions": [{"confidence": 1}]}\n'
        with patch.object(Path, 'read_bytes', side_effect=[original, changed]) as reader:
            value, sha = read_json_with_hash('synthetic-export.json')
        self.assertEqual(value, {'predictions': []})
        self.assertEqual(sha, hashlib.sha256(original).hexdigest())
        reader.assert_called_once()

    def test_synthetic_export_pipeline(self):
        spec = importlib.util.spec_from_file_location('synthetic_evaluator', ROOT / 'scripts/evaluate_generalization.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        m = manifest()
        protocol = {k: m[k] for k in ('ap_ious', 'ap_confidence_floor', 'operating_confidence', 'matching_iou',
                                      'nms_iou', 'nms_mode', 'max_detections')}
        protocol.update(status='frozen', calibration_bins=10)
        m['protocol_sha256'] = object_hash(protocol)
        b = dict(images=['image'], regions=[region()], predictions=[prediction()])
        m['dataset']['sha256'] = object_hash({k: b[k] for k in ('images', 'regions')})
        b.update(manifest_sha256=object_hash(m), dataset=m['dataset'], inference_config=m['resolved_inference_config'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [root / name for name in ('manifest.json', 'export.json', 'ontology.json', 'protocol.json')]
            for path, value in zip(paths, (m, b, crosswalk(), protocol)):
                path.write_text(json.dumps(value), encoding='utf-8')
            # The independent full gate tests verify provenance checks. This test isolates transport/reporting.
            with patch.object(module, 'ROOT', root), patch.object(module, 'frozen_gate') as gate, \
                 patch.object(module, 'read_json_with_hash', wraps=read_json_with_hash) as export_reader:
                out = module.run(*paths)
                gate.assert_called_once()
                export_reader.assert_called_once_with(paths[1])
                evidence = json.loads((out / 'input_evidence.json').read_text())
                self.assertEqual(evidence['export_sha256'], read_json_with_hash(paths[1])[1])
                result = json.loads((out / 'results.json').read_text())
                self.assertEqual(result['summary']['mAP50'], 1)
                self.assertEqual(result['summary']['TP'], 1)
                with self.assertRaises(FileExistsError):
                    module.run(*paths)

    def test_deterministic_naming_and_overwrite(self):
        m = manifest()
        self.assertEqual(experiment_name(m), experiment_name(dict(reversed(list(m.items())))))
        with tempfile.TemporaryDirectory() as tmp:
            reserve(tmp, m)
            m['freeze_approval'] = 'changed'
            with self.assertRaises(FileExistsError):
                reserve(tmp, m)

    def test_unsafe_id_rejected(self):
        m = manifest()
        m['experiment_id'] = '../escape'
        with self.assertRaises(ValueError):
            experiment_name(m)


class ScoringTests(unittest.TestCase):
    def test_mapping_validation(self):
        c = crosswalk()
        validate_crosswalk(c)
        self.assertEqual(shared_classes(c), [0, 1, 4])
        c['mappings'][1]['external_label'] = 'Crack'
        with self.assertRaises(ValueError):
            validate_crosswalk(c)

    def test_external_only_labels_cannot_be_mapping_targets(self):
        for label in ('Efflorescence', 'Corrosion/stain'):
            for status in ('candidate', 'approved'):
                c = crosswalk()
                c['mappings'][0].update(external_label=label, status=status)
                with self.subTest(label=label, status=status), self.assertRaisesRegex(ValueError, 'External-only'):
                    validate_crosswalk(c)

    def test_unmapped_and_candidates(self):
        c = crosswalk()
        c['mappings'][0]['status'] = 'candidate'
        self.assertEqual(map_region_labels(['Crack', 'Efflorescence', 'Spallation'], c), ([1], ['Crack', 'Efflorescence']))
        with self.assertRaises(ValueError):
            map_region_labels(['invented'], c)

    def test_multilabel_classwise(self):
        gt = [region(labels=[0, 1])]
        for c in (0, 1):
            rows, fn, n = match_class([prediction(c=c)], gt, c)
            self.assertTrue(rows[0]['correct'])
            self.assertEqual((fn, n), ([], 1))
        self.assertEqual(len(gt), 1)

    def test_duplicate_is_fp_and_missing_is_fn(self):
        rows, fn, n = match_class([prediction('p1'), prediction('p2', confidence=0.8)], [region(), region('r2')], 0)
        # Two distinct annotated regions can each match once.
        self.assertEqual(sum(r['correct'] for r in rows), 2)
        rows, fn, n = match_class([prediction('p1'), prediction('p2')], [region()], 0)
        self.assertEqual([r['correct'] for r in rows], [True, False])
        self.assertEqual(match_class([], [region()], 0)[1], ['r'])

    def test_counts(self):
        r = counts(2, 1, 2, 2)
        self.assertAlmostEqual(r['precision'], 2/3)
        self.assertEqual(r['recall'], 0.5)
        self.assertAlmostEqual(r['F1'], 4/7)
        self.assertEqual((r['FP_per_image'], r['FN_per_image']), (0.5, 1))
        self.assertEqual(counts(0, 0, 0, 1)['F1'], 0)

    def test_known_ap_and_empty_gt(self):
        self.assertEqual(average_precision([{'correct': False}, {'correct': True}], 1), 0.5)
        self.assertEqual(average_precision([], 1), 0)
        self.assertIsNone(average_precision([], 0))

    def test_iou_localization_and_wrong_class(self):
        self.assertFalse(match_class([prediction(box=[20, 20, 30, 30])], [region()], 0)[0][0]['correct'])
        self.assertEqual(match_class([prediction(c=1)], [region()], 0)[1], ['r'])

    def test_operating_point_distinct_from_ap_floor(self):
        r = evaluate(['image', 'empty'], [prediction(confidence=0.2)], [region()], [0, 1],
                     ap_floor=0.01, operating_confidence=0.5, matching_iou=0.5, ap_ious=AP_IOUS)
        self.assertEqual(r['summary']['mAP50'], 1)
        self.assertEqual(r['summary']['mAP50_95'], 1)
        self.assertEqual(r['summary']['FN_per_image'], 0.5)
        self.assertEqual(r['summary']['TP'], 0)
        self.assertEqual(len(r['confidence']), 1)
        self.assertIsNone(r['per_class'][1]['AP50'])

    def test_permutation_deterministic(self):
        p = [prediction('b'), prediction('a')]
        self.assertEqual(match_class(p, [region()], 0), match_class(list(reversed(p)), [region()], 0))

    def test_invalid_records(self):
        for p in (prediction(box=[0, 0, -1, 1]), prediction(confidence=float('nan'))):
            with self.assertRaises(ValueError):
                validate_records(['image'], [p], [region()])
        with self.assertRaises(ValueError):
            validate_records(['unknown'], [prediction()], [])

    def test_calibration_edges(self):
        r = reliability([dict(confidence=0., correct=False), dict(confidence=1., correct=True),
                         dict(confidence=0.5, correct=False)], 2)
        self.assertEqual([b['count'] for b in r['bins']], [1, 2])
        self.assertAlmostEqual(r['ECE'], 1/6)
        self.assertIsNone(reliability([])['ECE'])
        self.assertIsNone(reliability([], 2)['bins'][0]['accuracy'])

    def test_failure_serialization(self):
        r = failure_record('image', 'p', ['FP_TEXTURE', 'ERR_DUPLICATE_DETECTION'], 'synthetic')
        self.assertEqual(json.loads(json.dumps(r)), r)
        self.assertEqual(len(FailureCategory), 21)
        self.assertEqual(sum(c['count'] for c in category_counts([r])), 2)
        with self.assertRaises(ValueError):
            failure_record('image', 'p', ['MADE_UP'], 'synthetic')

    def test_tables_and_report(self):
        result = evaluate(['image'], [prediction()], [region()], [0], ap_floor=0, operating_confidence=0.5,
                          matching_iou=0.5, ap_ious=[0.5])
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write_report(folder, manifest(), result)
            self.assertTrue(all((folder / (name + '.csv')).exists() for name in TABLES))
            self.assertEqual(json.loads((folder / 'status.json').read_text())['status'], 'COMPLETE')
            with self.assertRaises(FileExistsError):
                write_tables(folder, {})

    def test_synthetic_plots(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from detection.generalization.plots import confidence_plot, reliability_plot
        cal = reliability([dict(confidence=0.8, correct=True), dict(confidence=0.6, correct=False)])
        with tempfile.TemporaryDirectory() as tmp:
            for index, plot in enumerate((confidence_plot, reliability_plot)):
                fig = plot(cal)
                path = Path(tmp) / f'{index}.png'
                fig.savefig(path)
                plt.close(fig)
                self.assertGreater(path.stat().st_size, 100)


if __name__ == '__main__':
    unittest.main()
