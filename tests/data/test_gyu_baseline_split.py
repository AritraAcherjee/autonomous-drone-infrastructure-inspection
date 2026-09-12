"""Synthetic tests for annotation consistency and dry-run grouping policy."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from data.validators.gyu_baseline_split import (annotation_consistency, assert_leakage_safe,
    canonical_annotations, connected_groups, csv_write, normalized_rows, proposal, representative)

A = '0 .5 .5 .2 .1\n1 .4 .3 .1 .2'
B = '1 .4 .3 .1 .2\n0 .5 .5 .2 .1'
C = '0 .5 .5 .3 .1\n1 .4 .3 .1 .2'


def record(split: str, name: str, labeled: bool = True, sha: str | None = None) -> tuple[str, dict]:
    path = f'data/raw/{split}/{name}'
    return path, dict(raw_split=split, pairing_status='exact_pair' if labeled else 'image_without_label',
        baseline_eligible=labeled, exclusion_reason='' if labeled else 'UNLABELED_UNCLASSIFIED',
        label_relative_path=f'data/raw/{split}/{Path(name).stem}.txt' if labeled else '',
        image_sha256=sha or path, annotation_count=2 if labeled else None, class_ids='[0, 1]' if labeled else '[]',
        width=100, height=200, mpo_warning=False, boundary_rounding_warning_count=0)


def decision(a: tuple[str, str], b: tuple[str, str], outcome: str) -> dict:
    return dict(split_a=a[0], image_a=a[1], split_b=b[0], image_b=b[1],
                human_outcome=outcome, review_authorized='true')


class BaselineSplitTests(unittest.TestCase):
    def test_identical_annotations(self) -> None:
        self.assertEqual(annotation_consistency([A, A]), 'IDENTICAL_ANNOTATIONS')

    def test_reordered_equivalence(self) -> None:
        self.assertEqual(annotation_consistency([A, B]), 'REORDERED_EQUIVALENT_ANNOTATIONS')

    def test_numeric_spelling_and_fingerprint(self) -> None:
        other = '0.0 0.500 0.5 2e-1 0.10\n1 0.4 0.3 .1 .2'
        self.assertEqual(annotation_consistency([A, other]), 'IDENTICAL_ANNOTATIONS')
        self.assertEqual(canonical_annotations(normalized_rows(A)), canonical_annotations(normalized_rows(other)))

    def test_conflicting_boxes_and_class_ids(self) -> None:
        self.assertEqual(annotation_consistency([A, C]), 'CONFLICTING_ANNOTATIONS')
        self.assertEqual(annotation_consistency([A, A.replace('0 .5', '2 .5')]), 'CONFLICTING_ANNOTATIONS')
        self.assertEqual(annotation_consistency([A, A+'\n0 .5 .5 .2 .1']), 'CONFLICTING_ANNOTATIONS')

    def test_annotation_availability(self) -> None:
        self.assertEqual(annotation_consistency([None, None]), 'NO_LABELS')
        self.assertEqual(annotation_consistency([None, A]), 'ONLY_ONE_LABELED_COPY')
        self.assertEqual(annotation_consistency(['', '']), 'IDENTICAL_ANNOTATIONS')

    def test_cross_split_duplicate_retains_evaluation(self) -> None:
        records = dict([record('train', 'a.jpg', sha='same'), record('valid', 'b.jpg', sha='same')])
        paths = list(records)
        rows, checks, _ = proposal(records, {'e1': paths}, {p: A for p in paths}, [])
        kept = [r for r in rows if r['proposed_included']]
        self.assertEqual([r['raw_split'] for r in kept], ['valid'])
        self.assertEqual(checks[0]['representative_image'], paths[1])
        assert_leakage_safe(rows, set())

    def test_within_split_deterministic_representative(self) -> None:
        records = dict([record('train', '20.JPG'), record('train', '100.jpg')])
        paths = list(records)
        rows, _, _ = proposal(records, {'e1': paths}, {p: A for p in paths}, [])
        self.assertEqual([Path(r['image_relative_path']).name for r in rows if r['proposed_included']], ['100.jpg'])

    def test_conflict_holds_both_without_selection(self) -> None:
        records = dict([record('train', 'a.jpg'), record('valid', 'b.jpg')])
        paths = list(records)
        rows, checks, _ = proposal(records, {'e1': paths}, dict(zip(paths, [A, C])), [])
        self.assertFalse(any(r['proposed_included'] for r in rows))
        self.assertEqual(checks[0]['representative_image'], '')
        self.assertTrue(checks[0]['blocker'])
        self.assertTrue(all(r['baseline_eligible'] for r in rows))

    def test_high_confidence_group_enforcement(self) -> None:
        records = dict([record('train', 'a.jpg'), record('valid', 'b.jpg')])
        d = decision(('train', 'a.jpg'), ('valid', 'b.jpg'), 'HIGH_CONFIDENCE_NEAR_DUPLICATE_LEAKAGE')
        rows, _, handling = proposal(records, {}, {p: A for p in records}, [d])
        self.assertEqual([r['raw_split'] for r in rows if r['proposed_included']], ['valid'])
        self.assertTrue(handling[0]['conflict_after_eligibility_filtering'])
        self.assertFalse(handling[0]['conflict_after_proposal'])

    def test_unresolved_group_enforcement_preserves_outcome(self) -> None:
        records = dict([record('train', 'a.jpg'), record('test', 'b.jpg')])
        d = decision(('train', 'a.jpg'), ('test', 'b.jpg'), 'UNRESOLVED_POSSIBLE_SAME_SCENE')
        rows, _, handling = proposal(records, {}, {p: A for p in records}, [d])
        self.assertEqual([r['raw_split'] for r in rows if r['proposed_included']], ['test'])
        self.assertEqual(handling[0]['human_outcome'], 'UNRESOLVED_POSSIBLE_SAME_SCENE')

    def test_unlabeled_member_never_receives_label(self) -> None:
        records = dict([record('train', 'a.jpg'), record('valid', 'b.jpg', False)])
        d = decision(('train', 'a.jpg'), ('valid', 'b.jpg'), 'HIGH_CONFIDENCE_NEAR_DUPLICATE_LEAKAGE')
        rows, _, handling = proposal(records, {}, {p: A if r['baseline_eligible'] else None for p, r in records.items()}, [d])
        self.assertEqual([r['raw_split'] for r in rows if r['proposed_included']], ['train'])
        excluded = next(r for r in rows if not r['proposed_included'])
        self.assertIsNone(excluded['annotation_count'])
        self.assertEqual(excluded['label_relative_path'], '')
        self.assertFalse(handling[0]['conflict_after_eligibility_filtering'])

    def test_orphan_exclusion_assertion(self) -> None:
        records = dict([record('train', 'a.jpg')])
        rows, _, _ = proposal(records, {}, {p: A for p in records}, [])
        with self.assertRaisesRegex(ValueError, 'orphan'):
            assert_leakage_safe(rows, {rows[0]['label_relative_path']})

    def test_leakage_assertion_failure(self) -> None:
        records = dict([record('train', 'a.jpg', sha='same'), record('valid', 'b.jpg', sha='same')])
        rows, _, _ = proposal(records, {}, {p: A for p in records}, [])
        with self.assertRaisesRegex(ValueError, 'image_sha256'):
            assert_leakage_safe(rows, set())
        rows[1]['image_sha256'] = 'different'
        for row in rows:
            row['leakage_group_id'] = 'group'
        with self.assertRaisesRegex(ValueError, 'leakage_group_id'):
            assert_leakage_safe(rows, set())

    def test_transitive_group_through_ineligible_member(self) -> None:
        records = dict([record('train', 'a.jpg'), record('valid', 'b.jpg', False), record('test', 'c.jpg')])
        decisions = [decision(('train', 'a.jpg'), ('valid', 'b.jpg'), 'HIGH_CONFIDENCE_NEAR_DUPLICATE_LEAKAGE'),
                     decision(('valid', 'b.jpg'), ('test', 'c.jpg'), 'UNRESOLVED_POSSIBLE_SAME_SCENE')]
        rows, _, _ = proposal(records, {}, {p: A if r['baseline_eligible'] else None for p, r in records.items()}, decisions)
        self.assertEqual([r['raw_split'] for r in rows if r['proposed_included']], ['test'])

    def test_rejected_edges_do_not_group(self) -> None:
        records = dict([record('train', 'a.jpg'), record('valid', 'b.jpg')])
        d = decision(('train', 'a.jpg'), ('valid', 'b.jpg'), 'REJECT_LEAKAGE_CANDIDATE')
        rows, _, _ = proposal(records, {}, {p: A for p in records}, [d])
        self.assertTrue(all(r['proposed_included'] for r in rows))

    def test_deterministic_split_generation_and_csv(self) -> None:
        records = dict([record('train', 'b.jpg'), record('train', 'a.jpg'), record('test', 'c.jpg')])
        paths = list(records)
        first = proposal(records, {'exact': paths[:2]}, {p: A for p in records}, [])
        second = proposal(dict(reversed(list(records.items()))), {'exact': list(reversed(paths[:2]))}, {p: A for p in records}, [])
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder)/'a.csv', Path(folder)/'b.csv'
            csv_write(a, first[0])
            csv_write(b, second[0])
            self.assertEqual(a.read_bytes(), b.read_bytes())


if __name__ == '__main__':
    unittest.main()
