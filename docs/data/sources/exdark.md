# ExDark — source record

Verified 2026-09-11. SOURCE_AND_TERMS_VERIFIED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | Universiti Malaya / Loh and Chan official dataset repository | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset |
| official_source_url | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset |
| version | 2018 release; dataset link updated 2022-09-02 | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset |
| doi | null | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset |
| citation | Yuen Peng Loh, Chee Seng Chan; Getting to Know Low-light Images with The Exclusively Dark Dataset; CVIU 178 (2019), 30-42; DOI 10.1016/j.cviu.2018.10.010. | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset |
| availability | Official page and download links listed; payload not tested or acquired | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset |
| approximate_size | 7,363 images; author lists archive as 1.5Gb; ground truth 4.2Mb (units as written); 3000 train / 1800 validation / 2563 test | https://raw.githubusercontent.com/cs-chan/Exclusively-Dark-Image-Dataset/master/Dataset/README.md; https://raw.githubusercontent.com/cs-chan/Exclusively-Dark-Image-Dataset/master/Groundtruth/README.md |
| modalities | ["RGB low-light"] | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset |
| annotation_type | Image class labels and object boxes in TXT [left, top, width, height]; lighting and experimental-split labels | https://raw.githubusercontent.com/cs-chan/Exclusively-Dark-Image-Dataset/master/Dataset/README.md; https://raw.githubusercontent.com/cs-chan/Exclusively-Dark-Image-Dataset/master/Groundtruth/README.md |
| classes_or_content | Bicycle, Boat, Bottle, Bus, Car, Cat, Chair, Cup, Dog, Motorbike, People, Table; 10 lighting types from Low to Twilight | https://raw.githubusercontent.com/cs-chan/Exclusively-Dark-Image-Dataset/master/Dataset/README.md; https://raw.githubusercontent.com/cs-chan/Exclusively-Dark-Image-Dataset/master/Groundtruth/README.md |
| license_identifier | LicenseRef-ExDark-NC | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset/blob/master/Dataset/README.md |
| commercial_restriction | Non-commercial only | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset/blob/master/Dataset/README.md |
| redistribution_notes | Dataset README explicitly permits only non-commercial research; contact Chee Seng Chan for commercial use. Redistribution rights are not expressly specified by that dataset statement; do not infer unrestricted redistribution from the code license. | https://github.com/cs-chan/Exclusively-Dark-Image-Dataset/blob/master/Dataset/README.md |

Code terms (separate): BSD-3-Clause repository software license, separate from explicit dataset NC research terms

Paper terms (separate): UNKNOWN; paper accessibility does not establish dataset rights

## AEGISINSPECT ROLE / DECISION

OPTIONAL; timing NOT_REQUIRED; M1 acquisition required: no.

Role: Optional low-light object-detection domain shift experiments. Owner: Chat 05 / Low-Light Vision (optional extension).

No structural-defect labels. Dataset-specific README restricts use to non-commercial research; root BSD software license does not override dataset terms. Commercial usage needs author contact.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- https://github.com/cs-chan/Exclusively-Dark-Image-Dataset
- https://github.com/cs-chan/Exclusively-Dark-Image-Dataset/blob/master/Dataset/README.md
- https://github.com/cs-chan/Exclusively-Dark-Image-Dataset/blob/master/LICENSE
- https://raw.githubusercontent.com/cs-chan/Exclusively-Dark-Image-Dataset/master/Dataset/README.md
- https://raw.githubusercontent.com/cs-chan/Exclusively-Dark-Image-Dataset/master/Groundtruth/README.md
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
