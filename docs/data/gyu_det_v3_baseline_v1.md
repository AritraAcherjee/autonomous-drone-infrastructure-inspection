# Approved GYU-DET baseline-v1 split specification

Baseline-v1 is a detector-training dataset specification, not a modification of the source dataset. It contains manifests and image-reference lists only. No images or labels are copied, linked, rewritten or repaired. M1 remains incomplete; no model has been trained.

## Approved inventory and exclusions

Raw GYU-DET v3 contains 11,123 images and 10,432 label files: 10,411 exact pairs, 712 unlabeled/unclassified images and 21 orphan labels. Baseline-v1 retains 10,398 supervised samples: train 8,305; valid 1,040; test 1,053, with 48,392 annotations. Every included image preserves its original split.

The 725 excluded raw images comprise 712 UNCLASSIFIED images, ten members of five conflicting-annotation exact-duplicate groups, two redundant equivalent duplicates and one image excluded for the conservative scene constraint. All 21 orphan labels are excluded separately; confirmed mappings remain zero. No negative identities are inferred from the published 691 total or from absent labels.

The human approves excluding both members of each conflict group for baseline-v1: train 4476.JPG/4631.JPG, 3852.JPG/4263.JPG, 139.JPG/183.JPG; valid 9228.jpg/9229.jpg, 9219.jpg/9220.jpg. These groups are resolved for baseline-v1 by exclusion, not annotation adjudication. No annotation is selected as better, merged or transferred. The original duplicate_annotation_consistency.csv under outputs/validation/gyu_det_v3/baseline_split remains unchanged for future study. The finalized exclusion reason explicitly records the approval; the dry-run evidence remains historical.

Equivalent duplicates retain train/10245.jpg and valid/11989.jpg; train/11150.jpg and train/9838.jpg are excluded. The conservative unresolved group retains test/12582.jpg and excludes train/11334.jpg; it is still not confirmed leakage. train/11727.jpg is retained, while valid/11985.jpg remains excluded/unclassified. Approved scene groups and SHA-identical content cannot cross retained splits. No labels are transferred. Rejected perceptual candidates introduce no grouping constraints.

## Warning and class policy

Readable primary images with MPO auxiliary-frame warnings remain eligible. The prior full validation reported 565 such raw-image warnings. Boundary overshoots <=1e-6 remain rounding warnings and are not clipped. The raw class IDs remain unchanged:

| ID | Source name | Presentation name |
|---:|---|---|
| 0 | Crack | Crack |
| 1 | Breakage | Breakage |
| 2 | Comb | Honeycombing |
| 3 | Hole | Hole |
| 4 | Reinforcement | Exposed Reinforcement |
| 5 | Seepage | Seepage |

## Portable reader paths

List entries use forward slashes and start with ./../../../raw/, relative to data/processed/gyu_det_v3_baseline_v1/splits/. This list-local representation remains valid after relocating the whole repository. Each resolves into the original raw images directory. The sibling labels path replaces the last images directory segment with labels and uses the exact image stem plus .txt. All 10,398 associations are asserted against the validated manifest, including case-preserved filenames.

The YAML uses JSON syntax, a valid YAML subset, and deliberately omits path. Its train/val/test entries are relative to the YAML directory. Pass an ABSOLUTE YAML filename to the planned Ultralytics workflow (e.g. str(Path('configs/data/gyu_det_v3_baseline_v1.yaml').resolve()) from the repository). This avoids dependence on global dataset-directory settings. Numeric IDs are retained through the names mapping. No download directive or model reference is present.

Reader semantics were checked against official [list loading](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/data/base.py) and [label/path resolution](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/data/utils.py). The equivalent assertions do not claim that the actual Ultralytics dataset decoder has run. Its installed/not-installed smoke-test result is recorded in manifest_metadata.json. Image hashes and box statistics are reused from validated artifacts; all paired label hashes are checked read-only before finalization.

## Reproduction and remaining training prerequisites

Run from the existing repository:

```powershell
python scripts/data/finalize_gyu_baseline_v1.py
python scripts/data/finalize_gyu_baseline_v1.py --check-reproducibility
python -m unittest discover -s tests/data -v
```

The reproducibility check writes metadata-only trees in two clean temporary directories and compares every byte. VERSION.json records source/final manifest hashes, the policy version, class mapping, exclusions and leakage constraints. No timestamps or machine-specific absolute paths enter the reproducible specification.

The conflict exclusions no longer block baseline-v1 approval. Before actual detector training, validate the selected installed reader, particularly MPO primary decoding, and ensure its cache/verification behavior cannot write into data/raw. Standard training-reader verification can create label caches or attempt image repair; a read-only raw mount or an explicitly controlled reader/cache policy is required for that later workflow. This task does not run that workflow, download weights or install Ultralytics. Source-image hashes are reused rather than re-reading the full image dataset. Unclassified-image and orphan limitations remain documented; those samples stay outside this supervised baseline. All prior human decisions and raw files remain immutable.
