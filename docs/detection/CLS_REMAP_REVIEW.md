# Class remap review and pipeline freeze

Task: [L1][CHAT-02] Verify class remap semantics and freeze training pipeline.

CLS_REMAP REVIEW = PASS. Classification **A: identity-preserving dataset IDs**.
The installed Ultralytics 8.4.145 flag enables matching pretrained classification
head weight rows to target class names. It never changes numeric annotations.
It is active configuration, not dead code. With the selected COCO checkpoint,
none of the six names match, so the conditional weight-row copying does nothing.
The separate model construction still changes the output count from 80 to six.

## Exact trace

Paths below are relative to
`C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection`.
Installed-package paths are under `.venv-detection/Lib/site-packages/`.

| Path and line | Function / behavior |
| --- | --- |
| `configs/detection/det_baseline.yaml:43` | Explicit `training.cls_remap: true`. The smoke overlay inherits it. |
| `src/detection/training/config.py:27` | `REQUIRED` requires the field. |
| `src/detection/training/config.py:35` | `load_config` parses YAML, copies it, applies only explicit smoke overrides, calls `validate_config`. |
| `src/detection/training/config.py:68` | `validate_config` checks required fields; it does not independently constrain the flag's boolean value. Installed argument validation handles its type. `single_cls` must be false. |
| `src/detection/training/config.py:123` | `load_development_data` checks exact approved YAML, class names and development manifest/list hashes. |
| `src/detection/training/trainer.py:74` | `training_arguments` forwards the training dictionary unchanged, including `cls_remap`. |
| `src/detection/training/trainer.py:83` | `trainer_class` supplies `GuardedDetectionTrainer`, inheriting the installed `DetectionTrainer`. |
| `src/detection/training/trainer.py:103` | `build_dataset` supplies `single_cls=False`, `classes=None`, and the approved names to `ReadOnlyDetectionDataset`. |
| `src/detection/training/trainer.py:178` | `run` enumerates `CLASSES` in original order into `data.names`; `nc=6`. |
| `src/detection/training/dataset.py:46` | `get_labels` validates labels read-only and copies `values[:, :1]` directly to `cls`; boxes occupy separate columns. |
| `ultralytics/cfg/default.yaml:26` | Installed `cls_remap` definition describes pretrained class-head row matching. |
| `ultralytics/cfg/__init__.py:307` | `CFG_BOOL_KEYS` includes `cls_remap`; `get_cfg` validates its type. |
| `ultralytics/models/yolo/detect/train.py:149` | `set_model_names_for_load` attaches target names before weight loading when the flag is true. |
| `ultralytics/models/yolo/detect/train.py:186` | `get_model` constructs `DetectionModel(..., nc=self.data['nc'])`, binds names, then loads pretrained weights. |
| `ultralytics/models/yolo/detect/train.py:139` | `set_model_attributes` preserves `data.names` and `data.nc` on the model. |
| `ultralytics/nn/tasks.py:312` | `BaseModel.load` invokes `_remap_cls_by_names`, then intersects compatible state-dict tensors. |
| `ultralytics/nn/tasks.py:344` | `_remap_cls_by_names` normalizes names using strip/lower, builds `src_lookup` and target-to-source `idx`. Only matching Detect `cv3` / `one2one_cv3` final classification weight/bias rows can be copied; zero matches returns immediately. No dataset object is involved. |
| `ultralytics/data/base.py:205` | `update_labels` can filter or collapse classes, but both options are disabled by the project builder. |
| `ultralytics/data/dataset.py:376` | `update_labels_info` converts box representation without class-ID remapping. |
| `ultralytics/data/dataset.py:409` | `collate_fn` concatenates class tensors without permuting IDs. |

Other repository occurrences before this review are recorded copies in smoke
`args.yaml`, `requested_config.json`, `resolved_config.json`, `provenance.json`,
and the implementation report's full configuration. They are evidence, not
additional transformations. The RT-DETR override of `_remap_cls_by_names` in
`ultralytics/nn/tasks.py:933` is not used by this YOLO26 detection model.

## No-training runtime proof

`outputs/validation/defect_detection/cls_remap_review/runtime_proof.json` records
the completed check. A deterministic synthetic label file outside raw contains
all six classes in deliberately unsorted order `[5, 0, 4, 1, 3, 2]`, with distinct
boxes. The actual project trainer's `build_dataset` preserves that exact sequence
in parsed training labels, pre-augmentation items, and formatted/collated validation
batches. The model and both datasets retain the exact names below.

| Source ID | Runtime ID | Runtime name |
| --- | --- | --- |
| 0 | 0 | Crack |
| 1 | 1 | Breakage |
| 2 | 2 | Honeycombing |
| 3 | 3 | Hole |
| 4 | 4 | Exposed Reinforcement |
| 5 | 5 | Seepage |

The already downloaded official `yolo26s.pt` was loaded on CPU, without training
or network access. Its SHA-256 is
`646f8bc3fe0a656803d95c294f7852321748cb29d13466a1af8862e2db384a1b`.
Its 80 source names yield target-to-pretrained indices `[-1, -1, -1, -1, -1, -1]`:
these are **unmatched pretrained weight rows**, not annotation IDs. Actual
`get_model` construction reported 80 -> 6 outputs and 696/708 transferred tensors.
The six-class model names remain in approved order. New final classification
outputs are initialized by the target model; compatible shared weights transfer.

The smoke therefore used original dataset IDs. No flag changes or runtime
refactor are needed. No new training, final-test content access, or CODEBRIM
access was performed for this review.

## Regression and evidence policy

Two focused tests in `tests/detection/test_training.py` freeze the identity and
name order through the project adapter and argument/name-binding path. Swapping
IDs 0/1, merging classes, or reordering the approved names fails these checks.
They require neither model downloads nor training; M1 tests are unchanged.

The `training_pipeline/before` test evidence is refreshed for the final reviewed
implementation, including the two new tests. The original smoke `after` evidence
and smoke reports retain their historical 74 detector / 112 M1 / 286 full counts.
Post-commit tests and readiness evidence are written outside tracked evidence to
`outputs/cache/cls_remap_postcommit/`, allowing an actually clean final checkout.
The final delivered review report records the resulting commit and fresh counts.

Raw verification compares all 21,559 inventoried file sizes/mtimes and rehashes
the same 320 development image/label files hashed by the smoke. Both comparison
against the smoke snapshot and before/after review comparison pass. This is not
a claim that final-test or archive contents were hashed. Approved manifests,
split lists, M1 preservation artifacts and raw source files remain unchanged.

Full DET-BASELINE remains unstarted. GO-CANDIDATE is a readiness recommendation;
Control Center must separately authorize any full training execution.
