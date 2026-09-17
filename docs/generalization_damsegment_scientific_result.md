# GEN-DAMSEGMENT-ZS-001 — Scientific External Generalization Result

## Status

Scientific execution: **COMPLETE**

Benchmark state: **CONSUMED**

Held-out evaluation count: **1**

This is the first frozen DET-FINAL-v1 zero-shot scientific evaluation on DamSegment v1.
DamSegment results were not used to tune DET-FINAL, thresholds, image size, augmentations, checkpoint selection, or DET-IMPROVED.

## Execution provenance

- Branch: `03/damsegment-preaccess`
- Scientific execution HEAD: `d57937abc1b74d652aeccf60ce3d6456e945eb7a`
- Runtime manifest SHA256: `64a732693e4eb30d5302f9938bb6da0139b3f151404cb4245db5056015f363c3`
- DET-FINAL-v1 SHA256: `4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3`
- Prediction bundle SHA256: `b7cfebcbb29d1aac4433ac2de01fdc02c112e45001749def00300e90f9c77d36`
- Results JSON SHA256: `8cafd13c1f9695f006fbebcd1c66892acfcba031be8d93cb360c53e208d4040b`
- Scientific completion SHA256: `4823c10047ac2813346e392e4c9feb937a5e15b95adb987d47b4e4a9637a83d3`
- Artifact hash index SHA256: `7eeb9e3f9bd50b00223a28d22776a010133ce24cf9e285187112e67f151a4c36`

The immutable runtime manifest remains bound to the scientific execution HEAD above. A later evidence commit does not change the execution HEAD.

## Dataset / evaluation scope

- DamSegment v1 Damage Detection subset
- Evaluated images: **1,500**
- Ground-truth regions: **19,710**
- Crack support: **19,229**
- Spalling mapped to Aegis Breakage support: **481**
- Approved scoring classes: `[0, 1]`
- Aegis classes 2-5 excluded from the shared-class aggregate
- Normalized detector predictions: **232,125**

## Frozen inference

- Model: DET-FINAL-v1 / YOLO26s
- imgsz: 640
- batch: 8
- device: CUDA:0
- workers: 0
- rect: true
- pad: 0.5
- FP16 runtime binding: quantize=16
- confidence collection floor: 0.001
- IoU: 0.7
- max detections: 300
- NMS: false
- augment: false

Inference duration: **15.272786267 s**

Scientific scoring duration: **200.821687350 s**

## Shared-class DamSegment metrics

| Metric | Value |
| --- | ---: |
| mAP50 | 0.053176162102 |
| mAP50-95 | 0.031339626243 |
| Precision | 0.253086419753 |
| Recall | 0.006240487062 |
| F1 | 0.012180629828 |
| TP | 123 |
| FP | 363 |
| FN | 19587 |

## Per-class metrics

| Class | GT | AP50 | AP50-95 | Precision | Recall | F1 | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Crack | 19229 | 0.016412642020 | 0.005617087715 | 0.504273504274 | 0.003068282282 | 0.006099452083 | 59 | 58 | 19170 |
| Breakage | 481 | 0.089939682185 | 0.057062164770 | 0.173441734417 | 0.133056133056 | 0.150588235294 | 64 | 305 | 417 |

## Scientific integrity

- Scientific scorer status: COMPLETE
- Scientific scorer exit code: 0
- Post-result tests: 120 passed, 46 subtests passed
- Inference rerun: NO
- Scoring rerun: NO
- Parameter changes after external result: NO
- DET-FINAL modified: NO
- Locked GYU raw test accessed: NO
- DET-IMPROVED started: NO

The first post-scoring evidence wrapper stopped only because it incorrectly expected `classes_with_gt` to contain `[0,1]`. The repository schema defines it as integer count `2`; the class IDs are stored separately in `scored_classes=[0,1]`. This was inspected read-only and the scientific scorer was not rerun.

## Scientific limitation

This is a frozen zero-shot external-domain result. Transfer is weak, particularly Crack recall. Because DamSegment is now consumed as an external detector-development benchmark, these measurements must not be used to tune DET-FINAL or DET-IMPROVED.
