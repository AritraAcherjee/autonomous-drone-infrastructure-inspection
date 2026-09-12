# GYU-DET M1 handoff — Chat 03 / Defect Detection

**Approved dataset: GYU-DET V3 baseline-v1.** This handoff closes the GYU-DET data-foundation evidence package only. The overall multi-dataset AegisInspect M1 milestone is not complete. No detector has been trained.

| Split | Supervised images |
|---|---:|
| Train | 8,305 |
| Valid | 1,040 |
| Test | 1,053 |
| Total | 10,398 |

**Annotation instances: 48,392.**

Configuration: `configs/data/gyu_det_v3_baseline_v1.yaml`.
Manifests: `data/manifests/gyu_det_v3_baseline_v1/` (train.csv, valid.csv, test.csv, excluded.csv, excluded_orphan_labels.csv, statistics, VERSION.json and manifest_metadata.json).

Split lists:
- `data/processed/gyu_det_v3_baseline_v1/splits/train.txt`
- `data/processed/gyu_det_v3_baseline_v1/splits/valid.txt`
- `data/processed/gyu_det_v3_baseline_v1/splits/test.txt`

| ID | Raw class | Approved presentation name |
|---:|---|---|
| 0 | Crack | Crack |
| 1 | Breakage | Breakage |
| 2 | Comb | Honeycombing |
| 3 | Hole | Hole |
| 4 | Reinforcement | Exposed Reinforcement |
| 5 | Seepage | Seepage |

## Data characteristics and constraints

Prior EDA describes the 10,411 original exact pairs, before baseline-v1 exclusions: Breakage dominates, Hole is rarest, instance imbalance approximately 15.62:1. Tiny boxes are approximately 9.52%, small 33.09%, medium 41.87%, large 15.52%; relative-area boundaries are 0.001, 0.01 and 0.1. Median annotations/image is 4; multi-class rate is approximately 57.03%. There are 85 source resolutions. These prior-EDA summaries are not silently presented as recomputed baseline-v1 percentages.

Test has a notably higher Breakage instance share, higher annotation density, larger source images and somewhat smaller median relative boxes than train. Per-class and size-aware evaluation should retain this distribution context; no performance claim follows from EDA alone.

Leakage handling is complete for the approved specification: retain valid/11989.jpg and exclude train/9838.jpg; retain train/11727.jpg while valid/11985.jpg remains unlabeled/excluded; retain test/12582.jpg and exclude train/11334.jpg under the conservative unresolved group. No SHA-identical content or approved grouping crosses included splits. Equivalent duplicates retain train/10245.jpg over train/11150.jpg. All ten conflicting-annotation duplicate members are excluded by human approval for baseline-v1; their evidence is preserved without annotation adjudication.

All 21 orphan labels are excluded; no repair mappings are confirmed. All 712 unlabeled images remain UNCLASSIFIED and excluded, not known negatives. In total, 725 raw images are excluded; the 21 orphan labels are counted separately. Do not infer or train a background-negative subset from those unknown identities.

565 source images had auxiliary MPO-frame validation warnings but readable primary JPEG frames. These are not automatically removed; the installed training reader still needs validation. Derived normalized corner overshoots <=1e-6 are retained as rounding warnings; raw labels are not clipped. Numeric class IDs are unchanged.

`data/raw/` is immutable. Dataset V3 license: **CC BY-NC-SA 4.0**. Treat this baseline as non-commercial unless appropriate separate permission exists. The article's CC BY-NC-ND 4.0 license is distinct. See the source/version-specific licensing record; raw archives must not be redistributed through Git.

## Pre-training gate — intentionally owned by Defect Detection

1. Select/install the actual detector environment in that workstream. Ultralytics is not installed in the current M1 environment and was not installed for this task.
2. Verify the installed reader loads every included image, particularly the MPO-tagged subset.
3. Prevent repair or rewriting of source images, and route/control label and image caches so `data/raw/` cannot be modified.
4. Run a no-training dataset-loader smoke test; no augmentation/training or weight download is part of this M1 handoff.
5. Assert the loader counts are exactly 8305 / 1040 / 1053 and all six IDs map to the approved names above.
6. Only after that gate passes may detector training begin under the workstream's authorization.

This intentionally deferred reader gate is not an unresolved GYU-DET M1 data-foundation blocker. No unlabeled/orphan recovery or additional split construction is required for this approved first baseline.

## Interface and read-only verification

From the repository:

```python
from pathlib import Path

DATA_CONFIG = Path(
    "configs/data/gyu_det_v3_baseline_v1.yaml"
).resolve()
```

Pass the absolute YAML path to the chosen framework. The YAML is valid JSON-form YAML with paths relative to its directory; lists use portable list-local ./../../../raw/ references. See `docs/data/gyu_det_v3_baseline_v1.md`. All 10,398 path-to-label associations already pass equivalent reader assertions; that is not an installed-reader decode test.

Read-only checks: `python scripts/data/check_gyu_m1.py`; tests: `python -m unittest discover -s tests/data -v`. Do not re-run split construction to consume the baseline. Prior finalization produced byte-identical artifacts in two clean temporary locations; current verification checks the retained hashes without regeneration.

Audit trail: `outputs/validation/gyu_det_v3/M1_EVIDENCE_INDEX.md`. Source provenance: `data/manifests/gyu_det_v3_source_provenance.json`. Scope completion means GYU-DET data foundation only, never all of M1 or detector-reader readiness.
