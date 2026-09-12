# AegisInspect Gazebo-generated dataset — source record

Verified 2026-09-11. INTERNAL_PLANNED_ASSET_LICENSE_UNRESOLVED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

Internal modalities and labels below are project requirements, not claims that generated data already exist. Gazebo documentation supports the simulator/Fuel mechanism only.

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | AegisInspect project / Gazebo simulation | docs/data/sources/aegisinspect_gazebo_dataset.md |
| official_source_url | docs/data/sources/aegisinspect_gazebo_dataset.md | docs/data/sources/aegisinspect_gazebo_dataset.md |
| version | null | docs/data/sources/aegisinspect_gazebo_dataset.md |
| doi | null | docs/data/sources/aegisinspect_gazebo_dataset.md |
| citation | AegisInspect project owner; internal requirement established by this scope decision. | docs/data/sources/aegisinspect_gazebo_dataset.md |
| availability | PLANNED_INTERNAL; not generated/acquired in this sweep | docs/data/sources/aegisinspect_gazebo_dataset.md |
| approximate_size | NOT_GENERATED; size TBD by simulation scenario specification | docs/data/sources/aegisinspect_gazebo_dataset.md |
| modalities | ["PLANNED RGB", "PLANNED depth", "PLANNED LiDAR", "PLANNED IMU", "PLANNED poses/ground truth"] | docs/data/sources/aegisinspect_gazebo_dataset.md |
| annotation_type | Planned synchronized simulation streams; potential segmentation/detection labels | docs/data/sources/aegisinspect_gazebo_dataset.md |
| classes_or_content | Planned inspection worlds, navigation scenarios and integration tests | docs/data/sources/aegisinspect_gazebo_dataset.md |
| license_identifier | LICENSE_UNRESOLVED | docs/data/sources/aegisinspect_gazebo_dataset.md |
| commercial_restriction | UNKNOWN; depends on selected upstream assets | docs/data/sources/aegisinspect_gazebo_dataset.md |
| redistribution_notes | LICENSE STATUS: UNRESOLVED. No blanket generated-data license. Redistribution depends on worlds, models, meshes, textures, plugins and imported assets; upstream asset-license manifest required before generation intended for sharing. | docs/data/sources/aegisinspect_gazebo_dataset.md |

Code terms (separate): UNKNOWN; no code-license grant assumed

Paper terms (separate): UNKNOWN; paper accessibility does not establish dataset rights

## AEGISINSPECT ROLE / DECISION

DEFER_TO_WORKSTREAM; timing LATER; M1 acquisition required: no.

Role: REQUIRED_LATER for integrated system verification. Owner: Simulation / Navigation / Sensor Fusion / 3D Mapping / Integration / System Testing.

Planned internal dataset, not an existing third-party release. Simulation cannot establish real-world generalization or replace real defects. Asset inventory not yet fixed.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- docs/data/sources/aegisinspect_gazebo_dataset.md
- https://gazebosim.org/docs/latest/fuel_insert/
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
