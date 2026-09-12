"""Deterministic, read-only filename diagnostics for nested GYU-DET splits."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SPLITS = ("train", "valid", "test")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def pairing_key(filename: str) -> str:
    """Trim whitespace and case-fold the stem, preserving the original elsewhere."""
    return Path(filename.strip()).stem.strip().casefold()


@dataclass(frozen=True)
class Entry:
    split: str
    path: Path
    key: str


def edit_distance(left: str, right: str) -> int:
    """Levenshtein distance with linear auxiliary memory."""
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def enumerate_entries(root: Path, split: str, kind: str) -> list[Entry]:
    directory = root / split / split / kind
    if not directory.is_dir():
        raise FileNotFoundError(f"Required directory missing: {directory}")
    extensions = IMAGE_EXTENSIONS if kind == "images" else {".txt"}
    return [Entry(split, path, pairing_key(path.name))
            for path in sorted(directory.iterdir(), key=lambda p: (p.name.casefold(), p.name))
            if path.is_file() and Path(path.name.strip()).suffix.casefold() in extensions]


def index_entries(entries: list[Entry]) -> dict[str, list[Entry]]:
    result: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        result[entry.key].append(entry)
    return dict(result)


def audit(root: Path, expected_negatives: set[tuple[str, str]] | None = None) -> dict[str, Any]:
    """Expected negatives require external evidence, never inferred from absence.

    Optional expected_negatives is a set of (split, basename) pairs supplied by a
    caller with authoritative evidence. Duplicate keys are not one-to-one pairs.
    """
    expected = {(split, pairing_key(key)) for split, key in (expected_negatives or set())}
    images = {s: enumerate_entries(root, s, "images") for s in SPLITS}
    labels = {s: enumerate_entries(root, s, "labels") for s in SPLITS}
    ii = {s: index_entries(images[s]) for s in SPLITS}
    li = {s: index_entries(labels[s]) for s in SPLITS}
    result: dict[str, Any] = {name: [] for name in FIELDS}
    orphans: list[Entry] = []
    for split in SPLITS:
        for kind, index in (("images", ii[split]), ("labels", li[split])):
            for key, entries in sorted(index.items()):
                if len(entries) > 1:
                    for entry in entries:
                        result["duplicate_basenames"].append(dict(
                            split=split, kind=kind, normalized_basename=key,
                            filename=entry.path.name, duplicate_count=len(entries)))
        matched = []
        for key in sorted(ii[split].keys() & li[split].keys()):
            if len(ii[split][key]) == len(li[split][key]) == 1:
                im, lab = ii[split][key][0], li[split][key][0]
                matched.append(dict(split=split, normalized_basename=key,
                                    image_filename=im.path.name, label_filename=lab.path.name,
                                    empty_annotation=not lab.path.read_bytes().strip()))
        result["matched_pairs"].extend(matched)
        counts = {}
        for kind, entries, opposite in (("labels", labels[split], ii),
                                         ("images", images[split], li)):
            unmatched = [e for e in entries if e.key not in opposite[split]]
            counts[kind] = len(unmatched)
            for entry in unmatched:
                elsewhere = [e for s in SPLITS if s != split
                             for e in opposite[s].get(entry.key, [])]
                row = dict(split=split, filename=entry.path.name, normalized_basename=entry.key,
                           exact_basename_exists_elsewhere=bool(elsewhere),
                           cross_split_matches=json.dumps([
                               {"split": e.split, "filename": e.path.name} for e in elsewhere],
                               ensure_ascii=False, sort_keys=True))
                if kind == "images":
                    row["classification"] = ("expected_negative_external_evidence"
                        if (split, entry.key) in expected else "unexplained_missing_label")
                else:
                    orphans.append(entry)
                result[f"unmatched_{kind}"].append(row)
        result["pairing_summary"].append(dict(
            split=split, total_images=len(images[split]), total_labels=len(labels[split]),
            exact_matched_pairs=len(matched), images_without_labels=counts["images"],
            labels_without_images=counts["labels"],
            ambiguous_images=len(images[split]) - counts["images"] - len(matched),
            ambiguous_labels=len(labels[split]) - counts["labels"] - len(matched),
            matched_empty_annotations=sum(row["empty_annotation"] for row in matched)))
    all_images = [e for s in SPLITS for e in images[s]]
    for label in orphans:
        elsewhere = any(label.key in ii[s] for s in SPLITS if s != label.split)
        scored = []
        for candidate in all_images:
            distance = edit_distance(label.key, candidate.key)
            similarity = 1 - distance / max(len(label.key), len(candidate.key), 1)
            numeric = (abs(int(label.key) - int(candidate.key))
                       if label.key.isascii() and label.key.isdecimal()
                       and candidate.key.isascii() and candidate.key.isdecimal() else None)
            scored.append((distance, -similarity, numeric if numeric is not None else float("inf"),
                           SPLITS.index(candidate.split), candidate.path.name.casefold(),
                           candidate.path.name, candidate, numeric))
        scored.sort(key=lambda item: item[:6])
        for scope in ("same_split", "all_splits"):
            selected = [item for item in scored
                        if scope == "all_splits" or item[6].split == label.split][:10]
            for rank, item in enumerate(selected, 1):
                candidate = item[6]
                result["pairing_candidates"].append(dict(
                    label_split=label.split, label_filename=label.path.name,
                    candidate_scope=scope, candidate_image_split=candidate.split,
                    candidate_image_filename=candidate.path.name, edit_distance=item[0],
                    normalized_similarity=round(-item[1], 8), numeric_difference=item[7],
                    exact_basename_exists_elsewhere=elsewhere, candidate_rank=rank))
    result["regression_5774"] = [r for r in result["matched_pairs"] if r["normalized_basename"] == "5774"]
    return result


FIELDS = {
    "pairing_summary": "split total_images total_labels exact_matched_pairs images_without_labels labels_without_images ambiguous_images ambiguous_labels matched_empty_annotations",
    "unmatched_labels": "split filename normalized_basename exact_basename_exists_elsewhere cross_split_matches",
    "unmatched_images": "split filename normalized_basename exact_basename_exists_elsewhere cross_split_matches classification",
    "pairing_candidates": "label_split label_filename candidate_scope candidate_image_split candidate_image_filename edit_distance normalized_similarity numeric_difference exact_basename_exists_elsewhere candidate_rank",
    "duplicate_basenames": "split kind normalized_basename filename duplicate_count",
    "matched_pairs": "split normalized_basename image_filename label_filename empty_annotation",
}


def write_outputs(result: dict[str, Any], output: Path) -> None:
    """Write stable UTF-8 CSVs and Markdown without timestamps or absolute paths."""
    output.mkdir(parents=True, exist_ok=True)
    for name, columns in FIELDS.items():
        with (output / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns.split(), lineterminator="\n")
            writer.writeheader()
            writer.writerows(result[name])
    summaries = result["pairing_summary"]
    missing = sum(r["images_without_labels"] for r in summaries)
    expected = sum(r["classification"] == "expected_negative_external_evidence"
                   for r in result["unmatched_images"])
    cross_labels = sum(r["exact_basename_exists_elsewhere"] for r in result["unmatched_labels"])
    cross_images = sum(r["exact_basename_exists_elsewhere"] for r in result["unmatched_images"])
    lines = ["# GYU-DET V3 pairing audit", "", "## Method and reproduction", "",
        "Run from the repository root (Python 3.10+, standard library only):", "", "```text",
        "python scripts/data/audit_gyu_pairing.py --root data/raw/gyu_det/v3/extracted --output outputs/validation/gyu_det_v3",
        "python -m unittest discover -s tests/data -v", "```", "",
        "Directories: `<root>/<split>/<split>/{images,labels}` for train, valid, test. "
        "Independent, non-recursive enumeration. Image extensions: "
        + ", ".join(sorted(IMAGE_EXTENSIONS)) + "; labels: .txt (case-insensitive).",
        "Pairing keys are whitespace-trimmed, case-folded filename stems. Original names are retained. "
        "Exact means equal normalized stems. Only unique one-to-one keys count as matched pairs; "
        "duplicate keys with a counterpart are ambiguous and never arbitrarily paired.", "",
        "## Pairing counts", "", "| Split | Images | Labels | Exact pairs | Images without labels | Orphan labels | Ambiguous images / labels |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for r in summaries:
        lines.append(f"| {r['split']} | {r['total_images']} | {r['total_labels']} | {r['exact_matched_pairs']} | {r['images_without_labels']} | {r['labels_without_images']} | {r['ambiguous_images']} / {r['ambiguous_labels']} |")
    lines += ["", "## Negative images and unresolved missing annotations", "",
        f"There are {missing} images without same-split labels. Expected negatives supported by "
        f"external evidence: {expected}; unexplained missing labels: {missing - expected}.",
        f"There are {sum(r['matched_empty_annotations'] for r in summaries)} unique matched pairs "
        "with empty/whitespace-only annotations. These encode no boxes and are consistent with "
        "negative examples; this audit does not visually verify no-defect status.",
        "The published total supplied for this audit is 691 negative/no-defect images. "
        "The current raw pairing discrepancy requires further investigation before all unlabeled "
        "images can be classified as intentional negatives. An aggregate total does not identify "
        "individual negatives. The CLI supplies no external negative manifest; the reusable "
        "validator accepts an explicit evidence-backed expected_negatives set.", "",
        "## Orphan labels and cross-split exact matches", "",
        f"Orphan labels with exact images in another split: {cross_labels}. "
        f"Unmatched images with exact labels in another split: {cross_images}.",
        "Cross-split matches do not repair the local split. Every matching filename and split "
        "is retained as JSON in the unmatched CSVs.", "",
        "## Filename-similarity candidates", "",
        "Top 10 candidates per orphan are emitted separately for same_split and all_splits. "
        "Rank order: ascending Levenshtein distance, descending similarity "
        "(1 - distance / maximum stem length), ascending absolute numeric difference when both "
        "stems are ASCII digits, then train/valid/test order and original filename. "
        "Ranks use unrounded similarity; CSV similarity is rounded to 8 decimal places. "
        "Numeric difference is blank for nonnumeric stems. Similarity is diagnostic only; "
        "no candidate is automatically paired or renamed.", "",
        "| Label split | Orphan label | Exact image elsewhere | Best same-split image | Best all-splits image | Distance / similarity / numeric difference (all) |",
        "|---|---|---|---|---|---|"]
    for label in result["unmatched_labels"]:
        best = {r["candidate_scope"]: r for r in result["pairing_candidates"]
                if r["label_split"] == label["split"] and r["label_filename"] == label["filename"]
                and r["candidate_rank"] == 1}
        def describe(scope: str) -> str:
            row = best.get(scope)
            return f"{row['candidate_image_split']}/{row['candidate_image_filename']}" if row else "none"
        top = best.get("all_splits")
        metrics = f"{top['edit_distance']} / {top['normalized_similarity']} / {top['numeric_difference']}" if top else "n/a"
        lines.append(f"| {label['split']} | {label['filename']} | {label['cross_split_matches']} | {describe('same_split')} | {describe('all_splits')} | {metrics} |")
    lines += ["", "## Duplicates and 5774 regression", "",
        f"Duplicate filename rows: {len(result['duplicate_basenames'])}. See duplicate_basenames.csv.",
        "5774 regression matches: " + json.dumps(result["regression_5774"], sort_keys=True), "",
        "## Output integrity and limitations", "",
        "SHA-256 hashes identify the generated CSVs. Unchanged input produces identical outputs. "
        "This is a filename audit, not box-format, image-content, or provenance validation. "
        "Raw files are read only. M1 remains incomplete.", ""]
    for name in FIELDS:
        digest = hashlib.sha256((output / f"{name}.csv").read_bytes()).hexdigest()
        lines.append(f"- `{name}.csv`: `{digest}`")
    (output / "pairing_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
