# Reproducible GYU-DET baseline training

The canonical experiment is `configs/detection/det_baseline.yaml`. The separate
`det_baseline_smoke.yaml` overlay is an engineering check, not a scientific result.
The approved dataset remains GYU-DET V3 baseline-v1: 8,305 train and 1,040 validation
images, with the original six class IDs. Final-test images are unavailable to this
development workflow. CODEBRIM is not an input.

## Model and baseline choices

Installed Ultralytics 8.4.145 contains YOLO26 model definitions and registers
`yolo26s.pt` in `ultralytics.utils.downloads.GITHUB_ASSETS_NAMES`. CPU construction
from the installed YAML (without pretrained weights or training) confirmed
10,009,784 parameters at 80 classes and 9,952,508 at six classes. Small is the
moderate-cost baseline for the 8GB RTX 4070 Laptop GPU; no medium/large model was
downloaded or evaluated. The acquisition URL is pinned to the package's official
`ultralytics/assets` release `v8.4.0`.

The full configuration uses 640 pixels, fixed batch 4, 100 maximum epochs, patience
30, seed 42, deterministic execution, CUDA device 0 and workers 0. SGD uses LR
0.01, linear decay to 0.0001, momentum 0.937, Nesterov enabled by the installed
optimizer, weight decay 0.0005, and nominal batch 64. Gradient accumulation is 16
outside warmup; weight decay is applied to weight groups, not bias/normalization
groups. Warmup is three epochs, momentum 0.8, bias LR 0.1. There is no class
weighting, freezing, resume, multi-scale input or architecture customization.

Native BF16 AMP is explicit and requires `torch.cuda.is_bf16_supported()`. The
installed trainer skips its auxiliary `yolo26n.pt` FP16 AMP check in BF16 mode.
Training validation internally uses the installed validator's AMP policy; its
arguments and precision policy are recorded. BF16 stability and finite gradients
must be demonstrated by smoke evidence. `channels_last` and compilation are off.

Augmentation values are explicit in the YAML: HSV .015/.7/.4, translation .1,
scale .5, horizontal flip .5, mosaic 1.0 (closed for the final ten epochs), and
zero rotation, shear, perspective, vertical flip, BGR swapping, mixup, cutmix,
copy-paste and multi-scale. Optional Albumentations is disabled regardless of
installation status. Classification-only auto augmentation/erasing is disabled.
Normal augmentation operates on in-memory training tensors and boxes, never source
images or label files. Validation uses no random training augmentation.

## EXIF integration

The pretraining gate remains closed/PASS and its artifacts are unchanged. Its
648 orientation-6/8 cases comprise 594 development images and 54 final-test images.
Only the 594 development cases are eligible for this training compatibility check.

The exact installed path is `BaseDataset.load_image` -> `patches.imread` ->
OpenCV `imdecode(IMREAD_COLOR)`. OpenCV rotates EXIF-6 pixels clockwise and EXIF-8
pixels counterclockwise. Stock YOLO label verification retains normalized XYWH;
it does not perform an EXIF box transform. Width/height swapping alone cannot
establish alignment.

The targeted check compares full decoded pixels with an explicitly rotated
ignore-orientation decode and compares the new loader with actual installed
`BaseDataset.load_image` output at 640. Eight reviewed spatial anchors cover both
orientations and both development splits. The source boxes correspond to oriented
display pixels on these anchors; applying another box rotation moves them off the
defects. Synthetic asymmetric-region regression tests check the actual stock
label parser, the stock pixel loader, the custom loader and pre-augmentation
normalized boxes for orientations 1, 6 and 8.

This establishes the coordinate convention using representative spatial evidence,
with decoder/adapter equivalence across all 594 development cases. It is not a
semantic audit of every source annotation. One additional exploratory example,
valid/12039.jpg, has labels over surface writing and is ambiguous as annotation
quality evidence in either coordinate frame; no label changes or exclusions were
made. It is not used as an alignment anchor. The test population was not opened.

No EXIF box-rotation adapter is required for the reviewed convention. A read-only
dataset adapter **is** required for source safety: the stock constructor writes
label caches even with `cache=False`, can repair JPEGs, and stock `load_image` can
read/delete preexisting raw-adjacent `.npy` files. `ReadOnlyDetectionDataset`
bypasses those paths, reuses the existing read-only label validator, and preserves
the installed decoder, resize behavior and in-memory mosaic buffer. Its only
augmentation difference is explicitly disabling optional Albumentations.

## Commands

Run from the repository in the existing `.venv-detection`. No dependency upgrades
are required.

```powershell
.\.venv-detection\Scripts\python.exe -B scripts/verify_detector_exif.py
.\.venv-detection\Scripts\python.exe -B scripts/check_detector_training.py --stage before
.\.venv-detection\Scripts\python.exe -B scripts/train_detector.py --config configs/detection/det_baseline_smoke.yaml --check
.\.venv-detection\Scripts\python.exe -B scripts/train_detector.py --config configs/detection/det_baseline_smoke.yaml --download-pretrained
.\.venv-detection\Scripts\python.exe -B scripts/check_detector_training.py --stage after
```

The one-epoch smoke selects 128 train and 32 validation images by ascending
SHA-256 of `42:split:repository-relative-image-path`. It retains batch 4, image size
640 and model/optimizer settings. Warmup and mosaic closing are disabled only in
the smoke overlay, and periodic saving changes from ten epochs to one. Membership
is recorded in `dataset_identity.json` and output-local lists; approved lists are
never modified. Validation receives only the selected validation records. The
internal Ultralytics attribute named `test_loader` is its validation loader and
contains these validation records, not the final test split.

The future full command, requiring explicit user approval to execute, is:

```powershell
.\.venv-detection\Scripts\python.exe -B scripts/train_detector.py --config configs/detection/det_baseline.yaml
```

This command has no smoke overlay and uses the cached official pretrained weights.
The current task must not execute it. Re-run tests after code/config changes, and
re-run the EXIF check if the installed loader or adapter fingerprint changes.

## Outputs, provenance and failure behavior

Each experiment owns `outputs/training/defect_detection/<experiment>/`. The CLI
refuses existing run directories before the trainer is constructed. Ultralytics
receives `exist_ok=True` only after this exclusive directory creation, so it uses
that exact directory instead of silently suffixing it. Do not overwrite failed
evidence; preserve it under a clearly named reviewed output location before retrying.

Outputs include requested config, effective Ultralytics arguments, resolved
optimizer groups, Git branch/SHA/dirty status/diff, implementation hashes, installed
package versions, Python/CUDA/cuDNN/driver/GPU metadata, selected dataset identities,
acquisition receipt and SHA-256, losses, validation metrics, runtime/memory evidence,
`results.csv`, and best/last/periodic checkpoints. Best is selected only by validation.
Checkpoints and transient plots/caches are ignored; concise metadata and reports
remain versionable. No full training run is authorized by the presence of a config.
Ultralytics 8.4.145 applies `save_period` to zero-based epoch indices: period 10
saves `epoch0.pt`, `epoch10.pt`, and so on (completed epochs 1, 11, ...), in addition
to best/last. The smoke's period 1 produced `epoch0.pt`. This native cadence is
recorded explicitly rather than interpreting the filenames as one-based epochs.

Before acquisition/training, all raw paths are inventoried for size/mtime and the
selected source images/labels are content-hashed (320 files for this smoke; all
18,690 development files for a full baseline). The same snapshot is repeated in
`finally` immediately after execution, including failure. Test/archive contents
are not hashed by this development run; their metadata is inventoried. Existing
raw-write audit hooks are reused unchanged, an additional read boundary denies
non-development raw contents, and workers 0 keeps Python operations in the guarded
process. Native decoder operations are constrained by the inspected read-only
implementation, with the post-run snapshot as an independent check.

Nonfinite losses/gradients, missing/zero optimizer updates, missing validation or
checkpoints, or raw changes make the run fail. Fixed-batch reduction after OOM is
refused. There is no silent repair, retry with different hyperparameters, or
fallback to test data. Partial acquisition files and failed evidence are retained.

Determinism is requested and recorded, but identical results across different
hardware, drivers or library builds are not promised. A one-epoch smoke supplies
engineering evidence only, and its small validation metrics cannot support model
selection or a detector-performance claim.
