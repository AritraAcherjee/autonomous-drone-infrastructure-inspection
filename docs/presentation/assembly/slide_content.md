# AegisInspect Presentation Assembly Source

Final presentation title:

**AegisInspect: Multimodal Drone Infrastructure Inspection**

Highest Stop-level statement:

**No Stop C or full-autonomy claim.**

This file is presentation-ready source material. It is not a frozen final
slide deck.

---

## 1. Problem / Motivation

AegisInspect is a robotics/computer-vision infrastructure-inspection system
combining deep-learning defect detection with classical localization, 3D
geometry, mapping, persistence and deterministic reporting.

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

**CAMERA / DETECTOR** -> **DEPTH** -> **CAMERA XYZ** ->
**LOCALIZATION / MAP RELATION** -> **MAP XYZ / P15** ->
**P16 PERSISTENCE + DASHBOARD** -> **P17 DETERMINISTIC REPORT**

Status language must distinguish:

- `DEMONSTRATED` for accepted runtime or real-handoff evidence;
- `SUPPORTED` for accepted measured evidence;
- `IMPLEMENTED` for software functionality;
- `MEASURED` for metrics without an accepted pass/fail threshold;
- `PENDING` for evidence not yet ingested or accepted.

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

## Insertable P19 Localization / 3D Status Slide

**Runtime acceptance:** `PASS` for the accepted LiDAR ICP runtime.

**Localization accuracy:** `MEASURED` against simulation ground truth, not
classified as PASS or FAIL.

Frozen evaluation:

- interval: 3–18 s;
- GT bracket maximum: 50 ms;
- linear translation interpolation and quaternion SLERP;
- SE(3) no-scale alignment; scale = 1;
- RPE delta: 1 s ± 50 ms.

Presentation-rounded measured results:

- ATE translational RMSE: **0.595 m** (76 samples);
- RPE translational RMSE: **0.341 m**;
- RPE rotational RMSE: **1.707 degrees** (44 pairs).

Mandatory qualification:

**These metrics evaluate localization trajectory accuracy, not absolute
defect-position accuracy.**

No frozen localization-accuracy pass/fail threshold exists.

---

## 11. Defect-to-Map Architecture

**Status:** `DEMONSTRATED / ACCEPTED P18 HANDOFF`

Presentation-safe wording:

**AegisInspect preserves a verified P15 mapped-defect record through the
P16 persistence/dashboard and P17 reporting handoff.**

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

The primary accepted P18 record has:

- machine class: **Honeycombing**;
- model: **DET-FINAL-v1**;
- confidence: **0.011138029396533966**;
- camera XYZ: approximately **[0.0056, -0.0028, 3.1251] m**;
- session-local map XYZ: approximately **[3.8882, 0.0712, -0.0035] m**;
- review state: **UNREVIEWED**.

Accepted caption:

**Accepted P18 evidence carried a machine-generated detector observation
through depth-based 3D projection into the session-local map frame and onward
to the inspection dashboard.**

The classification is low-confidence, machine-generated and `UNREVIEWED`.
The map coordinates are session-local, not globally surveyed coordinates.

---

## 12. Database / Dashboard

**Status:** `DEMONSTRATED / VERIFIED REAL HANDOFF`

Presentation-safe wording:

**AegisInspect demonstrated persistence, dashboard review and an accepted
persisted mapped-defect record.**

Verified original dashboard assets show one accepted record:

- Detector classification: **Honeycombing**;
- Confidence: **0.004553093574941158**;
- Map XYZ: **(3.9000027127470087, -0.09877989958311785, 0.0032930137079122536)**;
- Observation count: **1**;
- Review: **UNREVIEWED**;
- Model: **DET-FINAL-v1**.

This is extremely-low-confidence, unreviewed machine output. It is not a
confirmed physical defect, engineering diagnosis, severity determination,
repair recommendation or structural-safety conclusion.

---

## 13. Deterministic Reporting

**Status:** `DEMONSTRATED / VERIFIED REAL HANDOFF`

Presentation-safe wording:

**AegisInspect demonstrated deterministic reporting from the accepted
persisted/mapped evidence, with explicit human-review separation.**

Short accepted P18 report excerpt fields:

- Inspection ID: `2026091904`;
- Defect ID: `P15D-9b8ae056-1255-5cf4-ba40-e57a11f35e13`;
- machine class: `Honeycombing`;
- confidence: `0.011138029396533966`;
- coordinate frame: session-local `map`;
- review status: `UNREVIEWED`;
- model: `DET-FINAL-v1`.

Boundary:

The verified report preserves the accepted record's confidence, map
coordinates, provenance and `UNREVIEWED` state. It does not add severity,
dimensions, repair recommendations or structural-safety conclusions.

---

## 14. P19 Evaluation and 3D Status

**Status:** `MEASURED / ACCEPTED LOCALIZATION EVALUATION`

The accepted LiDAR ICP trajectory evaluation uses the frozen 3–18 s
methodology. Runtime acceptance is `PASS`; localization accuracy is
`MEASURED`, with no frozen accuracy pass/fail threshold.

P19 capstone disposition:

**FROZEN PENDING / FINAL QUANTITATIVE CORRESPONDENCE NOT COMPLETED.**

**P19 development is closed for the capstone.** No further MSI scientific
result is expected.

**Implemented / demonstrated:** depth projection, camera-frame XYZ,
map-frame XYZ, defect-to-map aggregation, persistence/reporting and full P18
core-system integration.

**Measured:** localization ATE/RPE.

**Pending:** final quantitative simulator-ground-truth correspondence
validation for absolute 3D defect-position accuracy.

Accepted wording:

**3D defect-to-map integration was demonstrated through P18; localization
accuracy was quantitatively measured. Final quantitative simulator-ground-truth
correspondence validation of absolute defect-position accuracy remained pending
at the capstone freeze.**

The frozen-pending research measurement is not a failure of the accepted P18
integrated system.

Optional technical-Q&A evidence, not a main-story slide:

- P19 qualifying receipt `0001.json`: `consecutive_valid_index = 710`;
- P19 RGB/depth binding `result.json`: RGB PASS; depth PASS;
- P19 startup alignment `result.json`: PASS;
- P19 truth `result.json`: PASS; target pixels `307,200 / 307,200`;
- operational GT publication: **NO**.

Frame these as advanced R&D validation infrastructure, not a production
runtime requirement.

P18 presentation evidence is verified and ingested. The first integrated
retry validated the same-observation data chain but recorded a missing
dashboard browser capture; it is not presented as a complete first-run PASS.
The separate dashboard-evidence completion package is PASS and the clean
repeatability run is PASS. These facts demonstrate accepted integrated
runtime, dashboard-completion and repeatability evidence, not full autonomy
or system-wide scientific validation.

---

## 15. Workstream 04 Low-Light Robustness

**Status:** `SUPPORTED / FROZEN VALIDATION BENCHMARK`

Accepted mAP50 results:

| Level | RAW | CLAHE |
| --- | ---: | ---: |
| L0 | 0.3886917344 | 0.2657391403 |
| L1 | 0.3796280361 | 0.2656420531 |
| L2 | 0.3342489847 | 0.2240838264 |
| L3 | 0.1263098877 | 0.0746161035 |
| L4 | 0.0031301687 | 0.0033883546 |

Accepted interpretation:

- low-light degradation substantially reduces detector performance;
- CLAHE does not provide general recovery;
- CLAHE is worse than RAW at L0-L3;
- L4 performance is effectively collapsed for both;
- conclusions apply only to this frozen validation benchmark.

LL-DETECTOR State A: when accepted L0-L4 evaluation arrives, add the learned
series and its provenance to the prepared chart/table.

LL-DETECTOR State B:

**Learned low-light adaptation was implemented, but final presentation-time
model training/evaluation was not completed.**

The deck remains valid in State B.

---

## 16. Limitations

Required visible limitations:

1. GYU detector metrics are not generic accuracy.
2. DamSegment zero-shot generalization is weak.
3. DamSegment scores only shared Crack and Breakage/Spalling classes.
4. simulated depth is not real-world depth validation.
5. camera XYZ alone does not establish map-frame localization.
6. DET-FINAL-v1 held-out mAP remains modest.
7. the accepted P16/P17 record is extremely-low-confidence, unreviewed machine output.
8. P19 localization is measured, not threshold-classified as accurate.
9. P19 3D correspondence validation is frozen pending at capstone close.
10. P18 demonstrates accepted runtime, dashboard-completion and repeatability evidence, not full autonomy or production readiness.
11. RAW and CLAHE performance is effectively collapsed at L4; the learned
    LL-DETECTOR result remains pending.
12. Stop C/full autonomy is not demonstrated.

---

## 17. Contributions / Engineering Decisions

Evidence-backed contributions include:

- reproducible GYU-DET data foundation;
- frozen held-out detector evaluation;
- external zero-shot generalization benchmark;
- multimodal ROS/Gazebo simulation foundation;
- simulated metric depth;
- runtime-validated camera-frame projection;
- deterministic mapping, persistence, reporting and evaluation layers;
- verified P16/P17 real handoff with dashboard review and deterministic report;
- measured LiDAR ICP localization evaluation.

Localization engineering decision:

OpenVINS was not hidden after initialization failure.

The team instrumented the initialization condition, tested one
evidence-derived correction, rejected blind tuning after the failure
persisted, preserved the downstream localization contract, and activated
the pre-designed RTAB-Map fallback.

---

## 18. Application Value, Current Capability and Next Steps

Current evidence priorities:

Demonstrated capability combines deep-learning defect detection, depth and
3D projection, localization/map-frame processing, mapped-defect persistence,
dashboard review, deterministic reporting and measured localization
evaluation.

Only remaining external late-evidence input:

- LL-DETECTOR L0-L4 training/evaluation results, if completed.

Application value:

- repeatable multimodal inspection evidence;
- traceable human review and deterministic reports;
- persistent records suitable for comparison over time;
- modular sensing, detector and localization interfaces.

These are application benefits, not proof of production readiness or market
validation.

---

## 19. Q&A / Evidence References

Keep available during Q&A:

- claim matrix;
- canonical results table;
- evidence inventory;
- limitations/Q&A source;
- P16/P17 runtime ZIP, database and deterministic-report hashes;
- canonical P17 Git preservation SHA;
- P19 localization evidence preservation commit;
- detector checkpoint hash;
- DamSegment result hashes;
- runtime validation reports.

Core message:

**Implemented is not the same as measured.**

**Simulation/runtime evidence is not the same as real-world accuracy.**

**PENDING means the result has not yet been ingested or accepted.**

Concise provenance identifiers:

- P16/P17 runtime ZIP: `df3f87f0edcea09f50394ca4ef7ca8d44e8718d93c3ca648b5a38a689f313ec2`;
- P17 deterministic report: `b5d506de2136349bafbec15aa225eb255ecb7c0ede348e2b29f98bc439c2551e`;
- P16 database: `5297ed89c50ea362ed229bc74155e1582882dd8284ebf07b2d951f27fe96bbd5`;
- P17 Git preservation: `eb4013fa236ab758c6b84e1a3ae02579bbfe488f`;
- P19 localization evidence preservation: `4c7bd79ad3b6356dff08b0adf30ece3e09a4d78a`.
