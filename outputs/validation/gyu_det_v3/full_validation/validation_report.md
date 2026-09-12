# GYU-DET V3 full read-only validation

This pass validates every inventoried image and every .txt label, including all orphan labels. No images are sampled, rewritten, reoriented, repaired, or used for training. M1 remains incomplete.

## Reproduce

```text
python scripts/data/validate_gyu_det.py --root data/raw/gyu_det/v3/extracted --audit outputs/validation/gyu_det_v3 --classes data/raw/gyu_det/v3/archives/classes.txt --output outputs/validation/gyu_det_v3/full_validation --manifest data/manifests/gyu_det_v3_raw_manifest.csv
python -m unittest discover -s tests/data -v
```

Python and Pillow versions and input audit/class SHA-256 hashes are in validation.json. SHA-256 is streamed for every image, including images which fail decoding. File metadata and audit/triage hashes are checked again before publishing outputs.

## Archive integrity

Previously verified complete per user; archives not re-tested by this extracted-file pass. This is separate from the checks below.

## Image integrity

Images validated: 11123; strict all-frame integrity failures: 565; primary-image decode failures: 0; auxiliary-frame failures: 565; unsupported extensions: 0.
JPEG files with MPF metadata can be recognized as MPO (multi-picture) containers. MPO is accepted under JPEG extensions. Auxiliary-frame failure remains an integrity error, but does not imply the primary image is unreadable. image_validation.csv separates primary_decode_success, decode_success (all declared frames), and decoder_failure_stage. Resolution statistics use successfully decoded primary images.
Pillow verify() plus a separate reopen and full load() of every frame is used with truncated-image acceptance disabled. These are decoder-based checks, not a guarantee against every possible bit-level defect. Channel counts are stored bands (palette images are not silently converted). EXIF orientation is reported, never applied.
EXIF counts: {"1": 9763, "3": 17, "6": 382, "8": 318, "absent": 643}.
Image mode counts: {"RGB": 11123}.

## Label syntax validity

Label files: 10432; unreadable: 0; malformed files: 0; invalid class-ID rows: 0; empty: 0; duplicate extra rows: 0.
UTF-8 is decoded strictly (optional BOM accepted); blank lines are ignored. Class IDs must parse with int(), so decimal/scientific class tokens are invalid. Malformed-file counts cover unreadable text, field counts, nonnumeric/nonfinite fields, and class IDs; geometry is reported separately. Duplicates mean identical whitespace-separated tokens; different numeric spellings are not silently equated. Empty labels are flagged but do not establish negative-image identity.

## Bounding-box validity

Invalid annotation rows (any row-level error): 0; normalized out-of-range rows: 0; derived boxes outside frame: 1809; zero/negative dimensions: 0.
Corners use the existing YOLO-to-corners helper in normalized space, so the check also applies to orphan labels. Every outside corner is flagged; excess <=1e-6 is a warning for possible decimal-rounding effects, larger excess is an error. No clipping or correction is applied. Multiple issue rows can refer to one annotation.

## Pairing anomalies

Exact pairs: 10411; images without labels: 712; orphan labels: 21; inventory discrepancies: 0.
Statuses come from the existing audit CSVs; no pairing conclusions are recomputed or overwritten. Missing/extra files are separately flagged as inventory drift. image_without_label does not mean negative.

## Human-triaged orphan labels

Existing outcomes: {"manual_review_plausible": 5, "no_valid_match_in_reviewed_top5": 10, "rejected": 2, "unresolved_hold": 4}.
All orphan statuses are included in label_validation.csv. See ../orphan_review/final_triage_summary.csv and ../orphan_review/human_triage_decisions.csv for complete decisions. No plausible preference is a confirmed mapping. Manifest human_triage_outcome is a JSON array of candidate-review references from the existing index, not an annotation linkage. Candidate image label paths remain blank when no exact label exists.

## Unresolved negative-image identity

The supplied published total is 691 negative/no-defect images. 712 unlabeled images minus 21 orphan labels equals 691, but the relationship remains unproven. None is classified as negative here.

## Class statistics

Class IDs/names use the authoritative local archives/classes.txt line ordering. Annotation instances count every five-field row with a valid class-ID token, including duplicates and rows with coordinate errors. valid_annotation_instances excludes rows with errors. Images containing a class count distinct existing audit exact-pair filenames only; orphan annotations contribute instances but no inferred images.

| Split | ID | Class | Instances | Valid instances | Orphan instances | Images |
|---|---:|---|---:|---:|---:|---:|
| train | 0 | Crack | 3883 | 3883 | 6 | 1627 |
| train | 1 | Breakage | 13417 | 13417 | 19 | 5546 |
| train | 2 | Comb | 4956 | 4956 | 4 | 2767 |
| train | 3 | Hole | 930 | 930 | 2 | 689 |
| train | 4 | Reinforcement | 10658 | 10658 | 46 | 3064 |
| train | 5 | Seepage | 3871 | 3871 | 6 | 1590 |
| valid | 0 | Crack | 366 | 366 | 0 | 146 |
| valid | 1 | Breakage | 2141 | 2141 | 0 | 765 |
| valid | 2 | Comb | 479 | 479 | 0 | 302 |
| valid | 3 | Hole | 230 | 230 | 0 | 108 |
| valid | 4 | Reinforcement | 1335 | 1335 | 0 | 334 |
| valid | 5 | Seepage | 379 | 379 | 1 | 167 |
| test | 0 | Crack | 404 | 404 | 0 | 150 |
| test | 1 | Breakage | 3628 | 3628 | 0 | 857 |
| test | 2 | Comb | 281 | 281 | 0 | 139 |
| test | 3 | Hole | 69 | 69 | 0 | 55 |
| test | 4 | Reinforcement | 1381 | 1381 | 0 | 389 |
| test | 5 | Seepage | 123 | 123 | 0 | 59 |

## Resolution statistics

Unique decoded resolutions: 85; unusual-resolution images: 116.
Heuristic warnings: minimum dimension <256, maximum >10000, aspect ratio outside [0.2,5], or fewer than 10 examples at that resolution. Rarity is not corruption. All resolutions are in resolution_statistics.csv.

| Width | Height | Count |
|---:|---:|---:|
| 5184 | 3888 | 3989 |
| 4608 | 3456 | 3381 |
| 1600 | 1200 | 778 |
| 2736 | 1824 | 691 |
| 2048 | 1536 | 453 |
| 5152 | 3864 | 261 |
| 4000 | 3000 | 233 |
| 1088 | 816 | 158 |
| 480 | 320 | 147 |
| 3456 | 2304 | 110 |
| 3888 | 5184 | 90 |
| 4000 | 2248 | 72 |
| 6000 | 4000 | 72 |
| 6000 | 3376 | 61 |
| 2592 | 1944 | 60 |

## Manifest and remaining work

Manifest: data/manifests/gyu_det_v3_raw_manifest.csv (11123 image rows). Parquet: not generated: pyarrow not installed; no dependency added.
Manifest validation_status aggregates image and paired-label diagnostics plus an unlabeled-image warning. Absent annotation_count is blank, not zero. Orphan labels are not inserted as image rows. Quality warnings do not authorize removal, correction, or negative classification.
Human intervention is required for unresolved pairing/negative identity and any reported annotation or integrity errors before a training-data policy is accepted. This pass does not create training data.
