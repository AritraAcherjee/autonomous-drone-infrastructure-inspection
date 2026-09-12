# TUM RGB-D — source record

Verified 2026-09-11. SOURCE_AND_TERMS_VERIFIED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | TUM Computer Vision Group | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |
| official_source_url | https://cvg.cit.tum.de/data/datasets/rgbd-dataset | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |
| version | RGB-D benchmark; 2011/2012 sequence collections; no single version number | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |
| doi | null | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |
| citation | Sturm, Engelhard, Endres, Burgard, Cremers; A Benchmark for the Evaluation of RGB-D SLAM Systems, IROS 2012. | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |
| availability | Official page and download links listed; payload not tested or acquired | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |
| approximate_size | Per-sequence sizes published; e.g. freiburg2_rpy_validation approximately 2.06 GB; aggregate UNKNOWN | https://cvg.cit.tum.de/data/datasets/rgbd-dataset/download |
| modalities | ["RGB", "depth", "trajectories", "accelerometer"] | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |
| annotation_type | RGB-D SLAM/odometry ground truth; sequence archives, PNG images/timestamp lists and ROS bags | https://cvg.cit.tum.de/data/datasets/rgbd-dataset/file_formats |
| classes_or_content | Freiburg1/2/3 sequences: indoor motion, structure/texture and dynamic people | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |
| license_identifier | CC-BY-4.0 | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |
| commercial_restriction | No non-commercial restriction in the identified grant; other rights may apply | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |
| redistribution_notes | Current official site: data CC BY 4.0 unless otherwise stated; retain attribution/license/modification notices. Historical 2012 workshop paper says CC BY 3.0; record acquisition-time terms. | https://cvg.cit.tum.de/data/datasets/rgbd-dataset |

Code terms (separate): BSD-2-Clause, explicitly separate on official benchmark page

Paper terms (separate): UNKNOWN; paper accessibility does not establish dataset rights

## AEGISINSPECT ROLE / DECISION

DEFER_TO_WORKSTREAM; timing LATER; M1 acquisition required: no.

Role: Depth / RGB-D SLAM validation. Owner: Depth / RGB-D SLAM.

Indoor RGB-D sensor domain differs from aerial inspection; depth/trajectory benchmark, not structural defect labels. Respect any sequence-specific exceptions.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- https://cvg.cit.tum.de/data/datasets/rgbd-dataset
- https://cvg.cit.tum.de/data/datasets/rgbd-dataset/download
- https://cvg.cit.tum.de/data/datasets/rgbd-dataset/file_formats
- https://cvg.cit.tum.de/_media/spezial/bib/sturm12iros_ws.pdf
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
