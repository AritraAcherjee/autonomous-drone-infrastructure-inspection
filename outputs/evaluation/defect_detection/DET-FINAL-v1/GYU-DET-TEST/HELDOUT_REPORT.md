# DET-FINAL-v1 one-time held-out evaluation

Frozen model: `d9cd2f5b58559d45e5d4a42ce702c595345e292b`. GYU-DET V3 baseline-v1 TEST, 1053 images and 5886 instances.

Primary test metrics: mAP50 **0.29669431228680787**; mAP50-95 **0.17480040543737643**.

At the previously selected **VALIDATION DIAGNOSTIC THRESHOLD 0.18618618618618618**, index186/1000: macro P **0.37674095487474335**, R **0.37432339044543**, mean per-class F1 **0.3556245448108634**. These are interpolated evaluator curves at IoU0.5. No test threshold optimization was executed; AP computation retained installed ranked integration semantics.

| Class | Instances | P | R | F1 | AP50 | AP50-95 | AP75 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Crack | 404 | 0.4107716181341531 | 0.41336633663366334 | 0.412064892774012 | 0.37611493543705943 | 0.2225092080350653 | 0.23606899943728504 |
| Breakage | 3628 | 0.3747159565379042 | 0.21168687982359427 | 0.2705391131864265 | 0.19795754711939248 | 0.08131880858939623 | 0.05634122798283842 |
| Honeycombing | 281 | 0.2266402984424858 | 0.5658362989323843 | 0.32364692682265894 | 0.2736183810913587 | 0.18754228081456045 | 0.2115448702605478 |
| Hole | 69 | 0.40449427583822256 | 0.4331614222918571 | 0.4183373102388677 | 0.3897520452565438 | 0.2623651720982592 | 0.3150505107569703 |
| Exposed Reinforcement | 1381 | 0.5921373202060732 | 0.3779869659666908 | 0.46142580345727285 | 0.4144481138229464 | 0.22009739003282108 | 0.20697772268000647 |
| Seepage | 123 | 0.2516862600896214 | 0.24390243902439024 | 0.24773322238594248 | 0.1282748509935466 | 0.0749695730541563 | 0.07761829482132188 |

## Descriptive validation comparison

| Metric | Validation | Test | Test - validation | Absolute gap |
|---|---:|---:|---:|---:|
| precision | 0.47223142096534465 | 0.37674095487474335 | -0.0954904660906013 | 0.0954904660906013 |
| recall | 0.4130733263020834 | 0.37432339044543 | -0.03874993585665337 | 0.03874993585665337 |
| mAP50 | 0.3884237740581788 | 0.29669431228680787 | -0.09172946177137092 | 0.09172946177137092 |
| mAP50_95 | 0.21699306833671056 | 0.17480040543737643 | -0.04219266289933413 | 0.04219266289933413 |

This comparison does not select a model, threshold or future experiment setting. Deployment threshold remains unresolved and must not be selected from held-out results.

## Frozen confusion evidence

Confusion uses confidence>0.001 and class-agnostic IoU>0.45; it is separate from the fixed diagnostic threshold.

- Truth Breakage -> predicted Honeycombing: 226
- Truth Exposed Reinforcement -> predicted Breakage: 168
- Truth Breakage -> predicted Exposed Reinforcement: 135
- Truth Breakage -> predicted Seepage: 86
- Truth Breakage -> predicted Crack: 70

Misses to background: {"Crack": 32, "Breakage": 869, "Honeycombing": 14, "Hole": 11, "Exposed Reinforcement": 279, "Seepage": 30}.

## Timing and integrity

{
  "ms_per_image": {
    "preprocess": 0.3720399811297853,
    "inference": 7.681884140178433,
    "loss": 0.0010659070612539,
    "postprocess": 0.2483455840962986
  },
  "evaluator_seconds": 104.21005439999863,
  "images": 1053,
  "gpu": "NVIDIA GeForce RTX 4070 Laptop GPU",
  "inference_batch_calls": 132
}

All 1053 images were processed exactly once in 132 batches. Checkpoint, manifest and raw SHA/size/mtime checks passed. No training, CODEBRIM access or DET-IMPROVED execution occurred. The exclusive ONE_TIME_RECEIPT.json is authoritative for final COMPLETED/FAILED state and timestamps. No retry is authorized.

## Evidence

Full metrics, per-class values, fixed-threshold metrics, curves, confusion, timing, provenance, integrity, prediction batches and the evidence index are retained in this directory. The result ZIP excludes the final receipt to avoid self-referential hashing; its hash is in that receipt. No evaluation closeout commit is authorized.
