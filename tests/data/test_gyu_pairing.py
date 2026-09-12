"""Synthetic pairing tests; no real raw data is written by these tests."""

from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "src"))

from data.validators.gyu_pairing import SPLITS, audit, edit_distance, pairing_key, write_outputs


class PairingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "extracted"
        for split in SPLITS:
            for kind in ("images", "labels"):
                (self.root / split / split / kind).mkdir(parents=True)

    def put(self, split: str, kind: str, name: str, content: str = "fixture") -> Path:
        path = self.root / split / split / kind / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_exact_jpg_txt_and_5774_regression(self) -> None:
        self.put("train", "images", "5774.JPG")
        self.put("train", "labels", "5774.txt", "0 0.5 0.5 0.2 0.2\n")
        result = audit(self.root)
        self.assertEqual(result["pairing_summary"][0]["exact_matched_pairs"], 1)
        self.assertEqual(result["regression_5774"][0]["image_filename"], "5774.JPG")
        self.assertEqual(result["unmatched_images"], [])
        self.assertEqual(result["unmatched_labels"], [])

    def test_case_insensitive_extensions_stems_and_whitespace(self) -> None:
        self.put("valid", "images", " AbC .jPg")
        self.put("valid", "labels", "abc.TxT")
        self.put("valid", "labels", "ignored.json")
        result = audit(self.root)
        self.assertEqual(result["pairing_summary"][1]["exact_matched_pairs"], 1)
        self.assertEqual(result["matched_pairs"][0]["image_filename"], " AbC .jPg")
        self.assertEqual(pairing_key("  5774.JPG  "), "5774")

    def test_genuine_negative_with_explicit_evidence(self) -> None:
        self.put("train", "images", "negative.JPG")
        self.put("train", "images", "unknown.JPG")
        result = audit(self.root, expected_negatives={("train", "negative")})
        classes = {r["filename"]: r["classification"] for r in result["unmatched_images"]}
        self.assertEqual(classes["negative.JPG"], "expected_negative_external_evidence")
        self.assertEqual(classes["unknown.JPG"], "unexplained_missing_label")
        self.assertEqual(result["pairing_summary"][0]["images_without_labels"], 2)

    def test_empty_negative_annotation_is_still_a_pair(self) -> None:
        self.put("test", "images", "negative.JPG")
        self.put("test", "labels", "negative.txt", " \n")
        result = audit(self.root)
        self.assertTrue(result["matched_pairs"][0]["empty_annotation"])
        self.assertEqual(result["unmatched_images"], [])

    def test_orphan_label_with_no_candidate(self) -> None:
        self.put("train", "labels", "111.txt")
        result = audit(self.root)
        self.assertEqual(result["unmatched_labels"][0]["filename"], "111.txt")
        self.assertFalse(result["unmatched_labels"][0]["exact_basename_exists_elsewhere"])
        self.assertEqual(result["pairing_candidates"], [])

    def test_cross_split_exact_basename_both_directions(self) -> None:
        self.put("train", "labels", "42.txt")
        self.put("valid", "images", "42.JPG")
        self.put("test", "images", "42.PNG")
        result = audit(self.root)
        self.assertTrue(result["unmatched_labels"][0]["exact_basename_exists_elsewhere"])
        self.assertTrue(all(r["exact_basename_exists_elsewhere"] for r in result["unmatched_images"]))
        self.assertIn('"split": "test"', result["unmatched_labels"][0]["cross_split_matches"])
        top = result["pairing_candidates"][0]
        self.assertEqual((top["candidate_scope"], top["edit_distance"], top["numeric_difference"]),
                         ("all_splits", 0, 0))
        self.assertEqual(result["matched_pairs"], [])

    def test_similar_names_are_never_paired(self) -> None:
        self.put("train", "labels", "111.txt")
        for name in ("110.JPG", "113.JPG", "211.JPG", "abcd.JPG"):
            self.put("train", "images", name)
        result = audit(self.root)
        self.assertEqual(result["matched_pairs"], [])
        top = result["pairing_candidates"][0]
        self.assertEqual(top["candidate_image_filename"], "110.JPG")
        self.assertEqual(top["edit_distance"], 1)
        self.assertAlmostEqual(top["normalized_similarity"], 2 / 3)
        self.assertEqual(top["numeric_difference"], 1)
        nonnumeric = next(r for r in result["pairing_candidates"] if r["candidate_image_filename"] == "abcd.JPG")
        self.assertIsNone(nonnumeric["numeric_difference"])
        self.assertEqual(edit_distance("kitten", "sitting"), 3)
        self.assertEqual(edit_distance("", "123"), 3)

    def test_duplicate_image_and_label_keys_are_ambiguous(self) -> None:
        self.put("train", "images", "dup.JPG")
        self.put("train", "images", "DUP.png")
        self.put("train", "labels", "dup.txt")
        self.put("valid", "images", "x.JPG")
        self.put("valid", "labels", "x.txt")
        self.put("valid", "labels", " x.txt")
        result = audit(self.root)
        self.assertEqual(len(result["duplicate_basenames"]), 4)
        self.assertEqual(result["matched_pairs"], [])
        self.assertEqual(result["pairing_summary"][0]["ambiguous_images"], 2)
        self.assertEqual(result["pairing_summary"][1]["ambiguous_labels"], 2)
        for row in result["pairing_summary"]:
            self.assertEqual(row["total_images"], row["exact_matched_pairs"] + row["images_without_labels"] + row["ambiguous_images"])
            self.assertEqual(row["total_labels"], row["exact_matched_pairs"] + row["labels_without_images"] + row["ambiguous_labels"])

    def test_top_ten_scopes_determinism_and_input_unchanged(self) -> None:
        self.put("train", "labels", "100.txt")
        for split in SPLITS:
            for n in range(101, 114):
                self.put(split, "images", f"{n}.JPG")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        first, second = audit(self.root), audit(self.root)
        self.assertEqual(first, second)
        candidates = first["pairing_candidates"]
        self.assertEqual(len(candidates), 20)
        for scope in ("same_split", "all_splits"):
            rows = [r for r in candidates if r["candidate_scope"] == scope]
            self.assertEqual([r["candidate_rank"] for r in rows], list(range(1, 11)))
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        out = Path(self.temporary.name) / "outputs"
        write_outputs(first, out)
        outputs = {p.name: p.read_bytes() for p in out.iterdir()}
        write_outputs(second, out)
        self.assertEqual(outputs, {p.name: p.read_bytes() for p in out.iterdir()})
        with (out / "duplicate_basenames.csv").open(encoding="utf-8", newline="") as handle:
            self.assertEqual(next(csv.reader(handle)), ["split", "kind", "normalized_basename", "filename", "duplicate_count"])
        self.assertIn("691", (out / "pairing_report.md").read_text(encoding="utf-8"))

    def test_missing_directory_fails(self) -> None:
        (self.root / "valid" / "valid" / "labels").rmdir()
        with self.assertRaisesRegex(FileNotFoundError, "Required directory missing"):
            audit(self.root)

    def test_cli_rejects_output_inside_input(self) -> None:
        process = subprocess.run([sys.executable, str(REPOSITORY / "scripts/data/audit_gyu_pairing.py"),
                                  "--root", str(self.root), "--output", str(self.root / "reports")],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertFalse((self.root / "reports").exists())


if __name__ == "__main__":
    unittest.main()
