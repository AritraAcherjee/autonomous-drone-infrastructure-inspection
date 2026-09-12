"""Synthetic correctness and full-output reproducibility checks for EDA."""
from __future__ import annotations
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from data.validators.gyu_eda import (BASELINE, RAW, annotation_bin, baseline_samples,
    box_metrics, cooccurrence, load_inventory, run_eda, tables, write_csv)
from data.validators.gyu_orphan_review import Box

CLASSES = ['Crack', 'Breakage', 'Comb', 'Hole', 'Reinforcement', 'Seepage']


def sample(split: str, ids: list[int], paired: bool = True) -> dict:
    return dict(split=split, image_filename=split+'.jpg', pairing_status='exact_pair' if paired else 'image_without_label',
                width=200, height=100, megapixels=.02, image_aspect_ratio=2, orientation='landscape',
                annotation_count=len(ids) if paired else None, classes=sorted(set(ids)))


def fixture(root: Path) -> dict:
    raw = root/'data/raw'
    validation = root/'validation'
    raw.mkdir(parents=True)
    validation.mkdir()
    (root/'scripts/data').mkdir(parents=True)
    (root/'scripts/data/eda_gyu_det.py').write_text('fixture CLI', encoding='utf-8')
    classes_path = raw/'classes.txt'
    classes_path.write_text('\n'.join(CLASSES), encoding='utf-8')
    manifest, labels, verified = [], [], []
    for split in ('train', 'valid', 'test'):
        content = '\n'.join(f'{cid} .5 .5 .2 .1' for cid in range(6))
        path = raw/(split+'.txt')
        path.write_text(content, encoding='utf-8')
        labels.append(dict(split=split, label_filename=path.name, label_relative_path=path.relative_to(root).as_posix(),
                           label_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), annotation_count=6,
                           validation_status='valid', pairing_status='exact_pair'))
        manifest.append(dict(split=split, image_filename=split+'.jpg', width=200, height=100,
                             image_sha256='cached', label_filename=path.name, annotation_count=6, pairing_status='exact_pair'))
        verified.append(dict(**manifest[-1], primary_decode_success=True))
    path = raw/'orphan.txt'
    path.write_text('0 .5 .5 .1 .1', encoding='utf-8')
    labels.append(dict(split='train', label_filename=path.name, label_relative_path=path.relative_to(root).as_posix(),
                       label_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), annotation_count=1,
                       validation_status='valid', pairing_status='orphan_label'))
    manifest.append(dict(split='train', image_filename='unlabeled.jpg', width=50, height=100,
                         image_sha256='cached2', label_filename='', annotation_count='', pairing_status='image_without_label'))
    verified.append(dict(**manifest[-1], primary_decode_success=True))
    write_csv(root/'manifest.csv', manifest)
    write_csv(validation/'label_validation.csv', labels)
    write_csv(validation/'image_validation.csv', verified)
    (validation/'validation.json').write_text(json.dumps({'summary': {}}))
    write_csv(root/'triage.csv', [dict(split='train', label_filename='orphan.txt', outcome='UNRESOLVED_HOLD', repair_authorized=False)])
    write_csv(root/'leakage.csv', [dict(review_authorized=True, human_outcome='REJECT_LEAKAGE_CANDIDATE')])
    (root/'policy.md').write_text('Analysis only')
    return dict(repository=root, manifest=root/'manifest.csv', validation=validation, triage=root/'triage.csv',
                leakage=root/'leakage.csv', policy=root/'policy.md', classes_path=classes_path, output=root/'outputs/eda/test')


class EdaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.samples = [sample('train', [0, 0, 1]), sample('valid', [1]), sample('test', [], False)]
        self.boxes = [dict(split=s['split'], image_filename=s['image_filename'], label_filename='a.txt', annotation_index=i+1,
                           class_id=cid, class_name=CLASSES[cid], **box_metrics(Box(cid, .5, .5, .2, .1), 200, 100))
                      for s, ids in zip(self.samples, [[0, 0, 1], [1], []]) for i, cid in enumerate(ids)]

    def test_class_counting_and_orphan_separation(self) -> None:
        result = tables(CLASSES, self.samples, self.boxes, [{'split': 'train', 'class_id': 0}], Counter(train=1))
        crack = result['class_distribution'][0]
        self.assertEqual(crack['exact_pair_annotation_instances'], 2)
        self.assertEqual(crack['exact_pair_images_containing_class'], 1)
        self.assertEqual(crack['orphan_annotation_instances'], 1)
        self.assertEqual(crack['percent_exact_pair_images'], 50)
        raw = next(r for r in result['dataset_overview'] if r['view'] == RAW and r['split'] == 'all')
        baseline = next(r for r in result['dataset_overview'] if r['view'] == BASELINE and r['split'] == 'all')
        self.assertEqual((raw['annotation_instances'], baseline['annotation_instances']), (5, 4))

    def test_box_calculation_non_square_image(self) -> None:
        b = box_metrics(Box(0, .5, .5, .2, .1), 200, 100)
        self.assertAlmostEqual(b['normalized_area'], .02)
        self.assertAlmostEqual(b['pixel_area'], 400)
        self.assertEqual((b['pixel_width'], b['pixel_height'], b['aspect_ratio']), (40, 10, 4))

    def test_size_boundary_rules(self) -> None:
        for area, category in [(.0009, 'tiny'), (.001, 'small'), (.01, 'medium'), (.1, 'large')]:
            self.assertEqual(box_metrics(Box(0, .5, .5, 1, area), 100, 100)['size_category'], category)

    def test_annotation_count_bin_boundaries(self) -> None:
        self.assertEqual([annotation_bin(n) for n in [0, 1, 2, 5, 6, 10, 11, 20, 21]],
                         ['0_explicit_empty_label', '1', '2-5', '2-5', '6-10', '6-10', '11-20', '11-20', '>20'])
        with self.assertRaises(ValueError):
            annotation_bin(-1)

    def test_cooccurrence_counts_images_not_instances(self) -> None:
        matrix = cooccurrence(self.samples, 6)
        self.assertEqual(matrix[0][:2], [1, 1])
        self.assertEqual(matrix[1][:2], [1, 2])

    def test_split_aggregation(self) -> None:
        result = tables(CLASSES, self.samples, self.boxes, [], Counter())
        self.assertEqual([r['annotation_instances'] for r in result['split_comparison']], [3, 1, 0])
        self.assertEqual(sum(r['exact_pair_annotation_instances'] for r in result['class_distribution_by_split']), 4)

    def test_baseline_filter_never_assigns_unlabeled_zero(self) -> None:
        self.assertEqual(len(baseline_samples(self.samples)), 2)
        self.assertIsNone(self.samples[-1]['annotation_count'])
        result = tables(CLASSES, self.samples, self.boxes, [], Counter())
        self.assertEqual(sum(r['exact_pair_images'] for r in result['annotation_count_distribution']
                             if r['annotation_bin'] == '0_explicit_empty_label'), 0)

    def test_border_rounding_and_extreme_aspect(self) -> None:
        b = box_metrics(Box(0, .1-1e-7, .5, .2, .001), 100, 100)
        self.assertTrue(b['near_border'])
        self.assertTrue(b['rounding_warning'])
        self.assertTrue(b['extreme_aspect_ratio'])

    def test_changed_label_fails_before_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder))
            (Path(folder)/'data/raw/train.txt').write_text('0 .5 .5 .2 .2')
            with self.assertRaisesRegex(ValueError, 'changed since validation'):
                load_inventory(args['repository'], args['manifest'], args['validation'], args['classes_path'])

    def test_no_image_decode_and_deterministic_outputs(self) -> None:
        # No actual image files exist in this fixture: loading must reuse validated metadata.
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder))
            first = run_eda(**args)
            before = {p.relative_to(args['output']): p.read_bytes() for p in args['output'].rglob('*') if p.is_file()}
            second = run_eda(**args)
            after = {p.relative_to(args['output']): p.read_bytes() for p in args['output'].rglob('*') if p.is_file()}
            self.assertEqual(first, second)
            self.assertEqual(before, after)
            self.assertEqual(first['exact_pair_images'], 3)
            self.assertEqual(first['exact_pair_annotation_instances'], 18)
            self.assertEqual(len(list((args['output']/'figures').glob('*.png'))), 9)

    def test_output_guard(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            args = fixture(Path(folder))
            args['output'] = Path(folder)/'data/raw'
            with self.assertRaisesRegex(ValueError, 'subdirectory'):
                run_eda(**args)


if __name__ == '__main__':
    unittest.main()
