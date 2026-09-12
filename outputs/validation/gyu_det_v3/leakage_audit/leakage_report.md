# GYU-DET V3 duplicate and leakage audit

Analysis only. Raw data, official split membership, the source manifest and human triage are unchanged. No final training export, deletion, orphan repair, or negative classification is approved. M1 remains incomplete.

## Method and reproducibility

Run `python scripts/data/audit_gyu_leakage.py` from the repository root. Run tests with `python -m unittest discover -s tests/data -v`. Existing review indexes are protected: use fresh --output and --review directories for another run.
Exact comparisons reuse SHA-256 from the existing manifest without rehashing images. Raw file sizes are checked against the manifest; size/mtime and protected input hashes are checked at completion. Therefore exact conclusions depend on the trusted manifest; equal-size external modifications predating this run are not detected.
Every primary image is loaded. Fingerprints use 128 deterministic dHash bits: 64 horizontal 8x8 comparisons after 9x8 grayscale LANCZOS resize, then 64 vertical comparisons after 8x9 resize. Strict greater-than comparison, row-major order, fixed 32-digit hexadecimal. Pillow version is recorded. EXIF rotation is not applied; rotated or cropped copies can be missed.
A BK-tree searches all cross-split fingerprints with Hamming radius 12; it is an exact metric search, not a sample or naive all-pairs scan. All qualifying pairs are exported, not just the displayed review subset.
Disjoint diagnostic tiers: distance 0 identical hash; 1-4 very strong; 5-8 probable; 9-12 weaker. These allow at most 3.125%, 6.25%, and 9.375% of bits to differ. Thresholds are heuristic, not calibrated probabilities or proof of leakage. Uniform/low-information scenes can collide. Low grayscale contrast or extreme hash bit counts are flagged. Exact cross-split content duplication is established by manifest SHA equality; perceptual similarity alone never establishes a leak.
Normalized basename collisions trim whitespace and case-fold stems; they do not imply matching content. Numeric filenames within absolute difference 2 are searched by sorted bisect ranges. Capture-series signals include numeric neighbors, matching camera make/model, and equal EXIF capture timestamps; no reliable temporal ordering, timezone or session identity is assumed. Missing metadata is not an error. Primary pixels alone contribute to fingerprints.

## Results

| Metric | Value |
|---|---|
| images | 11123 |
| fingerprint_failures | 0 |
| exact_duplicate_groups | 7 |
| within_split_exact_duplicate_pairs | 6 |
| cross_split_exact_duplicate_pairs | 1 |
| basename_collision_groups | 0 |
| within_split_basename_collision_pairs | 0 |
| cross_split_basename_collision_pairs | 0 |
| cross_split_identical_perceptual_hash | 1 |
| cross_split_very_strong | 1 |
| cross_split_probable | 1 |
| cross_split_weaker | 14 |
| candidate_pairs_needing_review | 17 |
| review_pairs_shown | 17 |
| review_sheet_count | 5 |
| rendering_failures | 0 |
| numeric_neighbor_pairs | 18 |
| numeric_neighbors_also_perceptual | 0 |
| cross_split_capture_metadata_groups | 1 |
| mpo_images | 565 |
| opencv_check | skipped: OpenCV not installed |
| opencv_load_failures | 0 |
| opencv_dimension_mismatches | 0 |

Within-split exact pair counts: {"train": 4, "valid": 2, "test": 0}.
Cross-split exact pair counts: {"train/valid": 1}.
Cross-split perceptual candidates by split pair: {"train/valid": 4, "train/test": 11, "valid/test": 2}.
Counts are unordered image pairs, not excess files. One duplicate group can contribute multiple within-split and cross-split pairs. Near tiers include SHA-equal pairs; total review candidates are deduplicated.

## Human review and limitations

The review index contains at most 24 pairs, ordered by exact content duplication, identical perceptual hash, then lowest distance and deterministic filenames. Four pairs per sheet, both raw primary images side by side with aspect ratio preserved. All statuses start pending. See ../leakage_review/index.csv; full near-candidate inventory is cross_split_near_duplicates.csv.
MPO compatibility: skipped: OpenCV not installed. The 565 affected images are not excluded or modified.
When available, OpenCV default imread is tested against manifest width/height; EXIF auto-orientation may cause swapped dimensions, so mismatch is a diagnostic rather than proof of unreadability. A skipped check does not certify future reader compatibility.
See ../baseline_data_policy.md for the provisional warning-only MPO and rounding policy. Human review is needed before deciding split contamination or any deduplication policy. No approved final split/training dataset exists.
