# DeepCrack — source record

Verified 2026-09-11. SOURCE_AND_TERMS_VERIFIED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | Yahui Liu original author dataset repository | https://github.com/yhlleo/DeepCrack |
| official_source_url | https://github.com/yhlleo/DeepCrack | https://github.com/yhlleo/DeepCrack |
| version | Liu et al. Neurocomputing 2019 dataset (537 images) | https://github.com/yhlleo/DeepCrack |
| doi | null | https://github.com/yhlleo/DeepCrack |
| citation | Yahui Liu, Jian Yao, Xiaohu Lu, Renping Xie, Li Li; DeepCrack: A Deep Hierarchical Feature Learning Architecture for Crack Segmentation, Neurocomputing 338 (2019), 139-153. | https://github.com/yhlleo/DeepCrack |
| availability | Official page and download links listed; payload not tested or acquired | https://github.com/yhlleo/DeepCrack |
| approximate_size | 537 images at 544 x 384; 300 train / 237 test; archive bytes UNKNOWN | https://yhlleo.github.io/papers/DeepCrack-Neurocomputing2019.pdf |
| modalities | ["RGB", "binary masks"] | https://github.com/yhlleo/DeepCrack |
| annotation_type | Pixel-wise crack segmentation | https://github.com/yhlleo/DeepCrack |
| classes_or_content | Crack / non-crack pixels across concrete/asphalt scenes | https://github.com/yhlleo/DeepCrack |
| license_identifier | LicenseRef-DeepCrack-NC | https://github.com/yhlleo/DeepCrack/blob/master/README.md |
| commercial_restriction | Non-commercial only | https://github.com/yhlleo/DeepCrack/blob/master/README.md |
| redistribution_notes | Explicit dataset use restricted to non-commercial research and education. No blanket redistribution or commercial grant inferred. | https://github.com/yhlleo/DeepCrack/blob/master/README.md |

Code terms (separate): DeepSegmentor has a separate BSD-style software grant and third-party notices; it does not replace dataset NC terms.

Paper terms (separate): Elsevier 2019 all rights reserved, shown in author-hosted paper

## AEGISINSPECT ROLE / DECISION

DEFER_TO_WORKSTREAM; timing LATER; M1 acquisition required: no.

Role: Crack segmentation benchmark. Owner: Chat 06 / Defect Segmentation.

This registry explicitly selects Liu et al., not Zou et al. TIP 2019 (CrackTree260, CRKWH100, CrackLS315, Stone331). Authors own only part of original images; upstream-image permissions/redistribution need review before broader reuse.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- https://github.com/yhlleo/DeepCrack
- https://github.com/yhlleo/DeepCrack/blob/master/README.md
- https://yhlleo.github.io/papers/DeepCrack-Neurocomputing2019.pdf
- https://github.com/qinnzou/DeepCrack
- https://github.com/yhlleo/DeepSegmentor/blob/master/LICENSE
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
