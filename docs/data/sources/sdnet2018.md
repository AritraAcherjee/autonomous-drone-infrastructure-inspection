# SDNET2018 — source record

Verified 2026-09-11. SOURCE_AND_TERMS_VERIFIED. This is a source/terms review, not downloaded-data validation.

## AUTHORITATIVE SOURCE FACTS

| Field | Finding | Evidence URL or internal record |
| --- | --- | --- |
| official_source | Utah State University institutional dataset record | https://digitalcommons.usu.edu/all_datasets/48/ |
| official_source_url | https://digitalcommons.usu.edu/all_datasets/48/ | https://digitalcommons.usu.edu/all_datasets/48/ |
| version | 2018 | https://digitalcommons.usu.edu/all_datasets/48/ |
| doi | 10.15142/T3TD19 | https://digitalcommons.usu.edu/all_datasets/48/ |
| citation | Maguire, Dorafshan, Thomas (2018), SDNET2018: A concrete crack image dataset for machine learning applications. Dataset DOI 10.15142/T3TD19. | https://digitalcommons.usu.edu/all_datasets/48/ |
| availability | Official page and download links listed; payload not tested or acquired | https://digitalcommons.usu.edu/all_datasets/48/ |
| approximate_size | Over 56,000 images; ZIP listed as 515,903 kB | https://digitalcommons.usu.edu/all_datasets/48/ |
| modalities | ["RGB"] | https://digitalcommons.usu.edu/all_datasets/48/ |
| annotation_type | Image-level cracked/non-cracked folder labels; no bounding boxes supplied by this classification dataset | https://digitalcommons.usu.edu/all_datasets/48/ |
| classes_or_content | Concrete bridge decks (D), walls (W), pavements (P); cracked and non-cracked patches | https://digitalcommons.usu.edu/all_datasets/48/ |
| license_identifier | CC-BY-4.0 | https://digitalcommons.usu.edu/all_datasets/48/ |
| commercial_restriction | No non-commercial restriction in the identified grant; other rights may apply | https://digitalcommons.usu.edu/all_datasets/48/ |
| redistribution_notes | CC BY 4.0 attribution, license link and modification notice; no NC condition in this grant. | https://digitalcommons.usu.edu/all_datasets/48/ |

Code terms (separate): UNKNOWN; no code-license grant assumed

Paper terms (separate): Data in Brief article: CC BY 4.0, verified separately at authors institutional article record

## AEGISINSPECT ROLE / DECISION

OPTIONAL; timing NOT_REQUIRED; M1 acquisition required: no.

Role: Auxiliary crack classification and robustness analysis. Owner: Defect Detection / crack robustness experiments.

Patch classification is not detector ground truth; retain source-image grouping to avoid patch leakage. No need for first detector.

Before acquisition: pin release/subset, preserve the actual terms and checksums, validate payload/annotations and provenance, and implement task-specific leakage grouping. A source listing alone is not proof every payload is retrievable. HOLD entries require explicit clearance first.

Evidence reviewed:

- https://digitalcommons.usu.edu/all_datasets/48/
- https://www.sciencedirect.com/science/article/pii/S2352340918314082
- https://commons.und.edu/cie-fac/14/
- docs/data/M1_DATASET_ACQUISITION_PLAN.md
- docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md
