# FLIR ADAS — source record

Verified 2026-09-11. SOURCE_VERIFIED_LICENSE_UNRESOLVED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | Teledyne FLIR OEM official dataset page | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| official_source_url | https://oem.flir.com/solutions/automotive/adas-dataset-form/ | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| version | Current expanded 26,442-frame listing; numeric release label not specified | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| doi | null | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| citation | Teledyne FLIR Thermal Dataset for Algorithm Training (official supplier listing). | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| availability | Official listing accessible via browser/search; sign-in/account notice and registration form present; gated payload/terms not tested | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| approximate_size | 26,442 frames; 520,000 boxes; 9,711 thermal + 9,233 RGB stills and 7,498 video frames; archive bytes UNKNOWN | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| modalities | ["Visible RGB", "thermal"] | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| annotation_type | Object bounding boxes; MSCOCO and Conservator JSON; thermal TIFF/JPEG and RGB JPEG | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| classes_or_content | Person, bike, car, motorcycle, bus, train, truck, traffic light, fire hydrant, street sign, dog, skateboard, stroller, scooter, other vehicle | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| license_identifier | LICENSE_UNRESOLVED | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| commercial_restriction | UNKNOWN | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |
| redistribution_notes | LICENSE STATUS: UNRESOLVED. No explicit dataset reuse grant recovered from public landing/form. Preserve and review actual download agreement before acquiring; commercial and redistribution rights UNKNOWN. | https://oem.flir.com/solutions/automotive/adas-dataset-form/ |

Code terms (separate): UNKNOWN; no code-license grant assumed

Paper terms (separate): UNKNOWN; paper accessibility does not establish dataset rights

## AEGISINSPECT ROLE / DECISION

HOLD; timing DO_NOT_ACQUIRE_YET; M1 acquisition required: no.

Role: Optional thermal/multimodal object-perception extension only. Owner: Thermal / Multimodal extension.

Automotive objects are not infrastructure thermal-defect ground truth. Registration/download form does not establish commercial or redistribution rights; no terms accepted or account created.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- https://oem.flir.com/solutions/automotive/adas-dataset-form/
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
