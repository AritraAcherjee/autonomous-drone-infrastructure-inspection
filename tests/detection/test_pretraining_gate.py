"""Reader safety, closed metadata contract and fail-closed reporting."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from detection.data.raw_guard import canonical, compare, inside, mutable_path, readonly_raw, snapshot
from detection.data.readonly_verifier import CLASSES, decode, load_approved, verify_label
from detection.pretraining_gate import SECTIONS, aggregate, finalize_report, write_json
from data.validators.gyu_baseline_v1 import EXPECTED_COUNTS, resolve_label, resolve_list_entry

ROOT = Path(__file__).resolve().parents[2]


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / 'data/raw'
        self.raw.mkdir(parents=True)

    def test_raw_and_descendants_rejected(self):
        for path in (self.raw, self.raw / 'a.cache', self.raw / 'images/a.npy'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                mutable_path(path, self.raw)

    def test_audit_guard_blocks_write_remove_and_rename(self):
        path = self.raw / 'original.txt'
        path.write_text('unchanged')
        with readonly_raw(self.raw):
            self.assertEqual(path.read_text(), 'unchanged')
            for action in (lambda: path.write_text('bad'), lambda: path.unlink(),
                           lambda: path.rename(self.root / 'moved')):
                with self.assertRaises(ValueError):
                    action()
        self.assertEqual(path.read_text(), 'unchanged')

    def test_parent_traversal_rejected(self):
        with self.assertRaises(ValueError):
            mutable_path(self.root / 'outputs/../data/raw/a.cache', self.raw)

    def test_similar_prefix_not_child(self):
        self.assertFalse(inside(self.root / 'data/raw-other/a.cache', self.raw))

    def test_controlled_cache_accepted(self):
        self.assertEqual(mutable_path(self.root / 'outputs/cache/ultralytics/x', self.raw),
                         (self.root / 'outputs/cache/ultralytics/x').resolve())

    def test_windows_case_and_separator(self):
        if os.name != 'nt':
            self.skipTest('Actual Windows path semantics')
        path = Path(str(self.raw).upper().replace('\\', '/') + '/A.CACHE')
        with self.assertRaises(ValueError):
            mutable_path(path, self.raw)

    def test_resolved_junction_target_rejected(self):
        # Resolve is the platform primitive that follows both symlinks and
        # junctions. Exercise the target comparison without requiring admin.
        with patch.object(Path, 'resolve', return_value=self.raw):
            with self.assertRaises(ValueError):
                mutable_path(self.root / 'outside-link/a.cache', self.raw)

    def test_snapshot_detects_content_even_with_same_stat(self):
        path = self.raw / 'a.txt'
        path.write_bytes(b'abc')
        before = snapshot(self.raw, {path})
        stamp = path.stat().st_mtime_ns
        path.write_bytes(b'def')
        os.utime(path, ns=(stamp, stamp))
        diff = compare(before, snapshot(self.raw, {path}))
        self.assertEqual(diff['sha256_changes'], ['a.txt'])
        self.assertEqual(diff['status'], 'FAIL')

    def test_snapshot_added_removed_cache_npy(self):
        diff = compare({'old': {'size': 1, 'mtime_ns': 1}},
                       {'new.cache': {'size': 1, 'mtime_ns': 1}, 'new.npy': {'size': 1, 'mtime_ns': 1}})
        self.assertEqual(diff['files_removed'], ['old'])
        self.assertEqual(diff['new_cache_files'], ['new.cache'])
        self.assertEqual(diff['new_npy_files'], ['new.npy'])

    def test_snapshot_size_and_timestamp(self):
        diff = compare({'a': {'size': 1, 'mtime_ns': 1}}, {'a': {'size': 2, 'mtime_ns': 2}})
        self.assertEqual(diff['size_changes'], ['a'])
        self.assertEqual(diff['mtime_ns_changes'], ['a'])

    def test_snapshot_unchanged_passes(self):
        self.assertEqual(compare({}, {})['status'], 'PASS')

    def test_evidence_serialization_rejects_raw(self):
        with self.assertRaises(ValueError):
            write_json(self.raw / 'evidence.json', {}, self.raw)

    def test_gate_json_round_trip(self):
        result = aggregate({k: {'status': 'PASS'} for k in SECTIONS})
        path = self.root / 'outputs/gate.json'
        write_json(path, result, self.raw)
        self.assertEqual(json.loads(path.read_text()), result)

    def test_runtime_pass_requires_passing_tests(self):
        sections = {k: {'status': 'PASS'} for k in SECTIONS}
        self.assertEqual(finalize_report(self.root, sections)['status'], 'FAIL')
        path = self.root / 'outputs/validation/defect_detection/pretraining_gate/test_results.json'
        write_json(path, {'status': 'FAIL'}, self.raw)
        self.assertEqual(finalize_report(self.root, sections)['status'], 'FAIL')
        write_json(path, {'status': 'PASS'}, self.raw)
        self.assertEqual(finalize_report(self.root, sections)['status'], 'PASS')


class DatasetTests(unittest.TestCase):
    def test_approved_yaml_lists_counts_and_mapping(self):
        config, records = load_approved(ROOT)
        self.assertEqual(config['names'], {str(i): n for i, n in enumerate(CLASSES)})
        self.assertEqual(config['nc'], 6)
        self.assertEqual(EXPECTED_COUNTS, {'train': 8305, 'valid': 1040, 'test': 1053})
        self.assertEqual(len(records), 10398)

    def test_changed_mapping_rejected(self):
        import yaml
        with patch.object(yaml, 'safe_load', return_value={'nc': 7, 'names': {}}):
            with self.assertRaisesRegex(ValueError, 'YAML'):
                load_approved(ROOT)

    def test_wrong_split_count_rejected(self):
        with patch('detection.data.readonly_verifier.EXPECTED_COUNTS', {'train': 8304}):
            with self.assertRaisesRegex(ValueError, '8304'):
                load_approved(ROOT)

    def test_duplicate_list_entry_rejected(self):
        from detection.data import readonly_verifier as verifier
        original = verifier.resolve_list_entry
        first = []
        def duplicate(path, line):
            if not first:
                first.append(original(path, line))
            return first[0]
        with patch.object(verifier, 'resolve_list_entry', side_effect=duplicate):
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                load_approved(ROOT)

    def test_list_local_path_resolution(self):
        path = ROOT / 'data/processed/gyu_det_v3_baseline_v1/splits/train.txt'
        self.assertEqual(resolve_list_entry(path, './../../../raw/a.jpg'), (ROOT / 'data/raw/a.jpg').resolve())

    def test_label_last_images_segment(self):
        image = ROOT / 'images/fixture/images/A.JPG'
        self.assertEqual(resolve_label(image), ROOT / 'images/fixture/labels/A.txt')

    def verify(self, text, ids='[0]', count=1):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'a.txt'
            if text is not None:
                path.write_text(text)
            return verify_label(dict(label=path, split='train', image_relative_path='a.jpg',
                label_relative_path='a.txt', annotation_count=str(count), class_ids=ids))

    def test_missing_label_fails(self):
        self.assertFalse(self.verify(None)['success'])

    def test_class_ids_invalid(self):
        for cid in ('6', '-1', '0.5', 'nan', '0.0'):
            with self.subTest(cid=cid):
                self.assertFalse(self.verify(f'{cid} .5 .5 .2 .2')['success'])

    def test_all_six_ids_unchanged(self):
        text = '\n'.join(f'{cid} .5 .5 .2 .2' for cid in range(6))
        self.assertTrue(self.verify(text, '[0, 1, 2, 3, 4, 5]', 6)['success'])

    def test_approved_boundary_warning_retained(self):
        result = self.verify('0 0.1 0.5 0.200001 0.2')
        self.assertTrue(result['success'])
        self.assertTrue(result['warnings'])

    def test_genuine_boundary_error_fails(self):
        self.assertFalse(self.verify('0 0.1 0.5 0.201 0.2')['success'])

    def test_malformed_row_fails(self):
        self.assertFalse(self.verify('0 .5 .5 .2')['success'])

    def test_manifest_annotation_mismatch_fails(self):
        self.assertFalse(self.verify('0 .5 .5 .2 .2', count=2)['success'])

    def test_decode_none_and_exception_fail(self):
        self.assertFalse(decode(Path('missing'), lambda p: None, 'test')['decode_success'])
        def broken(p):
            raise OSError('broken image')
        self.assertIn('broken image', decode(Path('x'), broken, 'test')['error'])

    def test_decode_color_shape(self):
        import numpy as np
        result = decode(Path('x'), lambda p: np.zeros((12, 20, 3), dtype=np.uint8), 'test')
        self.assertTrue(result['decode_success'])
        self.assertEqual((result['width'], result['height'], result['channels']), (20, 12, 3))


class AggregationTests(unittest.TestCase):
    def test_each_required_section_can_fail_gate(self):
        for section in SECTIONS:
            sections = {k: {'status': 'PASS'} for k in SECTIONS}
            sections[section]['status'] = 'FAIL'
            with self.subTest(section=section):
                self.assertEqual(aggregate(sections)['status'], 'FAIL')

    def test_missing_section_fails(self):
        self.assertEqual(aggregate({})['status'], 'FAIL')

    def test_execution_error_fails(self):
        sections = {k: {'status': 'PASS'} for k in SECTIONS}
        sections['execution_error'] = 'read interrupted'
        self.assertEqual(aggregate(sections)['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()
