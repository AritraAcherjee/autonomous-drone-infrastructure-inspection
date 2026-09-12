# GYU-DET V3 source and provenance

## SOURCE FACTS

Official title: **GYU-DET**. Repository: **Science Data Bank**. Authors: Linchang Zhao and Ruiping Li. Dataset DOI: https://doi.org/10.57760/sciencedb.19893. Acquired source version: **V3**. Associated paper: *Multi-defect type beam bridge dataset: GYU-DET*, https://doi.org/10.1038/s41597-025-05395-w.

The [official landing page](https://www.scidb.cn/en/detail?dataSetId=68827df9f367442c8be0c283e60ed3b7) is currently public and lists V3 in History. Select V3 explicitly: it displays CC BY-NC-SA 4.0, whereas the default V4 displays CC BY 4.0. The paper separately displays CC BY-NC-ND 4.0. Availability here means the record/file listings were accessible, not a fresh bulk-download test.

### Acquired files and verified MD5

| Source file | MD5 | Local size, bytes |
|---|---|---:|
| classes.txt | F078630BF0D0614B07C9DC990DA40801 | 53 |
| test.zip | 522A80C18CAA4A0030D7FFC9DDFA98B2 | 4,594,004,450 |
| train.zip | A8AAD1CC02E86C4857B8315EE9F1606E | 31,892,320,387 |
| valid.zip | D8EBE9C38D9D4D05DD9CFFB50A692086 | 4,220,930,256 |

These are the user-verified acquisition hashes, independently matched to the official V3 listings during this pass. The 53-byte classes.txt was rehashed locally; the three large archives were not rehashed again. Their local compressed total is 40,707,255,093 bytes, approximately 40.71 decimal GB / 37.91 GiB. MD5 is retained as the source's acquisition checksum, not substituted for the SHA-256 provenance of project manifests.

Raw local root: `data/raw/gyu_det/v3/`. Files live under `archives/`; extraction is under `extracted/`:

```text
train/train/images/    train/train/labels/
valid/valid/images/    valid/valid/labels/
test/test/images/      test/test/labels/
```

The source supplies original train/valid/test archives. Images are visible-light RGB bridge-surface imagery; labels use YOLO TXT rows: `class_id x_center y_center width height`, with normalized coordinates. The authoritative local order is `data/raw/gyu_det/v3/archives/classes.txt`:

| ID | Raw source class | AegisInspect presentation name |
|---:|---|---|
| 0 | Crack | Crack |
| 1 | Breakage | Breakage |
| 2 | Comb | Honeycombing |
| 3 | Hole | Hole |
| 4 | Reinforcement | Exposed Reinforcement |
| 5 | Seepage | Seepage |

Numeric IDs and raw labels are unchanged. Presentation names are derived project terminology, not a source relabeling.

## AEGISINSPECT-DERIVED VALIDATION FINDINGS

| Original split | Images | Labels | Exact pairs | Unlabeled/unclassified | Orphan labels |
|---|---:|---:|---:|---:|---:|
| train | 8898 | 8334 | 8314 | 584 | 20 |
| valid | 1112 | 1045 | 1044 | 68 | 1 |
| test | 1113 | 1053 | 1053 | 60 | 0 |
| total | 11123 | 10432 | 10411 | 712 | 21 |

All 11,123 primary images decode. There are 565 auxiliary MPO-frame warnings, no malformed label files, invalid annotation rows, invalid class IDs or nonpositive boxes. Normalized corner overshoots <=1e-6 remain rounding warnings. Baseline-v1 contains 10,398 supervised images and 48,392 instances after approved exclusions; no orphan repair is confirmed and absent labels do not identify negative images. Original splits and raw bytes are not rewritten.

Evidence: `outputs/validation/gyu_det_v3/full_validation/validation_report.md`, `data/manifests/gyu_det_v3_raw_manifest.csv`, `outputs/validation/gyu_det_v3/M1_EVIDENCE_INDEX.md`. Approved specification: `data/manifests/gyu_det_v3_baseline_v1/` and `docs/data/gyu_det_v3_baseline_v1.md`. Machine-readable source record: `data/manifests/gyu_det_v3_source_provenance.json`.

## Citation instructions

Cite the dataset with its used version: Zhao, L. and Li, R. (2025), *GYU-DET*, V3, Science Data Bank, https://doi.org/10.57760/sciencedb.19893. If using the repository citation exporter, select V3 first.

Also cite the associated methodology paper: Li, R., Zhao, L., Wei, H. et al. (2025), *Multi-defect type beam bridge dataset: GYU-DET*, Scientific Data 12, 1101, https://doi.org/10.1038/s41597-025-05395-w. Describe AegisInspect baseline-v1 exclusions separately and preserve source attribution and license links. These derived findings are not claimed as original dataset-author assertions.
