"""Approved membership, portable list/YAML paths and exclusion regressions."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from data.validators.gyu_baseline_v1 import (CONFLICTS, DISPLAY, EXPECTED_COUNTS, LIST_DIR, YAML_PATH,
    image_list_entry, resolve_label, resolve_list_entry, validate_approved, verify_lists, yaml_data)
from data.validators.gyu_baseline_split import csv_write


def row(split: str = 'train', name: str = '1.JPG', sha: str = 'sha') -> dict:
    return dict(raw_split=split, processed_split=split, proposed_included=True, baseline_eligible=True,
        image_relative_path=f'data/raw/gyu_det/v3/extracted/{split}/{split}/images/{name}',
        label_relative_path=f'data/raw/gyu_det/v3/extracted/{split}/{split}/labels/{Path(name).stem}.txt',
        pairing_status='exact_pair', image_sha256=sha, leakage_group_id='', exclusion_reason='')


class BaselineV1Tests(unittest.TestCase):
    def test_approved_conflicting_group_exclusion(self) -> None:
        self.assertEqual(len(CONFLICTS), 10)
        for split, filename in sorted(CONFLICTS):
            r = row(split, filename)
            expected = {s: int(s == split) for s in EXPECTED_COUNTS}
            with self.assertRaisesRegex(ValueError, 'approved exclusion'):
                validate_approved([r], set(), expected)

    def test_final_counts_are_fixed(self) -> None:
        self.assertEqual(EXPECTED_COUNTS, {'train': 8305, 'valid': 1040, 'test': 1053})
        self.assertEqual(sum(EXPECTED_COUNTS.values()), 10398)
        with self.assertRaisesRegex(ValueError, 'counts differ'):
            validate_approved([row()], set())

    def test_list_generation_is_portable(self) -> None:
        r = row()
        entry = image_list_entry(r['image_relative_path'])
        self.assertEqual(entry, './../../../raw/gyu_det/v3/extracted/train/train/images/1.JPG')
        for name in ('repo with spaces', 'other-repository'):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)/name
                self.assertEqual(resolve_list_entry(root/LIST_DIR/'train.txt', entry), (root/r['image_relative_path']).resolve())

    def test_label_resolution_case_and_last_images_segment(self) -> None:
        path = Path('parent/images/dataset/train/images/5774.JPG').resolve()
        self.assertEqual(resolve_label(path), Path('parent/images/dataset/train/labels/5774.txt').resolve())
        with self.assertRaises(ValueError):
            resolve_label(Path('no_image_directory.jpg'))

    def test_sha_leakage_assertion(self) -> None:
        with self.assertRaisesRegex(ValueError, 'image_sha256'):
            validate_approved([row(), row('valid')], set(), {'train': 1, 'valid': 1, 'test': 0})

    def test_same_scene_assertion(self) -> None:
        rows = [row(), row('valid', sha='different')]
        for r in rows:
            r['leakage_group_id'] = 'approved-scene'
        with self.assertRaisesRegex(ValueError, 'leakage_group_id'):
            validate_approved(rows, set(), {'train': 1, 'valid': 1, 'test': 0})

    def test_orphan_exclusion(self) -> None:
        r = row()
        with self.assertRaisesRegex(ValueError, 'orphan'):
            validate_approved([r], {r['label_relative_path']}, {'train': 1, 'valid': 0, 'test': 0})

    def test_unlabeled_exclusion(self) -> None:
        r = row()
        r.update(baseline_eligible=False, pairing_status='image_without_label', label_relative_path='')
        with self.assertRaisesRegex(ValueError, 'unlabeled'):
            validate_approved([r], set(), {'train': 1, 'valid': 0, 'test': 0})

    def test_manifest_yaml_and_real_label_path_consistency(self) -> None:
        r = row()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for field in ('image_relative_path', 'label_relative_path'):
                path = root/r[field]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            lists = dict(train=image_list_entry(r['image_relative_path'])+'\n', valid='', test='')
            self.assertEqual(verify_lists(root, [r], lists), 1)
            config = json.loads(json.dumps(yaml_data()))
            self.assertEqual(config['names'], {str(i): name for i, name in enumerate(DISPLAY)})
            self.assertNotIn('path', config)
            self.assertEqual((root/YAML_PATH.parent/config['val']).resolve(), (root/LIST_DIR/'valid.txt').resolve())
            (root/r['label_relative_path']).unlink()
            with self.assertRaisesRegex(ValueError, 'missing'):
                verify_lists(root, [r], lists)

    def test_deterministic_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder)/name for name in ('first', 'second')]
            for p in paths:
                p.mkdir()
                csv_write(p/'train.csv', [row()])
                (p/'train.txt').write_text(image_list_entry(row()['image_relative_path'])+'\n', encoding='utf-8')
                (p/'data.yaml').write_text(json.dumps(yaml_data(), indent=2)+'\n', encoding='utf-8')
            for name in ('train.csv', 'train.txt', 'data.yaml'):
                self.assertEqual((paths[0]/name).read_bytes(), (paths[1]/name).read_bytes())


if __name__ == '__main__':
    unittest.main()
