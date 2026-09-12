# Hilti SLAM 2022 — source record

Verified 2026-09-11. SOURCE_AND_TERMS_VERIFIED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | Hilti official challenge and Hilti-Research repository | https://www.hilti-challenge.com/dataset-2022 |
| official_source_url | https://www.hilti-challenge.com/dataset-2022 | https://www.hilti-challenge.com/dataset-2022 |
| version | 2022 | https://www.hilti-challenge.com/dataset-2022 |
| doi | null | https://www.hilti-challenge.com/dataset-2022 |
| citation | Zhang et al.; Hilti-Oxford Dataset: A Millimeter-Accurate Benchmark for SLAM, RA-L 2023; DOI 10.1109/LRA.2022.3226077. | https://www.hilti-challenge.com/dataset-2022 |
| availability | Official page and download links listed; payload not tested or acquired | https://www.hilti-challenge.com/dataset-2022 |
| approximate_size | 8 challenge + 8 additional sequences; individual listed rosbag sizes 6-80 GB; aggregate not assumed | https://www.hilti-challenge.com/dataset-2022 |
| modalities | ["Cameras", "LiDAR", "IMU", "ground-truth positions"] | https://www.hilti-challenge.com/dataset-2022 |
| annotation_type | ROS bags; calibrated SLAM streams; sparse surveyed 3DoF ground truth; selected extra 6DoF trajectories and E57 reference scans | https://www.hilti-challenge.com/dataset-2022 |
| classes_or_content | Handheld five-camera Alphasense, Hesai PandarXT-32 and IMU; Oxford theatre/construction | https://www.hilti-challenge.com/dataset-2022 |
| license_identifier | CC-BY-NC-SA-3.0 | https://www.hilti-challenge.com/dataset-2022 |
| commercial_restriction | Non-commercial only | https://www.hilti-challenge.com/dataset-2022 |
| redistribution_notes | This release page explicitly licenses its datasets/benchmarks CC BY-NC-SA 3.0: attribution, non-commercial use, share-alike for distributed adaptations. | https://www.hilti-challenge.com/dataset-2022 |

Code terms (separate): UNKNOWN; no code-license grant assumed

Paper terms (separate): UNKNOWN; paper accessibility does not establish dataset rights

## AEGISINSPECT ROLE / DECISION

DEFER_TO_WORKSTREAM; timing LATER; M1 acquisition required: no.

Role: Construction SLAM and sensor-fusion evaluation. Owner: Chat 10 / LiDAR SLAM + Mapping; Chat 11 / Sensor Fusion.

Large calibrated streams; sparse ground truth is not dense pose truth. Choose sequences and sensor adapters later; no first-detector requirement.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- https://www.hilti-challenge.com/dataset-2022
- https://github.com/Hilti-Research/hilti-slam-challenge-2022
- https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
