"""Synthetic freeze checks: deny split substitution and test-derived thresholds."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get('DET_FREEZE_PACKAGE_ROOT', Path(__file__).resolve().parents[2]))
spec = importlib.util.spec_from_file_location('det_final_freeze', ROOT/'scripts/analysis/verify_det_final_v1.py')
freeze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze)


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.m = freeze.read_json(ROOT/freeze.MANIFEST)

    def test_manifest_and_external_receipt(self):
        freeze.validate_manifest(self.m)
        self.assertEqual((ROOT/freeze.RECEIPT).read_text().split(),
                         [freeze.sha256(ROOT/freeze.MANIFEST), freeze.MANIFEST])

    def test_candidate_and_ontology_drift_rejected(self):
        changes = [('checkpoint_path', 'elsewhere.pt'), ('checkpoint_sha256', '0'*64), ('best_epoch', 92),
                   ('training_git_sha', '0'*40), ('input_size', 800), ('class_mapping', {'0':'Seepage'})]
        for key,value in changes:
            m = deepcopy(self.m); m[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                freeze.validate_manifest(m)

    def test_access_flags_and_deferred_status_fail_closed(self):
        for key in ('test_accessed', 'codebrim_accessed'):
            for value in (True, 'false', 0):
                m = deepcopy(self.m); m[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    freeze.validate_manifest(m)
        m = deepcopy(self.m); m['det_improved_status']['training_executed'] = True
        with self.assertRaises(ValueError):
            freeze.validate_manifest(m)

    def test_evaluation_and_threshold_drift_rejected(self):
        for key,value in (('imgsz',800), ('batch',4), ('quantize','bf16'), ('conf',.25), ('iou',.45), ('nms',True), ('augment',True)):
            m = deepcopy(self.m); m['evaluation_config'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                freeze.validate_manifest(m)
        m = deepcopy(self.m); m['threshold_policy']['heldout_threshold_optimization'] = True
        with self.assertRaises(ValueError):
            freeze.validate_manifest(m)

    def test_substitution_rejected_before_any_file_is_opened(self):
        with patch.object(freeze, 'read_json', side_effect=AssertionError('Unexpected file access')):
            for split,path in [('test',freeze.DATA), ('val','data/processed/gyu_det_v3_baseline_v1/splits/test.txt'),
                               ('val','data/raw/codebrim/data.yaml')]:
                with self.subTest(split=split, path=path), self.assertRaises(ValueError):
                    freeze.validate_development_request(self.m, ROOT, split, path)

    def test_dataset_yaml_cannot_hide_test_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = {'path':str(root), 'train':str(root/'outputs/training/defect_detection/DET-BASELINE/train.txt'),
                    'val':str(root/'data/processed/gyu_det_v3_baseline_v1/splits/test.txt'),
                    'nc':6, 'channels':3, 'names':self.m['class_mapping']}
            p = root/freeze.DATA; p.parent.mkdir(parents=True); p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'split path'):
                freeze.validate_development_request(self.m, root)
            data['test'] = 'sentinel-never-opened'
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'dataset keys'):
                freeze.validate_development_request(self.m, root)

    def test_reference_paths_deny_raw_test_and_escape(self):
        for value in ('../outside.json', 'data/raw/gyu_det/a.jpg', 'data/manifests/gyu_det_v3_baseline_v1/test.csv',
                      'data/processed/gyu_det_v3_baseline_v1/splits/test.txt', 'outputs/codebrim/evidence.json', 'C:/outside.json'):
            with self.subTest(path=value), self.assertRaises(ValueError):
                freeze.safe_reference(ROOT, value)

    def test_fixed_diagnostic_never_uses_another_split_optimum(self):
        p, r = [[0.0]*1000 for _ in range(2)], [[0.0]*1000 for _ in range(2)]
        for i in range(2):
            p[i][800] = r[i][800] = 1.0  # tempting test-derived optimum
        p[0][186],r[0][186],p[1][186],r[1][186] = .2,.4,.6,.8
        result = freeze.fixed_diagnostic_pr(p,r,[0,5])
        self.assertEqual(result['grid_index'],186)
        self.assertAlmostEqual(result['precision'],.4)
        self.assertAlmostEqual(result['recall'],.6)
        self.assertFalse(result['threshold_optimized'])
        with self.assertRaises(ValueError):
            freeze.fixed_diagnostic_pr(p,r,[0,0])


if __name__ == '__main__':
    unittest.main()
