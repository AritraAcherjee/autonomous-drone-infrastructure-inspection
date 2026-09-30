# AegisInspect — Autonomous Multimodal Drone Infrastructure Inspection System

AegisInspect is a capstone prototype for **drone-based infrastructure inspection**. It combines structural-defect detection, simulated multimodal sensing, metric depth, localization, 3D projection, defect-to-map aggregation, persistent inspection records, dashboard review, deterministic reporting, and quantitative evaluation.

The project is intentionally evidence-driven: a feature is described as **implemented**, **demonstrated**, **measured**, or **pending** according to the evidence actually available.

## Capstone status

| Milestone | Status | Meaning |
|---|---|---|
| **Stop A** | **Reached** | Dataset foundation, frozen detector, held-out evaluation, and external generalization evidence are available. |
| **Stop B** | **Partially reached** | The core inspection pipeline was integrated and demonstrated through P18, including localization, depth/XYZ, mapping, persistence, dashboard, and reporting. Final absolute 3D defect-position validation remained pending. |
| **Stop C** | **Not reached** | Obstacle avoidance, autonomous navigation, coverage planning, and autonomous mission execution were not completed. |
| **Final product** | **Not reached** | No claim is made of a production-ready autonomous inspection drone or real-world field deployment. |

The accepted core integration is a **prototype inspection pipeline**, not a completed autonomous drone product.

## System flow

```text
Gazebo simulation
    ↓
RGB + depth + IMU + LiDAR
    ↓
RGB → DET-FINAL-v1 / YOLO26s structural-defect detection
    ↓
depth + camera intrinsics → camera-frame 3D XYZ
    ↓
LiDAR ICP local odometry
    ↓
timestamp-correct camera XYZ → session-local map XYZ
    ↓
P15 defect-to-map aggregation / persistent mapped-defect record
    ↓
P16 SQLite persistence + Streamlit dashboard
    ↓
P17 deterministic report
    ↓
P19 quantitative evaluation
```

The final operational localization backend was **LiDAR ICP**. OpenVINS Mono + IMU and RTAB-Map RGB-D + IMU were investigated earlier but did not become the accepted Stop-B runtime backend.

## What was completed

| Capability | Capstone state |
|---|---|
| GYU-DET dataset pipeline and leakage-safe splits | **Supported** |
| Structural defect detection with YOLO26s | **Supported / held-out tested** |
| External zero-shot generalization testing | **Supported** |
| Controlled low-light robustness evaluation | **Measured** |
| ROS 2 / Gazebo multimodal simulation foundation | **Supported** |
| RGB, depth, IMU, and LiDAR sensor streams | **Supported** |
| Metric depth | **Supported** |
| Pixel/depth → camera-frame XYZ | **Supported** |
| LiDAR ICP local odometry | **Measured** |
| Camera XYZ → session-local map XYZ | **Demonstrated** |
| P15 defect-to-map aggregation and persistent IDs | **Demonstrated** |
| P16 SQLite persistence and Streamlit dashboard | **Demonstrated** |
| P17 deterministic reporting | **Demonstrated** |
| P18 core-system integration and clean repeatability | **Demonstrated** |
| P19 localization ATE/RPE evaluation | **Measured** |
| Final absolute defect-position correspondence evaluation | **Frozen pending** |
| Full LiDAR SLAM / persistent 3D environmental map | **Not completed** |
| Dedicated camera+IMU+LiDAR fused estimator | **Not completed** |
| Autonomous obstacle avoidance / navigation / mission execution | **Not completed** |
| Real-drone field deployment | **Not completed** |

## Dataset

The primary detector dataset is **GYU-DET V3 baseline-v1**.

| Split | Images |
|---|---:|
| Train | 8,305 |
| Validation | 1,040 |
| Held-out test | 1,053 |
| **Total** | **10,398** |

The dataset contains **48,392 annotations** across six classes:

1. Crack
2. Breakage
3. Honeycombing
4. Hole
5. Exposed Reinforcement
6. Seepage

The held-out test contains **5,886 ground-truth instances**.

## Structural defect detector

The canonical detector is:

**DET-FINAL-v1 / YOLO26s**

Checkpoint SHA-256:

```text
4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3
```

Held-out GYU-DET test results:

| Metric | Result |
|---|---:|
| mAP50 | **0.296694** |
| mAP50-95 | **0.174800** |
| Macro precision | **0.376741** |
| Macro recall | **0.374323** |
| Mean per-class F1 | **0.355625** |

The operating confidence threshold (~**0.186186**) was selected from validation data and frozen before held-out test evaluation.

These values are **object-detection metrics**, not a generic system "accuracy" percentage.

## External generalization

The frozen detector was evaluated **zero-shot** on the external **DamSegment** benchmark without retraining or tuning on that benchmark.

Shared-class result:

| Metric | Result |
|---|---:|
| mAP50 | **0.053176** |
| mAP50-95 | **0.031340** |
| Precision | **0.253086** |
| Recall | **0.006240** |
| F1 | **0.012181** |

This result shows **weak external-domain transfer**, especially for Crack recall. The scientific run completed successfully; the performance limitation is part of the result.

## Low-light robustness

Three controlled approaches were compared:

- **RAW** — darkened input with the unchanged detector
- **CLAHE** — local-contrast enhancement before the unchanged detector
- **LL-DETECTOR** — a learned low-light-adapted presentation/demo detector

At the most severe controlled darkness level, L4:

| Approach | mAP50 |
|---|---:|
| RAW | 0.003130 |
| CLAHE | 0.003388 |
| LL-DETECTOR | **0.124129** |

The learned model substantially improved severe low-light robustness in this controlled validation experiment, with a small tradeoff under normal/mild illumination.

**Important:** LL-DETECTOR is a **presentation/demonstration validation model**. It is not the canonical DET-FINAL-v1 detector, was not evaluated on the locked GYU held-out test, and is not presented as production-qualified evidence.

## ROS 2, Gazebo, sensors, and 3D projection

The robotics stack uses:

- **ROS 2 Lyrical Luth**
- **Gazebo Sim / Jetty**
- RGB camera
- simulated metric depth
- IMU
- 3D LiDAR
- simulation clock
- TF / static TF

Key interfaces include:

| Topic / interface | Purpose |
|---|---|
| `/aegis/sensors/camera/image_raw` | RGB image stream |
| `/aegis/sensors/camera/camera_info` | Camera calibration |
| `/aegis/perception/depth/image` | Metric depth, `32FC1`, metres |
| `/aegis/sensors/imu/data` | Inertial measurements |
| `/aegis/sensors/lidar/points` | LiDAR point cloud |
| `/aegis/localization/vio/odom` | Canonical localization output contract |
| `/aegis/mapping/project_camera` | Camera-frame 3D projection service |

The localization topic retained its historical `vio` name for interface compatibility even after **LiDAR ICP** became the accepted runtime backend.

Depth and camera intrinsics are used to convert image observations into:

```text
pixel / ROI + metric depth → camera_optical_frame XYZ
```

The integrated P18 path then used the accepted localization/map relationship to transform observations into **session-local map XYZ**.

## Localization evaluation

P19 compared accepted LiDAR ICP odometry against simulation ground truth.

| Metric | Result |
|---|---:|
| ATE translation RMSE | **0.595 m** |
| ATE matched samples | 76 |
| RPE translation RMSE @ 1 s | **0.341 m** |
| RPE rotation RMSE @ 1 s | **1.707°** |
| RPE pairs | 44 |

These are **trajectory-localization metrics**. The 0.595 m ATE value is **not** a defect-position error.

No frozen localization-accuracy PASS/FAIL threshold was defined for the capstone.

## Defect-to-map, persistence, dashboard, and reporting

### P15 — Defect-to-Map Fusion

P15 consumes mapped observations and performs deterministic:

- map-frame defect handling
- spatial association
- repeated-observation aggregation
- confidence aggregation
- persistent defect identity
- replay/idempotence handling

### P16 — Database + Dashboard

P16 provides:

- SQLite persistence
- Streamlit dashboard
- inspection and structure records
- mapped-defect records
- evidence references
- explicit human review state

The dashboard does **not** fabricate engineering severity, structural safety, repair urgency, or unmeasured dimensions.

### P17 — Deterministic Reporting

P17 generates deterministic reports from persisted inspection data.

The reporting layer intentionally preserves stored facts and avoids inventing:

- crack width
- severity
- repair action
- structural-safety conclusions
- engineering diagnoses

An LLM is not required for the accepted reporting path.

### P18 — Core Integration

P18 demonstrated the implemented inspection chain through runtime evidence and clean repeatability.

The accepted P18 evidence supports **core-system integration**, dashboard completion, and repeatability. It does **not** establish full autonomy, production readiness, field validation, or absolute 3D defect-position accuracy.

## P19 3D evaluation boundary

A final quantitative comparison between mapped defect XYZ and simulator ground-truth defect XYZ required an **explicit accepted correspondence** between each mapped defect and its ground-truth defect identity.

That correspondence was not preserved in acceptable immutable evidence before the capstone freeze.

Therefore:

**P19 3D defect-position evaluation = FROZEN PENDING**

Do not infer an absolute defect-position error from localization ATE/RPE.

## Important limitations

The following were **not completed or not validated as final-product capabilities**:

- full LiDAR SLAM
- persistent point-cloud / voxel / occupancy map
- dedicated multimodal camera+IMU+LiDAR fused estimator
- accepted video tracking / ByteTrack pipeline
- segmentation workstream
- obstacle avoidance
- autonomous path planning
- autonomous navigation
- coverage planning
- autonomous mission execution
- real-drone hardware integration
- real-world field trials
- final absolute 3D defect-position accuracy validation
- production safety, regulatory, and commercial hardening

AegisInspect should therefore be described as an **integrated infrastructure-inspection prototype**, not a production-ready autonomous drone system.

## Repository layout

```text
configs/                         frozen experiment and evaluation configuration
data/                            manifests and dataset metadata
dashboard/                       Streamlit review dashboard
database/                        database schema and persistence documentation
docs/
  data/                          dataset provenance, licensing, and acquisition policy
  detection/                     detector training/freeze documentation
  experiments/                   experiment analysis
  implementation_reports/       ROS/depth/runtime engineering evidence
  presentation/                 presentation claim/evidence framework
outputs/                         accepted evaluation and validation artifacts
ros2_ws/                         ROS 2 / Gazebo packages
scripts/                         training, evaluation, analysis, and validation entry points
src/
  defect_mapping/                P15 persistent defect aggregation
  detection/                     detector training and generalization code
  evaluation/                    P19 evaluation framework
  integrations/                  workstream adapters
  reporting/                     P17 deterministic reporting
  storage/                       P16 persistence layer
tests/                           dataset, detector, mapping, storage, reporting, integration, and evaluation tests
```

## Provenance and reproducibility

AegisInspect records provenance so a result can be traced back through:

```text
dataset
→ split/version
→ model checkpoint
→ code commit
→ configuration
→ environment
→ evaluation protocol
→ result artifact
```

Reproducibility controls include:

- frozen dataset splits
- Git commit SHAs
- SHA-256 hashes for key checkpoints and evidence
- fixed configurations
- deterministic seeds where applicable
- one-time held-out evaluation controls
- experiment manifests
- fail-closed validation
- saved result artifacts and evidence packages

Historical branch names, experiment IDs, status enums, and exact execution paths are retained when they are part of provenance. Some therefore contain earlier internal identifiers even though professor-facing documentation uses descriptive workstream names.

## Final capstone evidence

The final capstone presentation/evidence freeze is preserved at:

**`P20/deck-draft` @ `9fc8d8e2fed3ba4a16d2f2e59ab94b776dcdfede`**

Final presentation evidence:
https://github.com/AritraAcherjee/autonomous-drone-infrastructure-inspection/tree/9fc8d8e2fed3ba4a16d2f2e59ab94b776dcdfede/docs/presentation

P18 presentation evidence:
https://github.com/AritraAcherjee/autonomous-drone-infrastructure-inspection/tree/9fc8d8e2fed3ba4a16d2f2e59ab94b776dcdfede/outputs/presentation/p18_evidence

The default `main` branch is the shared project branch. Some late capstone evidence was intentionally preserved on dedicated workstream/presentation branches rather than merged into `main`.

## Suggested review path

For a quick technical review:

1. Read this README.
2. Review `docs/presentation/` at the final capstone evidence commit.
3. Review `src/detection/` and the held-out detector evidence.
4. Review `ros2_ws/` for the ROS 2 / Gazebo platform.
5. Review `src/defect_mapping/`, `src/storage/`, and `src/reporting/`.
6. Review P18 presentation evidence for the integrated pipeline.
7. Review `src/evaluation/` and the P19 evidence boundaries.

## Development scope

A logical post-capstone continuation would focus on:

```text
mature SLAM / global 3D mapping
→ multimodal localization fusion
→ obstacle avoidance
→ autonomous navigation and coverage
→ real-drone deployment
→ field validation
→ production hardening
```

---

**AegisInspect demonstrates how defect perception can be connected to spatial localization, persistent inspection records, human review, and deterministic reporting while keeping measured results and unfinished capabilities explicitly separated.**
