# CHAT-02 detector training pipeline and smoke report

Task: **[L1][CHAT-02] Build reproducible GYU-DET baseline training pipeline and perform smoke training only**

Project: AegisInspect — Autonomous Multimodal Drone Inspection System. Machine: Laptop 1.

Repository: `C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection`

Branch: `chat02/detector-training`. Base and final HEAD: `origin/main @ 043ce54`
(`043ce54d40708c6bf278f8b07741c1e4afe9ccd6`). Initial working tree was clean. No commit, merge, full
training, DET-IMPROVED experiment or CODEBRIM use occurred.

## 1. Exact files changed

The following are modified/new versionable files, including concise generated
evidence. Ignored checkpoints, trainer plots/logs, library caches and raw snapshots
remain on disk under the controlled output roots and are listed separately below.
All paths in this report are relative to the repository unless written absolutely.

```text
.gitignore
configs/detection/det_baseline.yaml
configs/detection/det_baseline_smoke.yaml
docs/detection/BASELINE_TRAINING.md
docs/implementation_reports/detector_training_smoke.md
outputs/training/defect_detection/SMOKE-DET-BASELINE/args.yaml
outputs/training/defect_detection/SMOKE-DET-BASELINE/checkpoint_acquisition.json
outputs/training/defect_detection/SMOKE-DET-BASELINE/dataset_identity.json
outputs/training/defect_detection/SMOKE-DET-BASELINE/development_data.yaml
outputs/training/defect_detection/SMOKE-DET-BASELINE/provenance.json
outputs/training/defect_detection/SMOKE-DET-BASELINE/raw_immutability.json
outputs/training/defect_detection/SMOKE-DET-BASELINE/requested_config.json
outputs/training/defect_detection/SMOKE-DET-BASELINE/resolved_config.json
outputs/training/defect_detection/SMOKE-DET-BASELINE/results.csv
outputs/training/defect_detection/SMOKE-DET-BASELINE/run_evidence.json
outputs/training/defect_detection/SMOKE-DET-BASELINE/train.txt
outputs/training/defect_detection/SMOKE-DET-BASELINE/valid.txt
outputs/validation/defect_detection/exif_alignment/geometry.json
outputs/validation/defect_detection/exif_alignment/train_10029.png
outputs/validation/defect_detection/exif_alignment/train_10052.png
outputs/validation/defect_detection/exif_alignment/train_10117.png
outputs/validation/defect_detection/exif_alignment/train_10129.png
outputs/validation/defect_detection/exif_alignment/valid_12047.png
outputs/validation/defect_detection/exif_alignment/valid_8582.png
outputs/validation/defect_detection/exif_alignment/valid_8845.png
outputs/validation/defect_detection/exif_alignment/valid_8902.png
outputs/validation/defect_detection/training_pipeline/after/detector.xml
outputs/validation/defect_detection/training_pipeline/after/detector_tests.txt
outputs/validation/defect_detection/training_pipeline/after/full_tests.txt
outputs/validation/defect_detection/training_pipeline/after/m1_tests.txt
outputs/validation/defect_detection/training_pipeline/after/pytest_results.xml
outputs/validation/defect_detection/training_pipeline/after/ready.json
outputs/validation/defect_detection/training_pipeline/after/test_results.json
outputs/validation/defect_detection/training_pipeline/before/detector.xml
outputs/validation/defect_detection/training_pipeline/before/detector_tests.txt
outputs/validation/defect_detection/training_pipeline/before/full_tests.txt
outputs/validation/defect_detection/training_pipeline/before/m1_tests.txt
outputs/validation/defect_detection/training_pipeline/before/pytest_results.xml
outputs/validation/defect_detection/training_pipeline/before/ready.json
outputs/validation/defect_detection/training_pipeline/before/test_results.json
outputs/validation/defect_detection/training_pipeline/changed_files.txt
outputs/validation/defect_detection/training_pipeline/final_git_review.txt
outputs/validation/defect_detection/training_pipeline/model_inspection.json
outputs/validation/defect_detection/training_pipeline/smoke_summary.json
scripts/check_detector_training.py
scripts/train_detector.py
scripts/verify_detector_exif.py
src/detection/training/__init__.py
src/detection/training/config.py
src/detection/training/dataset.py
src/detection/training/exif.py
src/detection/training/provenance.py
src/detection/training/trainer.py
tests/detection/test_training.py
```

## 2. Selected baseline model

YOLO26 **small**, official `yolo26s.pt`, task `detect`, pretrained initialization.
Installed Ultralytics 8.4.145 model definitions, asset registry, and CPU model
construction were inspected without downloading weights. Parameter counts:
10,009,784 at 80 classes; 9,952,508 after configuring the six approved classes.
Small provides moderate training/inference cost for the RTX 4070 Laptop's 8GB VRAM.
The smoke transferred 696/708 items from official pretrained weights. No unrelated
checkpoint was downloaded. Supported package families/identifiers are recorded in
`outputs/validation/defect_detection/training_pipeline/model_inspection.json`.

## 3. Exact full DET-BASELINE configuration

The complete, version-controlled configuration is reproduced below. Fixed batch
**4** is the final intended baseline batch, supported by this smoke's memory
evidence. The resolved SGD uses Nesterov=true, dampening=0, nominal batch=64 and
16-batch gradient accumulation outside warmup. Weight decay applies to weight
groups, with zero decay on bias/normalization groups. LR decays linearly from
0.01 to 0.0001. Native BF16 is selected explicitly; the installed validator uses
its own AMP/FP16 validation path. Native save_period=10 is zero-indexed: periodic
files are epoch0.pt, epoch10.pt, ...; best and last are also retained.

```yaml
schema_version: 1
experiment:
  id: DET-BASELINE
  description: GYU-DET V3 baseline-v1 pretrained YOLO26s at 640; validation-only development.
model:
  family: YOLO26
  size: s
  checkpoint: yolo26s.pt
  pretrained: true
  task: detect
  cache_dir: outputs/cache/models/ultralytics/v8.4.0
data:
  yaml: configs/data/gyu_det_v3_baseline_v1.yaml
  identity: GYU-DET V3 baseline-v1
  train_split: train
  validation_split: valid
  test_policy: prohibited
training:
  imgsz: 640
  batch: 4
  epochs: 100
  optimizer: SGD
  lr0: 0.01
  lrf: 0.01
  momentum: 0.937
  weight_decay: 0.0005
  warmup_epochs: 3.0
  warmup_momentum: 0.8
  warmup_bias_lr: 0.1
  nbs: 64
  cos_lr: false
  seed: 42
  deterministic: true
  device: '0'
  workers: 0
  patience: 30
  amp: bf16
  cache: false
  save: true
  save_period: 10
  resume: false
  single_cls: false
  cls_remap: true
  rect: false
  compile: false
  channels_last: false
  freeze: null
  time: null
  fraction: 1.0
  profile: false
  box: 7.5
  cls: 0.5
  cls_pw: 0.0
  dfl: 1.5
augmentation:
  hsv_h: 0.015
  hsv_s: 0.7
  hsv_v: 0.4
  degrees: 0.0
  translate: 0.1
  scale: 0.5
  shear: 0.0
  perspective: 0.0
  flipud: 0.0
  fliplr: 0.5
  bgr: 0.0
  mosaic: 1.0
  close_mosaic: 10
  mixup: 0.0
  cutmix: 0.0
  copy_paste: 0.0
  copy_paste_mode: flip
  multi_scale: 0.0
  auto_augment: null
  erasing: 0.0
  albumentations: disabled
output:
  project: outputs/training/defect_detection
  name: DET-BASELINE
  exist_ok: false
  best_and_last: true
validation:
  val: true
  split: val
  plots: true
  save_json: false
  conf: 0.001
  iou: 0.7
  max_det: 300
  nms: false
  augment: false
reproducibility:
  git: true
  environment: true
  requested_config: true
  resolved_config: true
```

## 4. Exact smoke configuration

```yaml
extends: det_baseline.yaml
smoke:
  name: SMOKE-DET-BASELINE
  epochs: 1
  train_images: 128
  valid_images: 32
  selection: sha256(seed:split:relative_path)
  warmup_epochs: 0.0
  close_mosaic: 0
  save_period: 1
```

128/8,305 training images (1.54%) and 32/1,040 validation images (3.08%) were selected
by ascending SHA-256 of `42:split:relative_path`. Selected memberships and hashes
are in the smoke output's `dataset_identity.json`; output-local train.txt/valid.txt
do not modify approved split lists. Training batch=4, validation batch=8, imgsz=640.
No test images or labels were consumed by the development loader, geometry check,
smoke validation, checkpoint selection, tuning or model selection. Required
existing repository tests retain their metadata-only split-integrity checks.

## 5–7. GPU confirmation, duration and outcome

**SMOKE TRAINING = PASS.** Actual device `cuda:0`, NVIDIA GeForce RTX 4070 Laptop
GPU, 8,188 MiB total VRAM. Python 3.11.15; torch 2.14.0+cu130; torchvision
0.29.0+cu130; Ultralytics 8.4.145; CUDA runtime 13.0; cuDNN
92400; driver 591.94. Native BF16 support was checked before training. No dependency
installation or upgrade was performed.

| Evidence | Observed result |
|---|---|
| Epochs / batches | 1 / 32 |
| Optimizer steps / verified parameter updates | 2 / 2 |
| Classes | 0 Crack; 1 Breakage; 2 Honeycombing; 3 Hole; 4 Exposed Reinforcement; 5 Seepage |
| Forward / backward / finite losses and gradients | PASS |
| Validation | 32 validation images, 181 annotations; epoch validation and best-checkpoint validation both completed |
| Checkpoints | best.pt, last.pt and periodic epoch0.pt created |
| OOM / NaN / silent batch changes | None |
| Peak CUDA allocated / reserved | 1.273 / 1.633 GiB (PyTorch memory; excludes desktop/other processes) |
| Trainer call including dataset/model setup | 50.53 seconds |
| Training plus epoch/final validation phase | 25.07 seconds |
| Acquisition plus trainer orchestration | 53.82 seconds, excluding pre/post raw snapshots and preflight |
| Epoch CSV elapsed time | 18.7988 seconds |

Mean training losses: box=2.12920594,
classification=10.11178398,
L1=0.01902058.
Epoch validation losses: box=2.11007, classification=7.11941, L1=0.02016.

Final best-checkpoint validation emitted precision=0.00179740, recall=0.01794872,
mAP50=0.00117987, mAP50–95=0.00072283. These are **engineering smoke metrics only**,
not DET-BASELINE scientific results or a detector-performance claim.

## 8. Warnings and resolved errors

The initial full-suite attempt found two failures after a new test module imported
Ultralytics during collection, globally replacing Pillow's Image.open and reaching
an absent optional HEIF plugin on deliberately corrupted fixtures. Imports are now
scoped to the new test module and Pillow's previous function is restored afterward.
Existing M1 code/tests were unchanged; no optional dependency was installed.
The final suites pass. Existing Pillow Image.getdata deprecation warnings remain
(26 full-suite warnings). The smoke trainer emitted no OOM/NaN/error warning.

An exploratory source annotation example, valid/12039.jpg, overlaps surface writing
and is ambiguous as annotation-quality evidence in both coordinate frames. It was
not used as a spatial anchor, changed, excluded, relabeled or used to select a model.
This observation does not claim a dataset-wide annotation-quality audit.

## 9. EXIF compatibility

**EXIF TRAINING GEOMETRY = PASS.** All **594/594** affected development images passed
exact pixel-rotation checks and equality between the read-only adapter and actual
installed BaseDataset.load_image at 640. The 54 affected test images were not opened.
OpenCV applies EXIF 6 clockwise / EXIF 8 counterclockwise rotation. Stock normalized
labels remain unchanged. Representative spatial comparisons across both orientations
and both development splits establish that the source boxes use oriented display
coordinates: a second box rotation displaces them from the defects. Eight annotated
comparison panels and per-image hashes/checks are saved under
`outputs/validation/defect_detection/exif_alignment/`.

Synthetic asymmetric-object regression tests prove stock decode/parser behavior,
unchanged normalized boxes and custom-loader equivalence for EXIF 1/6/8. No EXIF
box transformation is required for this convention. The implemented runtime dataset
adapter is required to bypass stock JPEG repair, label-cache writes and raw-adjacent
.npy reads/deletes; it uses the existing read-only label validator and raw guard.
Spatial semantics were reviewed on representative anchors, not every annotation.
M1 preservation artifacts and the closed pretraining gate remain unchanged.

## 10–11. Exact test commands and final results

Both before and after smoke:

```powershell
.\.venv-detection\Scripts\python.exe -B scripts/check_detector_training.py --stage before
.\.venv-detection\Scripts\python.exe -B scripts/check_detector_training.py --stage after
```

The runner executes detector tests first, then the unchanged required suites:

```powershell
.\.venv-detection\Scripts\python.exe -B -m pytest tests/detection -q -p no:cacheprovider --junitxml=outputs/validation/defect_detection/training_pipeline/after/detector.xml
.\.venv-detection\Scripts\python.exe -m unittest discover -s tests/data -v
.\.venv-detection\Scripts\python.exe -m pytest tests ros2_ws/src/aegisinspect_mapping/test ros2_ws/src/aegisinspect_system_tests/test -q -p no:cacheprovider --junitxml=<fresh-output-temporary-directory>/pytest_results.xml
```

The exact absolute argv, temporary XML paths and timestamps are retained in each
stage's `test_results.json` / `ready.json`; final XML and logs are copied into the
stage directory. PYTHONPATH contains repository `src` and
`ros2_ws/src/aegisinspect_mapping`.

| Suite | Before smoke | After smoke |
|---|---:|---:|
| Detector | 74 passed / 0 failed | 74 passed / 0 failed |
| M1 | 112 passed / 0 failed | 112 passed / 0 failed |
| Full Python | 286 passed / 0 failed | 286 passed / 0 failed |

No skips. Detector: 51 successful subtests. Full suite: 75 successful subtests.
The stored pretraining report's 232 predates 22 simulated-depth tests already present
in this base; 232 + 22 existing additions + 32 new detector tests = 286. No prior
test was removed or weakened.

## 12. Raw immutability

**RAW IMMUTABILITY = PASS.** All 21,559 raw files were inventoried for size/mtime;
all 320 selected smoke source images/labels were SHA-256 checked before/after.
Files added=0, removed=0, size changes=0, mtime changes=0, selected-source content
changes=0, raw .cache=0, raw .npy=0. EXIF checks separately verified raw immutability
while hashing their 1,188 image/label source files. Test/archive contents were not
hashed by the development runs; their metadata was inventoried. Source repair,
rewriting, disk image caches and label caches were bypassed, and raw-write audit
hooks remained active. Detailed pre/post snapshots are retained as ignored outputs.

## 13. Official pretrained checkpoint

- Filename/model: `yolo26s.pt` / `yolo26s`.
- Source: `https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26s.pt`.
- Acquisition: HTTPS, only after completed implementation, passing tests/EXIF gate,
  and the pre-smoke raw snapshot.
- Local path: `C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection\outputs\cache\models\ultralytics\v8.4.0\yolo26s.pt`.
- Size: 20,422,725 bytes.
- SHA-256: `646f8bc3fe0a656803d95c294f7852321748cb29d13466a1af8862e2db384a1b`.

## 14. Output paths

- Smoke run: `outputs/training/defect_detection/SMOKE-DET-BASELINE/`.
- Best/last: `weights/best.pt`, `weights/last.pt` (20,313,733 bytes each).
- Periodic: `weights/epoch0.pt` (40,376,609 bytes).
- Logs/plots/results/config/provenance/subsets: the same smoke directory.
- Raw snapshots: smoke `raw_before.json`, `raw_after.json`; concise result in
  `raw_immutability.json`.
- EXIF evidence: `outputs/validation/defect_detection/exif_alignment/`.
- Test/model/report evidence: `outputs/validation/defect_detection/training_pipeline/`.
- Library cache/settings: `outputs/cache/detection_training/`.
- Official model cache: `outputs/cache/models/ultralytics/v8.4.0/`.
- Intended full output: `outputs/training/defect_detection/DET-BASELINE/` — **not created**.

## 15–16. Git review and commit recommendation

Branch/HEAD/base remain as stated above. Changes are unstaged and uncommitted.
`git diff --check` passes. `git diff --stat` lists `.gitignore | 10 ++++++++++`;
new source/config/evidence files are untracked, so ordinary diff statistics omit
them. The exact inventory is listed in section 1 and `changed_files.txt`.
Final `git status`, `git diff --check`, and `git diff --stat` outputs are retained
in `final_git_review.txt`. Protected M1/data paths have no diff.

Recommended commit message: `feat(detection): add reproducible baseline training pipeline`

## 17. Future full training command — prepared, NOT EXECUTED

From `C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection`:

```powershell
.\.venv-detection\Scripts\python.exe -B scripts/train_detector.py --config configs/detection/det_baseline.yaml
```

There are no smoke overrides. This uses the existing verified official checkpoint.
Execute only after the user explicitly approves the real DET-BASELINE run.

## 18. Runtime estimate

One smoke epoch covered 128 train / 32 validation images. Console throughput was
32 training batches in 13.8 seconds, approximately 2.3 batches/s or 9.3 images/s;
epoch validation took approximately 4 seconds for 32 images. Simple linear scaling
gives about 17 minutes per full train/validation epoch, or about 29 hours for 100
epochs. Treat **20–40 hours** as a rough planning range, not a measured full-run
duration. This assumes the same batch 4, 640, mosaic, workers 0, storage and GPU
power conditions, with validation each epoch. Small-sample/cold-start/plot overhead,
image complexity, thermal throttling and caching can materially change throughput;
patience-based early stopping may shorten the run. Initial full dataset verification
is additional one-time overhead. No further tuning or training was performed to
refine this estimate.

## 19–20. Blockers and next step

No engineering blocker was found for starting the configured baseline. The task
stops after successful smoke validation and final tests. The remaining requirement
is explicit user approval for the full experiment. Review the config/evidence and
commit the pipeline after review; then authorize the full run separately. No full
baseline, test evaluation, DET-IMPROVED work, merge or automatic commit was performed.
