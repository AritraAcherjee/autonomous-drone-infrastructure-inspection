"""Synthetic tests for parsing, candidate selection, and review generation."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data.validators.gyu_orphan_review import (
    Box, INDEX_FIELDS, box_pixels, generate, image_panel, parse_yolo, read_csv, select_candidates,
)


class ReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "raw"
        self.audit = self.base / "audit"
        self.audit.mkdir()
        self.classes = self.base / "classes.txt"
        self.classes.write_text("Crack\nBreakage\nComb\nHole\nReinforcement\nSeepage\n")

    def write_csv(self, name: str, rows: list[dict[str, str]], fields: list[str]) -> None:
        with (self.audit / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def fixture(self, annotation: str = "0 0.5 0.5 0.5 0.5\n") -> None:
        directory = self.root / "train" / "train"
        (directory / "labels").mkdir(parents=True)
        (directory / "images").mkdir()
        (directory / "labels" / "111.txt").write_text(annotation)
        Image.new("RGB", (160, 90), "#777777").save(directory / "images" / "112.JPG")
        self.write_csv("unmatched_labels.csv", [{"split": "train", "filename": "111.txt"}], ["split", "filename"])
        self.write_csv("unmatched_images.csv", [{"split": "train", "filename": "112.JPG"}], ["split", "filename"])
        self.write_csv("matched_pairs.csv", [], ["split", "image_filename"])
        self.write_csv("pairing_candidates.csv", [], ["label_split", "label_filename", "candidate_image_split", "candidate_image_filename"])

    def test_yolo_parsing(self) -> None:
        boxes = parse_yolo("\n0 0.5 0.25 1 0.5\n1.0 0.1 0.2 0.1 0.2\n", ["Crack", "Breakage"])
        self.assertEqual(boxes, [Box(0, 0.5, 0.25, 1, 0.5), Box(1, 0.1, 0.2, 0.1, 0.2)])

    def test_coordinate_conversion(self) -> None:
        self.assertEqual(box_pixels(Box(0, 0.5, 0.25, 0.2, 0.5), (200, 100)), (80, 0, 120, 50))

    def test_invalid_annotation_handling(self) -> None:
        invalid = ["", "0 0.5 0.5 0.2", "0 0.5 0.5 0.2 0.2 9", "cat .5 .5 .2 .2",
                   "0 nan .5 .2 .2", "0 .5 inf .2 .2", "-1 .5 .5 .2 .2", "2 .5 .5 .2 .2",
                   "0.5 .5 .5 .2 .2", "0 1.1 .5 .2 .2", "0 .5 -.1 .2 .2", "0 .5 .5 0 .2",
                   "0 .5 .5 .2 -1", "0 .5 .5 1.1 .2"]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_yolo(value, ["Crack", "Breakage"])
        with self.assertRaisesRegex(ValueError, "Row 2"):
            parse_yolo("0 .5 .5 .2 .2\nBAD", ["Crack"])

    def test_overlay_generation_preserves_source_and_aspect(self) -> None:
        source = Image.new("RGB", (200, 100), "gray")
        original = source.tobytes()
        raw = image_panel(source, None, ["Crack"], width=200, height=200)
        overlay = image_panel(source, [Box(0, .5, .5, .2, .2)], ["Crack"], width=200, height=200)
        self.assertEqual(source.tobytes(), original)
        self.assertEqual(raw.getpixel((0, 49)), (16, 25, 35))
        self.assertEqual(raw.getpixel((0, 50)), (128, 128, 128))
        self.assertEqual(overlay.getpixel((80, 90)), (255, 53, 53))
        self.assertIsNotNone(ImageChops.difference(raw, overlay.crop((0, 0, 200, 200))).getbbox())
        self.assertIsNotNone(ImageChops.difference(overlay.crop((200, 0, 460, 200)), Image.new("RGB", (260, 200), "#101923")).getbbox())

    def test_unmatched_only_top_five_and_numeric_neighbors(self) -> None:
        names = ["1011.JPG", "1101.JPG", "1110.JPG", "1111.JPG", "1112.JPG", "1113.JPG", "112.JPG", "113.JPG", "110.JPG"]
        unmatched = [{"split": "train", "filename": name} for name in names]
        unmatched.append({"split": "valid", "filename": "111.JPG"})
        selected = select_candidates({"split": "train", "filename": "111.txt"}, unmatched,
                                     [{"split": "train", "image_filename": "110.JPG"}], [])
        self.assertEqual(len(selected), 7)
        self.assertEqual([r["candidate_rank"] for r in selected], [1, 2, 3, 4, 5, 7, 8])
        self.assertEqual([r["candidate_image_filename"] for r in selected[-2:]], ["112.JPG", "113.JPG"])
        self.assertTrue(all(r["candidate_image_split"] == "train" for r in selected))

    def test_review_index_and_reproducibility(self) -> None:
        self.fixture()
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        first, second = self.base / "first", self.base / "second"
        result = generate(self.root, self.audit, self.classes, first)
        generate(self.root, self.audit, self.classes, second)
        self.assertEqual(result["valid_annotations"], 1)
        self.assertEqual(result["review_sheets"], 1)
        self.assertEqual(result["rendering_failures"], 0)
        row = read_csv(first / "index.csv")[0]
        self.assertEqual(list(row), INDEX_FIELDS)
        self.assertEqual(row["review_status"], "pending")
        self.assertEqual(row["reviewer_selected_candidate"], "")
        self.assertEqual(row["review_notes"], "")
        self.assertEqual(row["annotation_count"], "1")
        self.assertTrue((first / row["review_sheet_path"]).exists())
        self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()}, {p.name: p.read_bytes() for p in second.iterdir()})
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        with self.assertRaisesRegex(ValueError, "already exists"):
            generate(self.root, self.audit, self.classes, first)

    def test_invalid_file_is_flagged_without_partial_overlay(self) -> None:
        self.fixture("0 .5 .5 .2 .2\n0 nan .5 .2 .2")
        out = self.base / "out"
        result = generate(self.root, self.audit, self.classes, out)
        self.assertEqual(result["invalid_annotations"], 1)
        self.assertEqual(result["valid_annotations"], 0)
        self.assertIn("Row 2", result["annotations"][0]["validation_error"])
        self.assertEqual(read_csv(out / "index.csv")[0]["review_status"], "pending")
        self.assertTrue((out / "train_111_review.png").exists())

    def test_corrupt_candidate_is_flagged(self) -> None:
        self.fixture()
        (self.root / "train/train/images/112.JPG").write_bytes(b"not an image")
        result = generate(self.root, self.audit, self.classes, self.base / "out")
        self.assertEqual(result["rendering_failures"], 1)

    def test_raw_output_guard(self) -> None:
        self.fixture()
        with self.assertRaisesRegex(ValueError, "Output cannot"):
            generate(self.root, self.audit, self.classes, self.root / "review")


if __name__ == "__main__":
    unittest.main()
