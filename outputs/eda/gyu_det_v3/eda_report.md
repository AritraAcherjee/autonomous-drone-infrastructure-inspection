# GYU-DET V3 exploratory data analysis

M1 remains incomplete. This is a complete-inventory EDA, not a processed dataset or a training run.

## Scope and reproducibility

Two views are explicit in dataset_overview.csv: RAW_VALIDATED_INVENTORY includes all images and separately identified orphan annotation instances; PROVISIONAL_BASELINE_ELIGIBLE contains exact image-label pairs only. All box, class-prevalence, density and co-occurrence statistics use exact pairs. The provisional view does not exclude reviewed leakage groups or readable MPO primary images. No samples have been removed.

Image metadata is reused from the manifest and full validation. No raw image is opened or decoded. All label bytes are checked against their existing validation SHA-256 before the shared YOLO parser reads geometry. Input hashes, package versions and output inventory are recorded in eda_summary.json. Image byte hashes are reused, not recomputed; therefore this analysis assumes raw image content remains unchanged since validation.

Install the recorded versions with `python -m pip install -r scripts/data/requirements-gyu-eda.txt`, then run from the repository: `python scripts/data/eda_gyu_det.py`. Dependencies: NumPy, Pillow (shared parser import) and Matplotlib; no seaborn. Deterministic ordering, linear-interpolated NumPy percentiles, no random sampling and no run timestamps are used. PNG reproducibility assumes the recorded plotting/runtime versions and fonts.

## Dataset and classes

Analyzed 10,411 exact-pair images with 48,447 instances. The 21 orphan labels contain 84 additional instances, never assigned to supervised images. The 712 unlabeled images have unknown annotation status; they are not counted as zero-box images.

| Class | Exact-pair instances | Orphan instances | Images containing class | % exact pairs |
|---|---:|---:|---:|---:|
| Crack | 4,647 | 6 | 1,923 | 18.47 |
| Breakage | 19,167 | 19 | 7,168 | 68.85 |
| Comb | 5,712 | 4 | 3,208 | 30.81 |
| Hole | 1,227 | 2 | 852 | 8.18 |
| Reinforcement | 13,328 | 46 | 3,787 | 36.37 |
| Seepage | 4,366 | 7 | 1,816 | 17.44 |

Breakage dominates instance counts; Hole is rarest. The majority/minority instance ratio is 15.62:1. Instance balance and image prevalence differ because multiple boxes can share a class in one image.

## Annotation density and co-occurrence

Per exact-pair image: mean 4.65, median 4, minimum 1, maximum 72. 57.03% of exact-pair images contain multiple defect classes; 4,474 contain one class. annotation_count_examples.csv identifies the 30 densest images.

Most common class combinations (single-class combinations included):

- Breakage: 2,232 images (21.44%).
- Breakage + Reinforcement: 1,433 images (13.76%).
- Comb: 687 images (6.60%).
- Breakage + Comb: 683 images (6.56%).
- Breakage + Comb + Reinforcement: 634 images (6.09%).

The raw 6x6 matrix counts images, not pairs of boxes. The normalized matrix is P(column class present | row class present); its diagonal is 1 for observed classes and its rows need not sum to 1. Multi-defect scenes suggest checking augmentation effects jointly across classes.

## Box geometry and small objects

Relative area categories are descriptive, not COCO pixel-area categories: tiny <0.001 (0.1%); small [0.001,0.01); medium [0.01,0.1); large >=0.1. These order-of-magnitude intervals compare scenes with different resolutions. Relative image area and normalized area are identical.

Median normalized area is 0.0143187. tiny 9.52%; small 33.09%; medium 41.87%; large 15.52%.

Pixel aspect ratio uses pixel width / pixel height; normalized aspect ratio is separately retained. A border box has any edge within 0.01 normalized units of a frame boundary, including overshoots. Extreme aspect ratios are <0.1 or >10. Measurements retain original geometry without clipping. box_examples.csv lists the 20 smallest/largest relative-area boxes and every border, extreme-ratio and rounding-warning box.

Exact-pair boxes: 13,468 near borders, 1,388 extreme aspect ratios, 1,808 boundary rounding warnings. The full validated label inventory has 1,809 overshoot warnings <=1e-6; one belongs to an orphan label. Orphan boxes are not silently mixed into exact-pair box distributions.

Small relative boxes can lose pixel detail when resized for YOLO. Before choosing input resolution, inspect their post-letterbox pixel dimensions at candidate sizes; relative area alone does not establish visibility. Larger inputs or tiles are hypotheses to evaluate later, with scene groups kept together and border/crop effects tracked. Extreme thin boxes make aggressive downscaling and geometric transforms especially worth checking.

## Resolution and original split differences

There are 85 unique stored resolutions. Rare means fewer than 10 images in the stated view/split; rarity is descriptive and not an exclusion rule. Width, height, megapixel and aspect quantiles are in image_statistics.csv. Major groups:

- 5184 x 3888: 3,989 images (35.86%).
- 4608 x 3456: 3,381 images (30.40%).
- 1600 x 1200: 778 images (6.99%).
- 2736 x 1824: 691 images (6.21%).
- 2048 x 1536: 453 images (4.07%).

| Split | Pairs | Instances | Mean boxes/image | Median box area | Median MP (raw) |
|---|---:|---:|---:|---:|---:|
| train | 8314 | 37632 | 4.53 | 0.01462 | 15.925 |
| valid | 1044 | 4929 | 4.72 | 0.01574 | 15.925 |
| test | 1053 | 5886 | 5.59 | 0.01227 | 20.155 |

Notable differences are descriptive flags, not significance tests: instance-share or resolution-share range >=5 percentage points, or largest/smallest nonzero split median/mean >=1.25.

- Breakage instance shares: train 35.60%, valid 43.44%, test 61.64%.
- Comb instance shares: train 13.16%, valid 9.72%, test 4.77%.
- Seepage instance shares: train 10.27%, valid 7.67%, test 2.09%.
- median_normalized_box_area: train 0.01462, valid 0.01574, test 0.01227.
- median_megapixels: train 15.93, valid 15.93, test 20.16.
- Resolution 2736x1824 raw image shares: train 7.59%, valid 1.35%, test 0.09%.
- Resolution 4608x3456 raw image shares: train 33.41%, valid 22.30%, test 14.38%.
- Resolution 5184x3888 raw image shares: train 31.71%, valid 45.50%, test 59.39%.

Variation in image scale can change effective defect size after letterboxing. Preserve aspect ratio and assess candidate input sizes against both small-box dimensions and computational cost. Augmentation experiments should preserve defect semantics: check that crops do not erase tiny reinforcement/hole targets and that geometry or photometric changes remain physically plausible. No augmentation configuration or input size is approved by this EDA.

## Evaluation and data-quality limitations

Class imbalance motivates reporting per-class precision/recall and AP alongside aggregate mAP, plus size-stratified errors and sample support. Rare-class estimates may be unstable; co-occurring defects and scene families reduce independence. These are implications inferred from the inventory, not model-performance claims.

All 21 orphan labels were human triaged, with zero confirmed mappings and no repair authorization. Plausible candidates remain unconfirmed. The 712 unlabeled images remain UNCLASSIFIED; the supplied 691 negative/no-defect total cannot identify intentional negatives by subtraction. Background-only evaluation and false-positive estimates remain limited until negative identity is resolved.

Leakage review retains its approved decisions: one confirmed exact cross-split duplicate, one high-confidence near duplicate, one conservative unresolved same-scene group and 14 rejected perceptual candidates. Future processed splits must keep each of the three groups together (or an approved representative for exact/high-confidence groups); unresolved is not confirmed leakage. No member is removed here.

- Exact: train/9838.jpg with valid/11989.jpg.
- High-confidence: train/11727.jpg with valid/11985.jpg.
- Conservative unresolved: train/11334.jpg with test/12582.jpg.

Full validation found 565 MPO auxiliary-frame failures while all 11,123 primary images decoded. These remain warning-only under the provisional policy; eventual training-reader compatibility remains to be established. Raw geometry, official splits, prior human decisions and data/raw remain unchanged. No final processed training dataset exists from this pipeline.

## Outputs

See output_inventory.csv for every generated relative path and purpose; figures/ contains nine 220-DPI PNGs. All box tables and figures refer to PROVISIONAL_BASELINE_ELIGIBLE unless explicitly marked raw. Class tables expose orphan counts separately, never as supervised image counts.
