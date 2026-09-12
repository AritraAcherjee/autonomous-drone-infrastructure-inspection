# Hilti x Trimble SLAM 2026 — source record

Verified 2026-09-11. SOURCE_AND_TERMS_VERIFIED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | Hilti / Trimble / Oxford official challenge | https://hilti-trimble-challenge.com/ |
| official_source_url | https://hilti-trimble-challenge.com/ | https://hilti-trimble-challenge.com/ |
| version | 2026; all ground truth released June 16; official HF release August 6 | https://github.com/Hilti-Research/hilti-trimble-slam-challenge-2026 |
| doi | null | https://hilti-trimble-challenge.com/ |
| citation | Centanni, Zhang et al.; Hilti-Trimble-Oxford Dataset: 360 Visual-Inertial Benchmark with Floor Plan Priors for SLAM and Localization, 2026; arXiv:2607.06464. | https://github.com/Hilti-Research/hilti-trimble-slam-challenge-2026 |
| availability | Official page and download links listed; payload not tested or acquired | https://hilti-trimble-challenge.com/ |
| approximate_size | 30 runs; total bytes UNKNOWN | https://github.com/Hilti-Research/hilti-trimble-slam-challenge-2026 |
| modalities | ["Dual fisheye RGB", "IMU", "floor plans", "reference trajectories"] | https://github.com/Hilti-Research/hilti-trimble-slam-challenge-2026 |
| annotation_type | 360 visual-inertial SLAM/localization; ROS2 db3 bags, PNG/DXF floor plans, trajectories | https://github.com/Hilti-Research/hilti-trimble-slam-challenge-2026 |
| classes_or_content | Insta360 front/back 1472 x 1440 at 30 Hz; IMU 1000 Hz; construction floors | https://github.com/Hilti-Research/hilti-trimble-slam-challenge-2026 |
| license_identifier | CC-BY-NC-SA-3.0 | https://hilti-trimble-challenge.com/ |
| commercial_restriction | Non-commercial only | https://hilti-trimble-challenge.com/ |
| redistribution_notes | 2026 homepage and repository LICENSE independently state CC BY-NC-SA 3.0; non-commercial, attribution and share-alike. | https://hilti-trimble-challenge.com/ |

Code terms (separate): UNKNOWN; no code-license grant assumed

Paper terms (separate): UNKNOWN; paper accessibility does not establish dataset rights

## AEGISINSPECT ROLE / DECISION

DEFER_TO_WORKSTREAM; timing LATER; M1 acquisition required: no.

Role: Construction VIO and floor-plan localization; not LiDAR-input benchmarking. Owner: Visual-Inertial SLAM / Localization; Chat 11 / Sensor Fusion.

Hesai XT32 LiDAR generated ground truth but its data are NOT included in provided ROS2 bags. Rolling shutter, timestamp offset, unregistered design floor plans and excluded scoring runs require adapters.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- https://hilti-trimble-challenge.com/
- https://github.com/Hilti-Research/hilti-trimble-slam-challenge-2026
- https://github.com/Hilti-Research/hilti-trimble-slam-challenge-2026/blob/main/LICENSE
- https://huggingface.co/datasets/Hilti-Research/hilti-trimble-slam-challenge-2026
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
