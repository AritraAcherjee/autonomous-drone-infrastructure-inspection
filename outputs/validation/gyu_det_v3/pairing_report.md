# GYU-DET V3 pairing audit

## Method and reproduction

Run from the repository root (Python 3.10+, standard library only):

```text
python scripts/data/audit_gyu_pairing.py --root data/raw/gyu_det/v3/extracted --output outputs/validation/gyu_det_v3
python -m unittest discover -s tests/data -v
```

Directories: `<root>/<split>/<split>/{images,labels}` for train, valid, test. Independent, non-recursive enumeration. Image extensions: .bmp, .jpeg, .jpg, .png, .tif, .tiff, .webp; labels: .txt (case-insensitive).
Pairing keys are whitespace-trimmed, case-folded filename stems. Original names are retained. Exact means equal normalized stems. Only unique one-to-one keys count as matched pairs; duplicate keys with a counterpart are ambiguous and never arbitrarily paired.

## Pairing counts

| Split | Images | Labels | Exact pairs | Images without labels | Orphan labels | Ambiguous images / labels |
|---|---:|---:|---:|---:|---:|---:|
| train | 8898 | 8334 | 8314 | 584 | 20 | 0 / 0 |
| valid | 1112 | 1045 | 1044 | 68 | 1 | 0 / 0 |
| test | 1113 | 1053 | 1053 | 60 | 0 | 0 / 0 |

## Negative images and unresolved missing annotations

There are 712 images without same-split labels. Expected negatives supported by external evidence: 0; unexplained missing labels: 712.
There are 0 unique matched pairs with empty/whitespace-only annotations. These encode no boxes and are consistent with negative examples; this audit does not visually verify no-defect status.
The published total supplied for this audit is 691 negative/no-defect images. The current raw pairing discrepancy requires further investigation before all unlabeled images can be classified as intentional negatives. An aggregate total does not identify individual negatives. The CLI supplies no external negative manifest; the reusable validator accepts an explicit evidence-backed expected_negatives set.

## Orphan labels and cross-split exact matches

Orphan labels with exact images in another split: 0. Unmatched images with exact labels in another split: 0.
Cross-split matches do not repair the local split. Every matching filename and split is retained as JSON in the unmatched CSVs.

## Filename-similarity candidates

Top 10 candidates per orphan are emitted separately for same_split and all_splits. Rank order: ascending Levenshtein distance, descending similarity (1 - distance / maximum stem length), ascending absolute numeric difference when both stems are ASCII digits, then train/valid/test order and original filename. Ranks use unrounded similarity; CSV similarity is rounded to 8 decimal places. Numeric difference is blank for nonnumeric stems. Similarity is diagnostic only; no candidate is automatically paired or renamed.

| Label split | Orphan label | Exact image elsewhere | Best same-split image | Best all-splits image | Distance / similarity / numeric difference (all) |
|---|---|---|---|---|---|
| train | 111.txt | [] | train/1011.JPG | train/1011.JPG | 1 / 0.75 / 900 |
| train | 112.txt | [] | train/1012.JPG | train/1012.JPG | 1 / 0.75 / 900 |
| train | 1264.txt | [] | train/10264.jpg | train/10264.jpg | 1 / 0.8 / 9000 |
| train | 1458.txt | [] | train/10458.jpg | train/10458.jpg | 1 / 0.8 / 9000 |
| train | 1554.txt | [] | train/10554.jpg | train/10554.jpg | 1 / 0.8 / 9000 |
| train | 1564.txt | [] | train/10564.jpg | train/10564.jpg | 1 / 0.8 / 9000 |
| train | 1800.txt | [] | train/10800.jpg | train/10800.jpg | 1 / 0.8 / 9000 |
| train | 190.txt | [] | train/1090.JPG | train/1090.JPG | 1 / 0.75 / 900 |
| train | 1959.txt | [] | train/10959.jpg | train/10959.jpg | 1 / 0.8 / 9000 |
| train | 237.txt | [] | train/2237.JPG | train/2237.JPG | 1 / 0.75 / 2000 |
| train | 238.txt | [] | train/2038.JPG | train/2038.JPG | 1 / 0.75 / 1800 |
| train | 314.txt | [] | train/1314.JPG | train/1314.JPG | 1 / 0.75 / 1000 |
| train | 3763.txt | [] | train/3765.JPG | train/3765.JPG | 1 / 0.75 / 2 |
| train | 4047.txt | [] | train/4048.JPG | train/4048.JPG | 1 / 0.75 / 1 |
| train | 4626.txt | [] | train/4625.JPG | train/4625.JPG | 1 / 0.75 / 1 |
| train | 4923.txt | [] | train/4922.JPG | train/4922.JPG | 1 / 0.75 / 1 |
| train | 574.txt | [] | train/1574.JPG | train/1574.JPG | 1 / 0.75 / 1000 |
| train | 664.txt | [] | train/1664.JPG | train/1664.JPG | 1 / 0.75 / 1000 |
| train | 728.txt | [] | train/1728.JPG | train/1728.JPG | 1 / 0.75 / 1000 |
| train | 7972.txt | [] | train/7971.JPG | train/7971.JPG | 1 / 0.75 / 1 |
| valid | 9156.txt | [] | valid/9155.JPG | valid/9155.JPG | 1 / 0.75 / 1 |

## Duplicates and 5774 regression

Duplicate filename rows: 0. See duplicate_basenames.csv.
5774 regression matches: [{"empty_annotation": false, "image_filename": "5774.JPG", "label_filename": "5774.txt", "normalized_basename": "5774", "split": "train"}]

## Output integrity and limitations

SHA-256 hashes identify the generated CSVs. Unchanged input produces identical outputs. This is a filename audit, not box-format, image-content, or provenance validation. Raw files are read only. M1 remains incomplete.

- `pairing_summary.csv`: `b81aa80ea1995f9940b1e749366d7fcfde918599a605334132fc8674eb110532`
- `unmatched_labels.csv`: `d57ce2fbbcf542b6a948a172d7138fa19be6054baefcd6d42e04e4144f6c2715`
- `unmatched_images.csv`: `8cdf863c3aabee243c4fd08bd92eb245d8405a8ffad1161381a3a40fc34c279b`
- `pairing_candidates.csv`: `561f0c1fc8f8d7da6d97b2c6950c8600430b8fef0cace950480cb42c06010a69`
- `duplicate_basenames.csv`: `ef017828a41d6614177bba807a4ee6a3f5f7b5e244db18cfd4b39f49a906486b`
- `matched_pairs.csv`: `68e7856fa6c4a826b9320ea48a0f2e03ea05445ecc9ecccd0780f20ae7a62a9d`
