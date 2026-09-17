# P20 Limitations and Q&A

## Required limitations

### 1. Detector metrics are not generic accuracy

DET-FINAL-v1 has accepted held-out mAP, precision, recall and F1 evidence.

Do not compress these into a generic "accuracy" percentage.

### 2. External generalization is weak

The DamSegment execution completed successfully, but zero-shot transfer is
weak.

This is a model-generalization limitation, not an execution failure.

### 3. DamSegment is a shared-class benchmark

DamSegment scoring uses only:

- Crack -> Crack
- Spalling -> Breakage

It is not a six-class GYU-DET evaluation.

### 4. Depth evidence is simulated

Metric depth was validated in ROS/Gazebo.

It is not real-world depth-camera accuracy evidence.

### 5. Camera XYZ stops in camera_optical_frame

The ProjectCamera milestone validates camera-frame XYZ.

It does not independently establish map-frame defect localization.

### 6. P16 demonstration data is synthetic

Dashboard demo structures, inspections, mapped defects and evidence rows
are synthetic/test-only.

### 7. Implemented modules do not prove a full mission

P15 mapping software and P17 reporting software are implemented, but that
does not establish a completed integrated autonomous mission.

### 8. Real VIO metrics remain pending

Real ATE and RPE must remain `PENDING` until accepted hash-bound MSI
trajectory evidence exists.

### 9. Real 3D defect localization remains pending

No real mean/RMSE/P95 localization error is currently authorized.

### 10. End-to-end autonomy remains pending

Do not claim full autonomous inspection completion without objective P18
runtime evidence.

---

# Likely Q&A

## Q: What is the main detector result?

The accepted one-time held-out GYU-DET result for DET-FINAL-v1 is:

- mAP50 = 0.29669431228680787
- mAP50-95 = 0.17480040543737643

These are detection metrics, not generic accuracy.

## Q: Was the held-out test used to choose the threshold?

No.

The diagnostic confidence `0.18618618618618618` was selected from
validation.

The held-out test was not used to optimize that threshold.

## Q: Why is DamSegment performance much lower?

It is an external-domain zero-shot benchmark with different data
characteristics and only a shared two-class scoring ontology.

The measured result demonstrates weak transfer, especially Crack recall.

P20 should present this as a scientific limitation rather than hide it.

## Q: Did the DamSegment run fail?

No.

The scientific execution completed successfully.

The performance itself is weak.

## Q: Are the dashboard defects real inspection records?

No.

The current P16 demo records are synthetic/test-only and exist to
demonstrate persistence and human-review workflow.

## Q: Is the depth result from a real sensor?

No.

The current verified depth result is simulated metric depth in Gazebo.

## Q: Does the system already map defects into a global frame?

The deterministic defect-to-map software layer is implemented.

However, accepted real map-frame localization accuracy has not yet been
demonstrated.

## Q: What does the camera projection service prove?

It proves runtime-validated projection into `camera_optical_frame` using
the exact-observation ProjectCamera contract.

It does not prove global/map localization.

## Q: What are the current ATE and RPE values?

`PENDING`.

P20 must not manufacture values from synthetic tests.

## Q: Why build P19 if there are no real spatial numbers yet?

P19 freezes a deterministic evaluation methodology so future accepted
upstream artifacts can be scored without changing methodology after
seeing the result.

## Q: Is the system fully autonomous today?

P20 does not currently have evidence supporting that claim.

Full end-to-end mission completion remains pending P18 evidence.

## Q: What can be demonstrated today?

Evidence-backed material includes:

- approved GYU-DET dataset foundation;
- DET-FINAL held-out evaluation;
- DamSegment external benchmark;
- ROS/Gazebo multimodal foundation;
- simulated metric depth;
- camera-frame 3D projection;
- implemented P15/P16/P17/P19 software layers.

The status of each should remain visible.

## Q: What is the final Stop-level title?

It is not frozen by P20.

00 Control Center owns the final title and highest Stop-level statement.
