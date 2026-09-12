# TU Delft ODA — source record

Verified 2026-09-11. SOURCE_AND_TERMS_VERIFIED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | TU Delft / 4TU.ResearchData | https://data.4tu.nl/articles/_/14214236/1 |
| official_source_url | https://data.4tu.nl/articles/_/14214236/1 | https://data.4tu.nl/articles/_/14214236/1 |
| version | 1 (2021-03-19) | https://data.4tu.nl/articles/_/14214236/1 |
| doi | 10.4121/14214236.v1 | https://data.4tu.nl/articles/_/14214236/1 |
| citation | Julien Dupeyroux, Nikhil Wessendorp, Raoul Dinaux, Guido De Croon; The Obstacle Detection and Avoidance Dataset for Drones (2021). Associated 2022 paper DOI 10.1145/3522784.3522786. | https://data.4tu.nl/articles/_/14214236/1 |
| availability | Official page and download links listed; payload not tested or acquired | https://data.4tu.nl/articles/_/14214236/1 |
| approximate_size | 1,369 trials; archive 98,186,579,073 bytes (98.19 decimal GB) | https://data.4tu.nl/articles/_/14214236/1; https://github.com/tudelft/ODA_Dataset |
| modalities | ["RGB", "DVS events", "24 GHz radar", "6-axis IMU", "OptiTrack"] | https://github.com/tudelft/ODA_Dataset |
| annotation_type | Obstacle positions and drone position/attitude; ROS bags/CSV; RGB AVI video | https://github.com/tudelft/ODA_Dataset |
| classes_or_content | Indoor MAV flights toward one or two poles, full/dim light; turn left/right or continue | https://github.com/tudelft/ODA_Dataset |
| license_identifier | CC0-1.0 | https://data.4tu.nl/articles/_/14214236/1 |
| commercial_restriction | No non-commercial restriction in the identified grant; other rights may apply | https://data.4tu.nl/articles/_/14214236/1 |
| redistribution_notes | Institutional record explicitly CC0 1.0; no NC limitation. Record creator citation for scientific provenance; separate software licenses not inferred. | https://data.4tu.nl/articles/_/14214236/1 |

Code terms (separate): UNKNOWN; no code-license grant assumed

Paper terms (separate): UNKNOWN; paper accessibility does not establish dataset rights

## AEGISINSPECT ROLE / DECISION

DEFER_TO_WORKSTREAM; timing LATER; M1 acquisition required: no.

Role: Obstacle detection/avoidance and aerial perception validation. Owner: Autonomous Navigation / Obstacle Detection.

Narrow indoor pole task and event/radar sensor mismatch; samples 593-629 lack obstacle coordinates. Useful for navigation methodology, not proof of outdoor collision avoidance.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- https://data.4tu.nl/articles/_/14214236/1
- https://github.com/tudelft/ODA_Dataset
- https://api.datacite.org/dois/10.4121/14214236.v1
- https://research.tudelft.nl/en/publications/a-novel-obstacle-detection-and-avoidance-dataset-for-drones/
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
