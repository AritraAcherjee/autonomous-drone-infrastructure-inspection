# DET-FINAL-v1 freeze package

Prepared 2026-09-14T00:28:00.540887+00:00 on `chat02/detector-training` at `8ee410771c8be794d366e5e014f14f748edca97f`. **READY for Control Center freeze approval.** This package has not been approved or committed. The GYU-DET held-out test remains blocked pending separate authorization.

## Selected model

DET-FINAL-v1 freezes the existing DET-BASELINE `weights/best.pt` for Monday. Selection used training and validation evidence only. No DET-IMPROVED experiment was run. A later DET-FINAL-v2 may supersede this model after Monday.

- Controlled checkpoint: `outputs/training/defect_detection/DET-BASELINE/weights/best.pt`; **20,301,573 bytes**.
- SHA-256: `4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3`.
- YOLO26s detection, Ultralytics 8.4.145, input size 640, six-class head.
- IDs: 0 Crack; 1 Breakage; 2 Honeycombing; 3 Hole; 4 Exposed Reinforcement; 5 Seepage.
- Best epoch **62**, established independently from the maximum CSV mAP50-95 row, saved checkpoint train metrics, and early-stop log. The stripped checkpoint's epoch field is -1; it is not used as the epoch provenance. Training ended at epoch 92 of 100, patience 30.

## Immutable evaluation policy

The [manifest](../../configs/detection/det_final_v1.yaml) is the complete proposed contract. All 61 evidence/source references have SHA-256 values in the [evidence index](../../outputs/analysis/defect_detection/DET-FINAL-v1/evidence_index.json); this includes the exact accepted replay configuration and installed evaluator code.

Evaluation uses batch **8**, CUDA device `0`, workers 0, rectangular batches, pad 0.5, stride 32, native PyTorch backend with default model fusion, **FP16** model/input (`quantize=16`), confidence floor **0.001**, argument IoU **0.7**, `max_det=300`, `nms=false`, `augment=false`, `agnostic_nms=false`, `single_cls=false`, all six classes, fraction 1, caches disabled, compile/channels-last/DNN disabled. Loader shuffle/drop-last are false, pin-memory true and rank -1. Seed 42 and deterministic=true are retained configuration values; the standalone replay does not add training's seed-initialization routine.

The inspected Detect head is **end-to-end**. Postprocessing applies confidence >0.001 and keeps up to 300 outputs; conventional NMS is bypassed. The argument IoU 0.7 therefore does not suppress boxes for this checkpoint.

Exact manifest-approved records feed the existing read-only adapter, without stock discovery, fallback, downloads, label deduplication, repair, or raw-adjacent caches. Installed aspect-ratio sorting controls rectangular batches. OpenCV primary decode and reviewed EXIF orientation are preserved; EXIF 6/8 swap header dimensions. Source boxes stay in the reviewed oriented frame. Resize uses INTER_LINEAR/ceil with long side 640, followed by centered LetterBox (padding 114, scaleup=false), RGB/CHW conversion and division by 255. Raw files are never rewritten.

AP matching uses class-aware IoU >= each threshold from `torch.linspace(0.5,0.95,10)` in float32. Candidates sort by descending IoU, deduplicate predictions and then ground truths, without a second IoU sort (`use_scipy=false`). AP uses confidence-ranked cumulative TP/FP, a monotone precision envelope, 101 recall samples and trapezoidal integration. mAP averages the installed evaluator's present-GT classes and IoU thresholds.

Confusion collection is separate: confidence >0.001, class-agnostic geometric matching at IoU >0.45; descending IoU, unique predictions, a second IoU sort, then unique ground truths. Matrix rows are predictions, columns truth; unmatched objects use background. This matrix is not a deployment operating point.

## Threshold and reporting policy

AP50/AP50-95 integrate ranked predictions; they require the fixed collection floor, **not a single deployment threshold**. Preserve the existing **VALIDATION DIAGNOSTIC THRESHOLD = 0.18618618618618618**, grid index 186 of `np.linspace(0,1,1000)`. It came from the accepted validation replay's maximum smoothed mean class F1, with smoothing fraction 0.1. No new threshold optimization was performed.

Validation headline P/R use installed per-class interpolated curves at IoU 0.5 and that common index; F1 is a mean of per-class F1, not the harmonic mean of macro P/R. Accepted integer error counts use their separately documented greedy matcher and confidence >= the diagnostic threshold; they must not be substituted for evaluator P/R.

For a later authorized test, AP is primary. Any P/R/F1 must use the same fixed index via `fixed_diagnostic_pr` in the verifier module. The future reporting implementation must bypass stock per-split argmax selection and maximum-F1 plot annotations; it must not select or report a test-optimized operating point. Existing replay `plots=true` is retained; any future curve output must label the fixed validation point.

**Deployment confidence threshold remains a downstream validation/integration parameter and is not selected from the held-out test.**

## Validation evidence and limitations

Validation only: 1,040 images, 4,907 instances. P **0.47223142096534465**; R **0.4130733263020834**; AP50 **0.3884237740581788**; AP50-95 **0.21699306833671056**. The [per-class table](../../outputs/analysis/defect_detection/DET-BASELINE/per_class_metrics.csv) and [accepted failure analysis](../experiments/defect_detection/DET_BASELINE_FAILURE_ANALYSIS.md) are authoritative references. CSV epoch-62 metrics and final best-checkpoint FP16 metrics arise from different validation contexts and are not interchangeable.

Known limits: missed detections/weak confidence separation; localization and instance extent errors; tiny/thin objects; class/texture confusion and overprediction; density partly confounded by object size; annotation ambiguity and limited source detail. Seepage remains weak. These are validation findings; generalization remains unmeasured.

DET-IMPROVED-01's single proposed change, imgsz 640 -> 800, is scientifically accepted but **DEFERRED until after Monday and NOT AUTHORIZED for training**.

## Access contract and chronology

`test_accessed=false`; `codebrim_accessed=false`. No training, inference, test-list/manifest read, raw-content read, or CODEBRIM access occurred in this preparation task. Stored M1 metadata supplied the held-out count and hashes; the held-out split itself was not opened or rehashed. The access declaration follows accepted evidence and this task's controls, and is not an independent audit of all historic activity.

The manifest SHA is in [manifest.sha256](../../outputs/analysis/defect_detection/DET-FINAL-v1/manifest.sha256). The delivered ZIP's SHA and timestamp are in the external delivery receipt, avoiding self-referential hashing. Neither a timestamp nor a hash alone proves historical non-access. Control Center should approve the manifest/package hashes and retain the later freeze commit SHA before authorizing the test.

After approval, this model/configuration is immutable for the one-time test. A separately authorized runner must verify the approved commit, manifest, package and checkpoint hashes, bind the stored approved test-list identity, and create an exclusive durable STARTED receipt **before the first held-out open**. Record completion or failure, timestamps, exact arguments and outputs. A failed/partial run must not trigger an automatic repeat. Stop for Control Center review. These are required future controls, not a claim that a one-time runner already exists.

The existing development adapter still rejects test records. The verifier only verifies files/contracts and selects a fixed diagnostic curve index; it has no training or inference entry point. Future authorized test integration must preserve geometry/matching and leave development guards intact. **Separate freeze approval and held-out-test authorization are still required.**

## Review and verification

[Commit review](../../outputs/analysis/defect_detection/DET-FINAL-v1/commit_review.md) lists every file and its category. Concise pre-existing baseline configs, results and provenance are included as unmodified dependencies. Weights, raw data, large prediction dumps, machine-specific development lists, and duplicate/source-image montages stay local/ignored. The accepted failure-analysis report intentionally retains links to optional local artifacts; those remain available locally but are not all Git deliverables.

Checks: 7 existing analysis tests, 8 freeze tests, 18 detector configuration tests and 9 synthetic EXIF/adapter tests passed (42 tests, 51 subtests). [Integrity evidence](../../outputs/analysis/defect_detection/DET-FINAL-v1/integrity_check.json) verifies all 47 frozen baseline files by SHA/size/mtime, all 19,389 development raw file sizes/mtimes, and recorded protected input hashes. No raw content rehash or held-out traversal was needed. Git diff --check passed; no files were staged or committed.
