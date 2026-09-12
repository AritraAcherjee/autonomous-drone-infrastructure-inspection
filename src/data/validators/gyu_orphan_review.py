"""Human-only orphan review using existing audit inventories and Pillow."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, __version__ as PILLOW_VERSION

from data.validators.gyu_pairing import edit_distance, pairing_key

INDEX_FIELDS = "label_split label_filename annotation_count candidate_rank candidate_image_filename candidate_image_split edit_distance normalized_similarity numeric_difference review_sheet_path review_status reviewer_selected_candidate review_notes".split()
COLORS = ("#FF3535", "#FFB000", "#00D5FF", "#FF54DA", "#76FF40", "#B4A2FF")


@dataclass(frozen=True)
class Box:
    class_id: int
    x: float
    y: float
    width: float
    height: float


def parse_yolo(text: str, classes: list[str]) -> list[Box]:
    """Reject the entire annotation on any malformed row; never partially render."""
    boxes = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"Row {number}: expected exactly 5 numeric fields")
        try:
            values = [float(value) for value in fields]
        except ValueError as exc:
            raise ValueError(f"Row {number}: nonnumeric field") from exc
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Row {number}: nonfinite value")
        class_id, x, y, width, height = values
        if not class_id.is_integer() or not 0 <= class_id < len(classes):
            raise ValueError(f"Row {number}: invalid class ID {class_id}")
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
            raise ValueError(f"Row {number}: invalid normalized coordinates or dimensions")
        boxes.append(Box(int(class_id), x, y, width, height))
    if not boxes:
        raise ValueError("Orphan annotation contains no annotation rows")
    return boxes


def box_pixels(box: Box, size: tuple[int, int]) -> tuple[float, float, float, float]:
    """Convert YOLO center/size to unrounded pixel corners; do not distort geometry."""
    width, height = size
    return ((box.x - box.width / 2) * width, (box.y - box.height / 2) * height,
            (box.x + box.width / 2) * width, (box.y + box.height / 2) * height)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_filename(name: str) -> str:
    if not name or Path(name).name != name or "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError(f"Unsafe filename in audit inventory: {name!r}")
    return name


def select_candidates(label: dict[str, str], unmatched: list[dict[str, str]],
                      matched: list[dict[str, str]], cached: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Re-rank only the existing unmatched inventory; no raw pairing enumeration.

    The previous CSV is truncated to ten candidates and includes matched images.
    Reuse its scores where available, and score missing inventory entries using
    the original audit's distance helper and documented ordering.
    """
    split, name = label["split"], safe_filename(label["filename"])
    if split not in ("train", "valid", "test"):
        raise ValueError(f"Invalid split: {split}")
    key = pairing_key(name)
    occupied = {(r["split"], pairing_key(r["image_filename"])) for r in matched}
    cache = {(r["candidate_image_split"], r["candidate_image_filename"]): r for r in cached
             if r["label_split"] == split and r["label_filename"] == name}
    scored = []
    seen = set()
    for image in unmatched:
        image_name = safe_filename(image["filename"])
        image_key = pairing_key(image_name)
        if image["split"] != split or (split, image_key) in occupied or image_name in seen:
            continue
        seen.add(image_name)
        previous = cache.get((split, image_name))
        distance = int(previous["edit_distance"]) if previous else edit_distance(key, image_key)
        similarity = 1 - distance / max(len(key), len(image_key), 1)
        numeric = (abs(int(key) - int(image_key)) if key.isascii() and key.isdecimal()
                   and image_key.isascii() and image_key.isdecimal() else None)
        scored.append(dict(candidate_image_filename=image_name, candidate_image_split=split,
                           edit_distance=distance, normalized_similarity=similarity,
                           numeric_difference=numeric))
    scored.sort(key=lambda r: (r["edit_distance"], -r["normalized_similarity"],
                              r["numeric_difference"] if r["numeric_difference"] is not None else math.inf,
                              r["candidate_image_filename"].casefold(), r["candidate_image_filename"]))
    selected = []
    for rank, row in enumerate(scored, 1):
        if rank <= 5 or (row["numeric_difference"] is not None and row["numeric_difference"] <= 2):
            selected.append(dict(row, candidate_rank=rank,
                                 selection_reason="top_5" if rank <= 5 else "numeric_neighbor"))
    return selected


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def image_panel(source: Image.Image, boxes: list[Box] | None, classes: list[str],
                width: int = 760, height: int = 600) -> Image.Image:
    """Aspect-preserving panel; overlays have numbered boxes and full-label callouts."""
    rail = 260 if boxes is not None else 0
    panel = Image.new("RGB", (width + rail, height), "#101923")
    fitted = source.copy()
    fitted.thumbnail((width, height), Image.Resampling.LANCZOS)
    offset = ((width - fitted.width) // 2, (height - fitted.height) // 2)
    panel.paste(fitted, offset)
    if boxes is None:
        return panel
    draw = ImageDraw.Draw(panel)
    for number, box in enumerate(boxes, 1):
        corners = box_pixels(box, fitted.size)
        left, top, right, bottom = (corners[0] + offset[0], corners[1] + offset[1],
                                    corners[2] + offset[0], corners[3] + offset[1])
        # Normalized fields may describe a box extending outside the frame.
        # Clip only display coordinates; report the condition separately.
        left, right = max(offset[0], left), min(offset[0] + fitted.width - 1, right)
        top, bottom = max(offset[1], top), min(offset[1] + fitted.height - 1, bottom)
        color = COLORS[box.class_id % len(COLORS)]
        draw.rectangle((left, top, max(left, right), max(top, bottom)), outline=color, width=3)
        draw.text((left + 2, top + 2), str(number), font=font(16), fill="white", stroke_width=2, stroke_fill="black")
        label_y = 12 + (number - 1) * min(25, (height - 28) / max(len(boxes), 1))
        draw.line((max(left, right), (top + bottom) / 2, width + 8, label_y + 9), fill=color, width=1)
        draw.text((width + 12, label_y), f"#{number:02d} | {box.class_id} {classes[box.class_id]}",
                  font=font(17), fill=color)
    return panel


def index_row(label: dict[str, str], count: int, candidate: dict[str, Any], sheet: str) -> dict[str, Any]:
    return dict(label_split=label["split"], label_filename=label["filename"], annotation_count=count,
                **{k: candidate[k] for k in ("candidate_rank", "candidate_image_filename",
                    "candidate_image_split", "edit_distance", "normalized_similarity", "numeric_difference")},
                review_sheet_path=sheet, review_status="pending", reviewer_selected_candidate="", review_notes="")


def generate(root: Path, audit_dir: Path, classes_path: Path, output: Path) -> dict[str, Any]:
    root, audit_dir, classes_path, output = (p.resolve() for p in (root, audit_dir, classes_path, output))
    repository_raw = Path(__file__).resolve().parents[3] / "data" / "raw"
    if any(output == protected or protected in output.parents for protected in (root, repository_raw.resolve())):
        raise ValueError("Output cannot be inside data/raw or the dataset root")
    if (output / "index.csv").exists():
        raise ValueError("Review index already exists; use a new output directory to preserve reviewer decisions")
    classes = classes_path.read_text(encoding="utf-8-sig").splitlines()
    if not classes or any(not line.strip() for line in classes):
        raise ValueError("classes.txt must contain one nonempty class name per line")
    classes = [line.strip() for line in classes]
    required = ("unmatched_labels.csv", "unmatched_images.csv", "matched_pairs.csv", "pairing_candidates.csv")
    inventories = {name: read_csv(audit_dir / name) for name in required}
    labels = inventories["unmatched_labels.csv"]
    # Validate every annotation and select every candidate before any rendering.
    prepared = []
    for label in labels:
        candidates = select_candidates(label, inventories["unmatched_images.csv"],
                                       inventories["matched_pairs.csv"], inventories["pairing_candidates.csv"])
        path = root / label["split"] / label["split"] / "labels" / label["filename"]
        text = ""
        try:
            text = path.read_text(encoding="utf-8-sig")
            boxes, error = parse_yolo(text, classes), ""
        except (ValueError, OSError) as exc:
            boxes, error = [], str(exc)
        prepared.append((label, candidates, boxes, error, sum(bool(line.strip()) for line in text.splitlines())))
    output.mkdir(parents=True, exist_ok=True)
    index = []
    statuses = []
    triage = []
    for label, candidates, boxes, error, count in prepared:
        stem = pairing_key(label["filename"])
        sheet_name = f"{label['split']}_{stem}_review.png"
        row_height = max(680, 100 + 26 * len(boxes))
        sheet = Image.new("RGB", (1840, 130 + max(1, len(candidates)) * row_height), "#101923")
        draw = ImageDraw.Draw(sheet)
        draw.text((24, 18), f"ORPHAN REVIEW | {label['split']} / {label['filename']} | {count} annotation rows", font=font(28), fill="white")
        draw.text((24, 58), "UNVERIFIED CANDIDATES - human review required; filename scores do not establish a pair", font=font(20), fill="#FFCE62")
        draw.text((24, 90), "INVALID: " + error if error else "All YOLO rows valid. Left: raw pixels. Right: hypothetical overlay with numbered class callouts.", font=font(19), fill="#FF6868" if error else "#BAE0CE")
        label_status = dict(label_split=label["split"], label_filename=label["filename"], annotation_count=count,
                            validation_status="invalid" if error else "valid", validation_error=error,
                            candidate_count=len(candidates), rendering_failures=[], warnings=[])
        if not candidates:
            draw.text((24, 160), "No eligible unmatched candidates available.", font=font(24), fill="white")
        rank1 = None
        for display_number, candidate in enumerate(candidates):
            y = 130 + display_number * row_height
            filename = candidate["candidate_image_filename"]
            image_path = root / label["split"] / label["split"] / "images" / filename
            resolution = "unavailable"
            try:
                with Image.open(image_path) as opened:
                    resolution = f"{opened.width} x {opened.height}"
                    if opened.getexif().get(274, 1) != 1:
                        label_status["warnings"].append(f"{filename}: EXIF orientation present; stored pixel orientation retained")
                    source = opened.convert("RGB")
                raw = image_panel(source, None, classes, height=row_height - 80)
                overlay = image_panel(source, boxes if not error else None, classes, height=row_height - 80)
                sheet.paste(raw, (24, y + 64))
                sheet.paste(overlay, (810, y + 64))
                if error:
                    draw.text((826, y + 82), "OVERLAY WITHHELD: INVALID ANNOTATION", font=font(23), fill="#FF3535", stroke_width=2, stroke_fill="black")
                if candidate["candidate_rank"] == 1:
                    rank1 = overlay.copy()
                    if error:
                        ImageDraw.Draw(rank1).text((15, 15), "INVALID - NO BOXES RENDERED", font=font(24), fill="#FF3535")
                tiny = sum(b.width * source.width < 10 or b.height * source.height < 10 for b in boxes)
                if tiny:
                    label_status["warnings"].append(f"{filename}: {tiny} boxes have a dimension below 10 source pixels")
            except (OSError, ValueError) as exc:
                failure = f"{filename}: {exc}"
                label_status["rendering_failures"].append(failure)
                draw.text((24, y + 100), "IMAGE RENDER FAILED: " + failure, font=font(21), fill="#FF6868")
            draw.text((24, y + 5), f"Rank {candidate['candidate_rank']} | {filename} | {resolution} | {candidate['selection_reason']}", font=font(24), fill="white")
            draw.text((24, y + 37), f"edit distance {candidate['edit_distance']} | similarity {candidate['normalized_similarity']:.8f} | numeric difference {candidate['numeric_difference']}     RAW (left) / HYPOTHETICAL BOXES (right)", font=font(19), fill="#BECAD7")
            index.append(index_row(label, count, candidate, sheet_name))
        for number, box in enumerate(boxes, 1):
            if box.x - box.width / 2 < -1e-6 or box.y - box.height / 2 < -1e-6 or box.x + box.width / 2 > 1 + 1e-6 or box.y + box.height / 2 > 1 + 1e-6:
                label_status["warnings"].append(f"Box {number}: corners extend beyond frame; display clipped, normalized fields valid")
        sheet.save(output / sheet_name)
        statuses.append(label_status)
        triage.append((label, candidates[0] if candidates else None, rank1, bool(error)))
    contact = Image.new("RGB", (2400, 100 + 540 * math.ceil(max(1, len(triage)) / 3)), "#101923")
    contact_draw = ImageDraw.Draw(contact)
    contact_draw.text((24, 18), "GYU-DET V3 | rank-1 UNMATCHED candidates | human triage only", font=font(32), fill="white")
    contact_draw.text((24, 61), "These overlays are hypotheses, not accepted pairings. Inspect full review sheets before making decisions.", font=font(22), fill="#FFCE62")
    for n, (label, candidate, overlay, invalid) in enumerate(triage):
        x, y = (n % 3) * 800, 100 + (n // 3) * 540
        title = f"{label['split']}/{label['filename']} -> {candidate['candidate_image_filename'] if candidate else 'NO CANDIDATE'}"
        contact_draw.text((x + 14, y + 10), title, font=font(23), fill="white")
        if overlay:
            overlay.thumbnail((780, 485), Image.Resampling.LANCZOS)
            contact.paste(overlay, (x + 10, y + 48))
        else:
            contact_draw.text((x + 14, y + 90), "Overlay unavailable - see validation.json", font=font(21), fill="#FF6868")
    contact.save(output / "all_rank1_candidates.png")
    with (output / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(index)
    summary = dict(valid_annotations=sum(not p[3] for p in prepared), invalid_annotations=sum(bool(p[3]) for p in prepared),
                   review_sheets=len(prepared), candidate_rows=len(index),
                   rendering_failures=sum(len(s["rendering_failures"]) for s in statuses), annotations=statuses,
                   classes={str(i): name for i, name in enumerate(classes)}, classes_path=str(classes_path),
                   pillow_version=PILLOW_VERSION,
                   input_sha256={str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in [classes_path, *(audit_dir / name for name in required)]})
    (output / "validation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    readme = """# GYU-DET V3 orphan annotation visual review

The pairing audit found 712 images without labels and 21 orphan labels. The published
negative/no-defect total supplied for this audit is 691. The relationship 712 - 21 = 691
is suggestive but insufficient: it does not prove that these annotations belong to
21 of the unlabeled images. No remaining image is classified as negative here.

Filename similarity is not evidence of a true pair. Every overlay is a hypothesis.
Human visual review is required before any repair mapping is accepted. Compare the
raw panel with the overlay at full resolution, checking defect location, category,
box extent, and all annotation rows. Record pending/accepted/rejected decisions in
index.csv, with the selected filename and notes. A reviewer selection is only a
proposal, not an automatic repair. data/raw/ remains immutable. M1 is not complete.

## Reproduce

From the repository root, using Python 3.10+ and Pillow 10.1+:

```text
python scripts/data/review_gyu_orphans.py --root data/raw/gyu_det/v3/extracted --audit outputs/validation/gyu_det_v3 --classes data/raw/gyu_det/v3/archives/classes.txt --output outputs/validation/gyu_det_v3/orphan_review
python -m unittest discover -s tests/data -v
```

An existing index.csv is never overwritten; choose a fresh --output directory to
reproduce a package without destroying review decisions. Pillow's bundled default
font is used; validation.json records its Pillow version and hashes of audit inputs
and the authoritative local classes.txt. Class IDs follow its zero-based line order.

## Selection and interpretation

The generator reads unmatched_labels.csv, unmatched_images.csv, matched_pairs.csv,
and pairing_candidates.csv. It does not repeat dataset pairing discovery. Previous
top-ten lists contain matched images, so they cannot alone supply the requested
unmatched shortlist. Cached distances are reused; missing scores are computed over
the CSV unmatched inventory using the original audit distance helper. Already
matched normalized image basenames are excluded. Only same-split candidates are used.

Order is edit distance ascending, normalized similarity descending, absolute numeric
difference ascending, then case-folded and original filename. Similarity equals
1 - distance / maximum stem length. Select top five plus every numeric neighbor
within absolute difference <= 2. candidate_rank retains rank among all eligible
unmatched images, so added numeric neighbors may have ranks greater than five.
review_sheet_path is relative to this directory. Every index row starts pending,
with reviewer_selected_candidate and review_notes blank. Full sheets include source
resolution. Both raw and overlay views retain aspect ratio and stored pixel orientation.
Every numbered box has a connector to a readable class ID/name in the overlay rail.
No EXIF rotation is applied; any nontrivial orientation is flagged in validation.json.

## Validation and limitations

All orphan files are validated before rendering starts: five numeric fields per
nonblank row, finite values, integer class ID in classes.txt, centers in [0,1],
dimensions in (0,1]. Blank lines are ignored; empty orphan annotations are flagged.
Any malformed row suppresses the entire file's overlay. Invalid files and image
failures are flagged on sheets and in validation.json; index review status remains
pending. Valid normalized fields can yield corners beyond the frame; these are
flagged and clipped only for display. Original annotations are never changed.
Tiny boxes are flagged for closer inspection. Reduced-size contact sheets cannot
establish alignment for tiny defects. No automatic pairing, renaming, or repair occurs.
"""
    readme += f"\n## This run\n\nValid annotations: {summary['valid_annotations']}; invalid: {summary['invalid_annotations']}; sheets: {summary['review_sheets']}; candidate rows: {summary['candidate_rows']}; rendering failures: {summary['rendering_failures']}.\n"
    (output / "README.md").write_text(readme, encoding="utf-8")
    return summary
