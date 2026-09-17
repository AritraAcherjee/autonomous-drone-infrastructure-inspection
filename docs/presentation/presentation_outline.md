# AegisInspect Presentation Content Outline

Final title / highest Stop-level claim:

**PENDING 00 CONTROL CENTER DECISION**

This is content source material, not a frozen final deck.

---

## Slide 1 - Problem / Motivation

**Evidence scope:** architecture/context

Infrastructure inspection can require difficult access, repeated visual
review and consistent defect documentation.

AegisInspect explores a modular drone-inspection pipeline combining vision,
simulation, spatial reasoning, persistent records and evidence-backed
evaluation.

**Do not claim:** validated full autonomous inspection.

---

## Slide 2 - AegisInspect Objective

Build an inspection system architecture that can:

1. acquire RGB / depth / IMU / LiDAR observations;
2. detect structural defects;
3. estimate or consume spatial pose/depth;
4. associate observations over time;
5. map defect observations into persistent records;
6. support human review and deterministic reporting;
7. evaluate each subsystem using explicit evidence contracts.

**Status:** mixed implementation; incomplete segments must remain labelled.

---

## Slide 3 - System Architecture

Recommended visual pipeline:

Sensors
-> localization / mapping
-> perception
-> tracking / depth
-> defect-to-map fusion
-> persistence / dashboard
-> deterministic reporting
-> evaluation evidence

Suggested badges:

- Detector: `SUPPORTED / REAL_HELD_OUT`
- External generalization: `SUPPORTED / EXTERNAL_BENCHMARK`
- ROS/Gazebo/depth/projection: `SUPPORTED / SIMULATION_RUNTIME`
- P15/P16/P17/P19: `IMPLEMENTED_NOT_REAL_EVIDENCE`
- VIO real metrics: `PENDING_NOT_YET_VERIFIED`
- End-to-end mission: `PENDING_NOT_YET_VERIFIED`

Architecture does not imply every segment has completed real validation.

---

## Slide 4 - Dataset / Six Defect Classes

**Badge:** `SUPPORTED / DATA_FOUNDATION`

Approved GYU-DET V3 baseline-v1:

- 10,398 supervised images
- 8,305 train
- 1,040 validation
- 1,053 test
- 48,392 annotations
- 6 classes

Classes:

1. Crack
2. Breakage
3. Honeycombing
4. Hole
5. Exposed Reinforcement
6. Seepage

Speaker note:

These are data-foundation facts, not detector-performance values.

---

## Slide 5 - Detector Training + Evaluation Methodology

Model:

`DET-FINAL-v1 / YOLO26s`

Methodology points:

- frozen checkpoint before one-time held-out test access;
- 1,053 held-out test images;
- 5,886 GT instances;
- validation-selected diagnostic threshold;
- no test-threshold optimization;
- retained provenance and checkpoint hashing.

Speaker note:

Deployment threshold remains unresolved.

---

## Slide 6 - GYU Held-Out Detector Results

**Badge:** `SUPPORTED / REAL_HELD_OUT`

Primary metrics:

- mAP50: **0.29669431228680787**
- mAP50-95: **0.17480040543737643**

At validation diagnostic confidence `0.18618618618618618`:

- macro precision: **0.37674095487474335**
- macro recall: **0.37432339044543**
- mean per-class F1: **0.3556245448108634**

Presentation label:

**DET-FINAL-v1 held-out GYU-DET detection performance**

Do not call these metrics "accuracy."

---

## Slide 7 - External Generalization: DamSegment

**Badge:** `SUPPORTED / EXTERNAL_BENCHMARK`

Experiment:

`GEN-DAMSEGMENT-ZS-001`

Scope:

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

Required interpretation:

DET-FINAL-v1 shows weak zero-shot external-domain transfer, particularly
for Crack recall.

This limitation is a scientific result and should not be hidden.

---

## Slide 8 - ROS/Gazebo Simulation Foundation

**Badge:** `SUPPORTED / SIMULATION_RUNTIME`

Verified foundation includes:

- ROS 2 Lyrical
- Gazebo Sim 10.5.0
- RGB
- CameraInfo
- IMU
- 3D LiDAR
- depth
- `/clock`
- TF/static TF

Observed GUI runtime rates may be shown only as runtime observations.

Do not present them as configured target rates or real-drone sensor rates.

---

## Slide 9 - Depth + Camera-Frame 3D Projection

**Badge:** `SUPPORTED / SIMULATION_RUNTIME`

Simulated depth:

- `sensor_msgs/Image`
- `32FC1`
- metres
- `camera_optical_frame`
- 640 x 480
- RGB/depth/CameraInfo geometry validated
- 103 colcon tests, zero failures/errors/skips

Camera-frame projection:

- live `/aegis/mapping/project_camera`
- `aegisinspect_interfaces/srv/ProjectCamera`
- camera-frame XYZ
- 196 MSI WSL colcon tests, zero failures/errors/skips

Explicit boundary:

This does not demonstrate real-world depth accuracy or map-frame defect
localization accuracy.

---

## Slide 10 - Localization / VIO

**Badge:** `PENDING_NOT_YET_VERIFIED / PENDING`

Architecture/status may be shown.

Real quantitative fields must display:

- ATE: **PENDING**
- RPE translation: **PENDING**
- RPE rotation: **PENDING**
- timestamp-alignment coverage: **PENDING**

Do not show synthetic P19 fixtures as real VIO results.

---

## Slide 11 - Defect-to-Map + Persistence

P15:

**Badge:** `IMPLEMENTED_NOT_REAL_EVIDENCE / IMPLEMENTATION_TEST`

Presentation-safe wording:

"AegisInspect includes implemented deterministic defect-to-map fusion
software."

P16 persistence may be shown alongside it.

Real map-localization accuracy remains pending.

---

## Slide 12 - Dashboard / Human Review

**Badge:** `IMPLEMENTED_NOT_REAL_EVIDENCE / SYNTHETIC_DEMO`

Presentation-safe wording:

"AegisInspect includes a persistent inspection database and review
dashboard, demonstrated using synthetic mapped-defect records."

Current documented demo:

- one synthetic structure;
- one synthetic inspection;
- three synthetic mapped defects;
- four synthetic evidence rows.

Machine-created defects begin `UNREVIEWED`.

Do not label these records as field inspection evidence.

---

## Slide 13 - Deterministic Reporting

**Badge:** `IMPLEMENTED_NOT_REAL_EVIDENCE / IMPLEMENTATION_TEST`

Presentation-safe wording:

"AegisInspect includes deterministic report-generation software with
fail-closed validation and explicit human-review separation."

Do not claim a completed autonomous-inspection report from a validated
end-to-end mission.

---

## Slide 14 - Evaluation Framework / P19

**Badge:** `IMPLEMENTED_NOT_REAL_EVIDENCE / IMPLEMENTATION_TEST`

Canonical spatial-evaluation tooling supports future calculation of:

- VIO ATE;
- VIO RPE;
- timestamp-alignment coverage;
- mean / median / RMSE / P95 defect-location error;
- matched and unmatched defect counts.

Current real project values:

**PENDING**

---

## Slide 15 - Integrated Demo / System Status

Present subsystem status, not an unsupported completion claim.

Currently evidence-backed:

- data foundation;
- internal held-out detection;
- DamSegment external benchmark;
- ROS/Gazebo sensor foundation;
- simulated depth;
- camera-frame projection.

Implemented but not yet real-performance evidence:

- P15 defect-to-map software;
- P16 persistence/dashboard;
- P17 deterministic reporting;
- P19 spatial-evaluation tooling.

Pending:

- accepted real VIO metrics;
- real 3D defect-localization accuracy;
- validated full P18 end-to-end mission.

---

## Slide 16 - Limitations

Minimum visible limitations:

1. GYU held-out detector metrics are not generic "accuracy."
2. DamSegment zero-shot transfer is weak.
3. DamSegment covers only shared Crack and Breakage/Spalling classes.
4. Simulated depth is not real-world depth validation.
5. Camera-frame XYZ is not map-frame localization.
6. P16 demo records are synthetic.
7. P15/P17 implementation does not prove an integrated mission.
8. Real VIO ATE/RPE remains pending.
9. Real 3D defect-localization accuracy remains pending.
10. Full autonomous mission completion requires P18 evidence.

---

## Slide 17 - Contributions / Next Steps

Evidence-backed contributions:

- reproducible data foundation;
- held-out detector evaluation with frozen provenance;
- external zero-shot generalization benchmark;
- ROS/Gazebo multimodal sensor foundation;
- simulated metric depth;
- camera-frame 3D projection;
- deterministic mapping/persistence/reporting/evaluation software layers.

Next evidence priorities:

- accepted MSI VIO trajectory evidence;
- real ATE/RPE;
- explicit GT-linked defect localization evaluation;
- P18 integrated mission evidence.

---

## Slide 18 - Q&A / Evidence References

Keep claim matrix and evidence inventory available during Q&A.

Key principle:

**Implemented is not the same as measured.**
**Simulated is not the same as real-world validated.**
**PENDING means not yet measured/accepted.**

Final title / highest Stop-level statement remains controlled by 00.
