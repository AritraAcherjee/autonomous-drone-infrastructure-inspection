# AegisInspect Presentation Assembly Source

Final presentation title:

**PENDING 00 CONTROL CENTER DECISION**

Highest Stop-level statement:

**PENDING 00 CONTROL CENTER DECISION**

This file is presentation-ready source material. It is not a frozen final
slide deck.

---

## 1. Problem / Motivation

AegisInspect investigates how an inspection-drone software stack can combine
structural-defect perception, multimodal simulation, spatial reasoning,
persistent review records and quantitative evaluation.

The project is intentionally modular so each technical claim can be tied to
its own evidence rather than treating implementation existence as proof of
full-system performance.

**Presentation boundary:** do not claim a validated full autonomous mission.

---

## 2. AegisInspect Objective

Build an evidence-driven inspection architecture that can:

- acquire RGB, depth, IMU and LiDAR observations;
- detect structural defects;
- consume localization and depth information;
- project observations into 3D;
- aggregate defect observations;
- persist inspection records;
- support explicit human review;
- generate deterministic reports;
- evaluate detector, localization and spatial outputs reproducibly.

---

## 3. Overall System Architecture

Recommended visual flow:

**DATA**
->
**DETECTION**
->
**GENERALIZATION TEST**
->
**DRONE SIMULATION**
->
**LOCALIZATION**
->
**3D PROJECTION**
->
**DEFECT MAPPING**
->
**DATABASE / REVIEW**
->
**REPORT**
->
**QUANTITATIVE EVALUATION**

Status language must distinguish:

- supported measured result;
- implemented software;
- simulation/runtime evidence;
- pending runtime result.

Architecture arrows describe intended integration and do not by themselves
prove that the complete chain has run end-to-end.

---

## 4. GYU-DET Dataset / Six Defect Classes

**Status:** `SUPPORTED / DATA_FOUNDATION`

Approved GYU-DET V3 baseline-v1:

- 10,398 supervised images
- 8,305 train
- 1,040 validation
- 1,053 test
- 48,392 annotations
- 6 classes

Classes:

- Crack
- Breakage
- Honeycombing
- Hole
- Exposed Reinforcement
- Seepage

Dataset counts are not detector-performance metrics.

---

## 5. Detector Training + Scientific Evaluation Methodology

Model:

**DET-FINAL-v1 / YOLO26s**

Evaluation controls:

- frozen checkpoint before one-time held-out test execution;
- held-out GYU-DET test contains 1,053 images and 5,886 instances;
- diagnostic confidence threshold selected from validation;
- no held-out test threshold optimization;
- checkpoint and provenance hashes retained;
- external DamSegment benchmark executed zero-shot.

Checkpoint SHA256:

`4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3`

---

## 6. DET-FINAL Held-Out GYU Results

**Status:** `SUPPORTED / REAL_HELD_OUT`

Primary held-out test results:

- mAP50: **0.29669431228680787**
- mAP50-95: **0.17480040543737643**

At validation-selected diagnostic confidence
`0.18618618618618618`:

- macro precision: **0.37674095487474335**
- macro recall: **0.37432339044543**
- mean per-class F1: **0.3556245448108634**

Approved label:

**DET-FINAL-v1 held-out GYU-DET detection performance**

Never relabel these values as generic "accuracy" or "drone accuracy."

---

## 7. External Generalization - DamSegment

**Status:** `SUPPORTED / EXTERNAL_BENCHMARK`

Experiment:

`GEN-DAMSEGMENT-ZS-001`

Evaluation scope:

- DamSegment v1 Damage Detection
- 1,500 images
- 19,710 GT regions
- Crack -> Crack
- Spalling -> Breakage
- only shared Aegis classes `[0, 1]`

Shared-class results:

- mAP50: **0.053176162102447924**
- mAP50-95: **0.031339626242648855**
- precision: **0.25308641975308643**
- recall: **0.006240487062404871**
- F1: **0.01218062982768865**

Scientific interpretation:

**DET-FINAL-v1 shows weak zero-shot external-domain transfer to
DamSegment, particularly for Crack recall.**

The experiment succeeded scientifically; cross-domain performance was weak.

---

## 8. ROS 2 / Gazebo Simulation Foundation

**Status:** `SUPPORTED / SIMULATION_RUNTIME`

Verified simulation foundation includes:

- ROS 2 Lyrical
- Gazebo Sim 10.5.0
- RGB
- CameraInfo
- IMU
- 3D LiDAR
- depth
- simulation clock
- TF / static TF

Runtime-observed topic rates must not be presented as configured target
rates or real-drone sensor performance.

---

## 9. Simulated Metric Depth

**Status:** `SUPPORTED / SIMULATION_RUNTIME`

Verified simulated depth contract:

- ROS message: `sensor_msgs/Image`
- encoding: `32FC1`
- units: metres
- frame: `camera_optical_frame`
- resolution: 640 x 480
- RGB/depth/CameraInfo geometry validated

Runtime test evidence:

**103 tests, 0 errors, 0 failures, 0 skipped**

Boundary:

simulated metric depth is not real-world depth-camera accuracy.

---

## 10. Camera-Frame 3D Projection

**Status:** `SUPPORTED / SIMULATION_RUNTIME`

Runtime-validated service:

`/aegis/mapping/project_camera`

Type:

`aegisinspect_interfaces/srv/ProjectCamera`

Verified result frame:

`camera_optical_frame`

Runtime test evidence:

**196 colcon tests, 0 errors, 0 failures, 0 skipped**

Boundary:

camera-frame XYZ does not establish real map-frame defect localization or
real global localization accuracy.

---

## Insertable Localization / Stop-B Backend Status Slide

This section is deliberately insertable because localization runtime
evidence may change before the final presentation.

Primary localization approach:

**OpenVINS Mono + IMU**

OpenVINS engineering state:

- compatibility/build integration succeeded;
- sensor delivery was validated;
- live runtime initialization remained blocked after controlled diagnosis;
- one evidence-derived correction was tested;
- initialization remained blocked;
- further blind tuning was rejected;
- OpenVINS was removed from the Stop-B critical path.

Active Stop-B fallback:

**RTAB-Map RGB-D + IMU**

Current RTAB-Map runtime result:

**PENDING**

Current quantitative fields:

- backend runtime result: **PENDING**
- ATE RMSE: **PENDING**
- RPE translation RMSE: **PENDING**
- RPE rotation RMSE: **PENDING**
- timestamp-alignment coverage: **PENDING**

Do not state that OpenVINS successfully provided drone odometry.

Do not state that RTAB-Map is successful until accepted MSI evidence exists.

---

## 11. Defect-to-Map Architecture

**Status:** `IMPLEMENTED_NOT_REAL_EVIDENCE / IMPLEMENTATION_TEST`

Presentation-safe wording:

**AegisInspect includes implemented deterministic defect-to-map fusion
software.**

Conceptual flow:

detection / track
->
robust depth
->
camera XYZ
->
pose transform
->
map XYZ
->
temporal aggregation
->
duplicate handling
->
persistent defect record

Real map-frame defect-localization accuracy remains **PENDING**.

---

## 12. Database / Dashboard

**Status:** `IMPLEMENTED_NOT_REAL_EVIDENCE / SYNTHETIC_DEMO`

Presentation-safe wording:

**AegisInspect includes a persistent inspection database and review
dashboard, demonstrated using synthetic mapped-defect records.**

Current documented demonstration contains:

- one synthetic structure;
- one synthetic inspection;
- three synthetic mapped defects;
- four synthetic evidence rows.

Machine-created defects begin as:

`UNREVIEWED`

Do not describe these synthetic records as field inspection data.

---

## 13. Deterministic Reporting

**Status:** `IMPLEMENTED_NOT_REAL_EVIDENCE / IMPLEMENTATION_TEST`

Presentation-safe wording:

**AegisInspect includes deterministic report-generation software with
fail-closed validation and explicit human-review separation.**

Boundary:

a completed autonomous-inspection report from a validated integrated
mission has not yet been claimed.

---

## 14. P19 Evaluation Methodology

**Status:** `IMPLEMENTED_NOT_REAL_EVIDENCE / IMPLEMENTATION_TEST`

Canonical P19 tooling is prepared for:

- VIO ATE translation RMSE;
- VIO RPE translation RMSE;
- VIO RPE rotation RMSE;
- timestamp-alignment coverage;
- mean defect-location error;
- median defect-location error;
- defect-location RMSE;
- P95 defect-location error;
- matched and unmatched counts.

Current real project values remain:

**PENDING**

Synthetic fixture values are not real project results.

---

## 15. Limitations

Required visible limitations:

1. GYU detector metrics are not generic accuracy.
2. DamSegment zero-shot generalization is weak.
3. DamSegment scores only shared Crack and Breakage/Spalling classes.
4. simulated depth is not real-world depth validation.
5. camera XYZ alone does not establish map-frame localization.
6. OpenVINS did not successfully initialize for Stop-B runtime.
7. RTAB-Map runtime result remains pending.
8. P16 demo records are synthetic.
9. real VIO ATE/RPE remains pending.
10. real 3D defect-localization accuracy remains pending.
11. P15/P17 implementation does not prove a complete integrated mission.
12. full autonomous end-to-end completion requires P18 evidence.

---

## 16. Contributions / Engineering Decisions

Evidence-backed contributions include:

- reproducible GYU-DET data foundation;
- frozen held-out detector evaluation;
- external zero-shot generalization benchmark;
- multimodal ROS/Gazebo simulation foundation;
- simulated metric depth;
- runtime-validated camera-frame projection;
- deterministic mapping, persistence, reporting and evaluation layers.

Localization engineering decision:

OpenVINS was not hidden after initialization failure.

The team instrumented the initialization condition, tested one
evidence-derived correction, rejected blind tuning after the failure
persisted, preserved the downstream localization contract, and activated
the pre-designed RTAB-Map fallback.

---

## 17. Next Steps

Current evidence priorities:

- obtain accepted RTAB-Map RGB-D + IMU runtime evidence;
- evaluate trajectory with canonical P19 methodology;
- populate ATE / RPE / alignment coverage;
- obtain explicit estimated-vs-GT defect correspondences;
- populate real 3D defect-location metrics;
- run and validate P18 integrated mission path;
- update the final title only after 00 accepts the achieved Stop level.

---

## 18. Q&A / Evidence References

Keep available during Q&A:

- claim matrix;
- canonical results table;
- evidence inventory;
- limitations/Q&A source;
- canonical commit and PR references;
- detector checkpoint hash;
- DamSegment result hashes;
- runtime validation reports.

Core message:

**Implemented is not the same as measured.**

**Simulation/runtime evidence is not the same as real-world accuracy.**

**PENDING means the result has not yet been accepted.**
