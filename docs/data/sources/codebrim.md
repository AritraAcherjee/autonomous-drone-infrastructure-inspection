# CODEBRIM — source record

Verified 2026-09-11. SOURCE_AND_TERMS_VERIFIED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | Zenodo / original authors | https://zenodo.org/records/2620293 |
| official_source_url | https://zenodo.org/records/2620293 | https://zenodo.org/records/2620293 |
| version | 1.0 | https://zenodo.org/api/records/2620293 |
| doi | 10.5281/zenodo.2620293 | https://zenodo.org/records/2620293 |
| citation | Official dataset title: CODEBRIM: COncrete DEfect BRidge IMage Dataset. Martin Mundt, Sagnik Majumder, Sreenivas Murali, Panagiotis Panetsos, Visvanathan Ramesh; Goethe University / Egnatia Odos; CVPR 2019, Meta-learning Convolutional Neural Architectures for Multi-target Concrete Defect Classification with CODEBRIM. | https://zenodo.org/records/2620293 |
| availability | Official page and download links listed; payload not tested or acquired | https://zenodo.org/records/2620293 |
| approximate_size | 1,590 source images / 30 bridges; original-image ZIP 8.3 GB; four alternative packages total 36.4 GB | https://zenodo.org/records/2620293; https://arxiv.org/html/1904.08486v1 |
| modalities | ["RGB"] | https://zenodo.org/records/2620293 |
| annotation_type | Original images with boxes; extracted crops have multi-label classification targets; no masks established | https://zenodo.org/records/2620293 |
| classes_or_content | Crack; spallation; efflorescence; exposed bars; corrosion stain; background | https://arxiv.org/html/1904.08486v1 |
| license_identifier | LicenseRef-CODEBRIM-NC | https://zenodo.org/records/2620293/files/license.md?download=1 |
| commercial_restriction | Non-commercial only | https://zenodo.org/records/2620293/files/license.md?download=1 |
| redistribution_notes | Custom terms: non-commercial research/education only; no commercial gain from derivatives; no dataset or modified-dataset redistribution. Colleagues must accept terms; data-free models/annotations may be shared under the same terms. Cite authors; record acceptance/any required permission before acquisition. | https://zenodo.org/records/2620293/files/license.md?download=1 |

Code terms (separate): Separate repository custom research/educational terms; adapted ENAS code has additional upstream terms.

Paper terms (separate): arXiv version: perpetual non-exclusive arXiv distribution license, not dataset permission

## AEGISINSPECT ROLE / DECISION

DEFER_TO_WORKSTREAM; timing LATER; M1 acquisition required: no.

Role: Protected external/domain-shift evaluation after detector baseline freeze. Owner: Chat 03 / Defect Detection: external evaluation.

Partial taxonomy overlap; multi-label regions differ from YOLO single-class boxes. Define compatible metrics before predictions. Never train/tune baseline on this holdout.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- https://zenodo.org/records/2620293
- https://zenodo.org/records/2620293/files/license.md?download=1
- https://arxiv.org/html/1904.08486v1
- https://github.com/ccc-frankfurt/meta-learning-CODEBRIM
- https://zenodo.org/api/records/2620293
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
