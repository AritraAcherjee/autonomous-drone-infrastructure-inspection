# EuRoC MAV — source record

Verified 2026-09-11. SOURCE_AND_TERMS_VERIFIED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | ETH Zurich ASL / ETH Research Collection | https://projects.asl.ethz.ch/datasets/euroc-mav/ |
| official_source_url | https://projects.asl.ethz.ch/datasets/euroc-mav/ | https://projects.asl.ethz.ch/datasets/euroc-mav/ |
| version | 2016 dataset; institutional deposit 2024-09-27 | https://projects.asl.ethz.ch/datasets/euroc-mav/; https://www.research-collection.ethz.ch/entities/researchdata/bcaf173e-5dac-484b-bc37-faf97a594f1f |
| doi | 10.3929/ethz-b-000690084 | https://projects.asl.ethz.ch/datasets/euroc-mav/ |
| citation | Burri, Nikolic, Gohl, Schneider, Rehder, Omari, Achtelik, Siegwart; The EuRoC micro aerial vehicle datasets, IJRR 2016; paper DOI 10.1177/0278364915620033. | https://projects.asl.ethz.ch/datasets/euroc-mav/ |
| availability | Official page and download links listed; payload not tested or acquired | https://projects.asl.ethz.ch/datasets/euroc-mav/ |
| approximate_size | 11 benchmark sequences; institutional ZIP bundles: 12,096.15 + 5,762.35 + 5,734.81 MB; calibration 4,211.46 MB | https://www.research-collection.ethz.ch/entities/researchdata/bcaf173e-5dac-484b-bc37-faf97a594f1f; https://www.research-collection.ethz.ch/server/api/core/bitstreams/d861e63b-cfa9-4411-85a5-5ad6b3526e44/content |
| modalities | ["Monochrome stereo", "IMU", "ground-truth poses/positions", "structure scans"] | https://projects.asl.ethz.ch/datasets/euroc-mav/ |
| annotation_type | Visual-inertial odometry/SLAM, motion and structure ground truth; ASL format and ROS data | https://projects.asl.ethz.ch/datasets/euroc-mav/ |
| classes_or_content | Machine hall and Vicon rooms; Asctec Firefly MAV; stereo 20 Hz, IMU 200 Hz | https://projects.asl.ethz.ch/datasets/euroc-mav/ |
| license_identifier | InC-NC | https://www.research-collection.ethz.ch/entities/researchdata/bcaf173e-5dac-484b-bc37-faf97a594f1f |
| commercial_restriction | Non-commercial only | https://www.research-collection.ethz.ch/entities/researchdata/bcaf173e-5dac-484b-bc37-faf97a594f1f |
| redistribution_notes | ETH record states In Copyright - Non-Commercial Use Permitted. Treat commercial use and redistribution beyond identified permission as requiring clarification. | https://www.research-collection.ethz.ch/entities/researchdata/bcaf173e-5dac-484b-bc37-faf97a594f1f |

Code terms (separate): UNKNOWN; no code-license grant assumed

Paper terms (separate): UNKNOWN; paper accessibility does not establish dataset rights

## AEGISINSPECT ROLE / DECISION

DEFER_TO_WORKSTREAM; timing LATER; M1 acquisition required: no.

Role: VIO / localization benchmark. Owner: Visual-Inertial SLAM / Localization.

Independent exposure, dynamic-motion and ground-truth synchronization limits; rights statement is not a Creative Commons open-data license.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- https://projects.asl.ethz.ch/datasets/euroc-mav/
- https://www.research-collection.ethz.ch/entities/researchdata/bcaf173e-5dac-484b-bc37-faf97a594f1f
- https://www.research-collection.ethz.ch/server/api/core/bitstreams/d861e63b-cfa9-4411-85a5-5ad6b3526e44/content
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
