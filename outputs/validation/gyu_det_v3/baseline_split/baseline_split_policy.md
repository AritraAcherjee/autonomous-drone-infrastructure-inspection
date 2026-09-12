# GYU-DET V3 dry-run baseline split proposal

**DRY RUN ONLY. No sample files or processed dataset are created. M1 remains incomplete.**

## Eligibility versus proposed inclusion

baseline_eligible means valid exact-pair eligibility BEFORE duplicate and leakage handling. proposed_included is the final dry-run decision. An eligible image can therefore have an exclusion_reason. Unlabeled images remain UNCLASSIFIED, never negative. Orphan labels are excluded independently in excluded_orphan_labels.csv; they are not extra raw-image rows. No label transfer or orphan repair is permitted. Readable MPO primary images and <=1e-6 boundary-rounding warnings remain eligible. This does not certify compatibility with the eventual training reader.

## Exact duplicate consistency and representative policy

All exact SHA-256 groups from the existing audit are reconciled with the complete manifest. Label hashes are verified against full validation. Fields are validated with the existing YOLO parser, then compared as exact decimal values. Whitespace, decimal spelling and row order do not cause false conflicts; rows form a multiset, so repeated rows retain multiplicity. No coordinate tolerance, rounding or clipping is applied. IDENTICAL_ANNOTATIONS means the normalized rows match in order; REORDERED_EQUIVALENT_ANNOTATIONS means they match only after sorting. Availability, row counts, class multiplicities, box values and normalized content fingerprints are reported separately.

A conflicting group is blocked: all its eligible members are held out of the proposal, with no automatic representative. This is a reversible manifest exclusion pending human review, not a judgment that any member is invalid. For equivalent or one-labeled-copy groups, retain an eligible representative, prioritizing test, then valid, then train. The valid/test tie rule protects test isolation and is a proposal policy, not a new human leakage outcome. Within a split use lexicographic casefolded raw relative path, with the original path as a tie-breaker. This is string order, not numeric filename order. Redundant copies are excluded to avoid evaluation inflation or training overweighting.

Equivalent groups: 2; conflicting groups: 5.

| Group | Consistency | Proposed representative | Human review required |
|---|---|---|---|
| EXACT_1 | CONFLICTING_ANNOTATIONS | none | True |
| EXACT_2 | IDENTICAL_ANNOTATIONS | data/raw/gyu_det/v3/extracted/train/train/images/10245.jpg | False |
| EXACT_3 | CONFLICTING_ANNOTATIONS | none | True |
| EXACT_4 | CONFLICTING_ANNOTATIONS | none | True |
| EXACT_5 | IDENTICAL_ANNOTATIONS | data/raw/gyu_det/v3/extracted/valid/valid/images/11989.jpg | False |
| EXACT_6 | CONFLICTING_ANNOTATIONS | none | True |
| EXACT_7 | CONFLICTING_ANNOTATIONS | none | True |

## Leakage handling

All retained members preserve their raw split. No global random resplit is used. Exact duplicate edges and approved high-confidence or conservative unresolved edges form connected components, including paths through currently ineligible members. If eligible retained members span splits, choose test, then valid, then train and exclude members from the other splits. This keeps evaluation-side samples and sacrifices redundant/conflicting-split training coverage. No files are moved. Rejected perceptual candidates impose no grouping constraint. Original human outcomes are preserved; unresolved is not confirmed leakage.

- data/raw/gyu_det/v3/extracted/train/train/images/9838.jpg ↔ data/raw/gyu_det/v3/extracted/valid/valid/images/11989.jpg: CONFIRMED_EXACT_CROSS_SPLIT_LEAKAGE. Pre-handling eligible: True/True; proposed splits: excluded / valid. Exclusion reasons: EQUIVALENT_EXACT_DUPLICATE_REDUNDANT / none.
- data/raw/gyu_det/v3/extracted/train/train/images/11727.jpg ↔ data/raw/gyu_det/v3/extracted/valid/valid/images/11985.jpg: HIGH_CONFIDENCE_NEAR_DUPLICATE_LEAKAGE. Pre-handling eligible: True/False; proposed splits: train / excluded. Exclusion reasons: none / UNLABELED_UNCLASSIFIED.
- data/raw/gyu_det/v3/extracted/train/train/images/11334.jpg ↔ data/raw/gyu_det/v3/extracted/test/test/images/12582.jpg: UNRESOLVED_POSSIBLE_SAME_SCENE. Pre-handling eligible: True/True; proposed splits: excluded / test. Exclusion reasons: APPROVED_LEAKAGE_GROUP_OTHER_SPLIT_RETAINED / none.

## Dry-run counts and exclusions

Pre-handling eligible exact pairs: 10,411. Proposed counts: {"test": 1053, "train": 8305, "valid": 1040}.

Exclusion totals (raw images only):

- ANNOTATION_CONFLICT_HUMAN_REVIEW_REQUIRED: 10.
- APPROVED_LEAKAGE_GROUP_OTHER_SPLIT_RETAINED: 1.
- EQUIVALENT_EXACT_DUPLICATE_REDUNDANT: 2.
- UNLABELED_UNCLASSIFIED: 712.

Raw-official comparisons in split_statistics.csv and related tables use exact-pair supervision as the class/box denominator; raw_official_images also exposes all image counts. exclusion_summary.csv gives exact counts excluded from each original split and why. Source dimensions and all per-box measurements are reused from validated metadata and EDA. No images are decoded. The exact dataset identities and pending negative status prevent interpreting the supplied 691 negative total as identified negatives.

## Raw and presentation class names

| ID | Raw source | Proposed AegisInspect display name |
|---:|---|---|
| 0 | Crack | Crack |
| 1 | Breakage | Breakage |
| 2 | Comb | Honeycombing |
| 3 | Hole | Hole |
| 4 | Reinforcement | Exposed Reinforcement |
| 5 | Seepage | Seepage |

IDs remain unchanged. No classes are merged and no labels are rewritten.

## Assertions, reproducibility and approval boundary

Run `python scripts/data/propose_gyu_baseline_split.py` from the repository. No random seed is needed: all choices and serialization orders are deterministic. Input/source SHA-256 values are recorded in proposal_summary.json. Image byte hashes are reused from validation; existing raw images are checked for existence but not rehashed. All exact-pair label bytes are hash-checked read-only. The routine fails if a leakage or inclusion assertion fails. Annotation-conflict groups are reported as blockers even when the held-out proposal passes leakage assertions.

The YAML references reserved FUTURE list files under data/processed/gyu_det_v3_baseline. These files are not created or claimed to exist. The config is a proposal, not approval to train. Human review of blocked groups and explicit approval of any later materialization are still required. Official raw split membership, every prior human decision, and data/raw remain unchanged. No files are copied, linked, moved, renamed, deleted or repaired.
