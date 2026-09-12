# GYU-DET M1 evidence index

Scope: GYU-DET V3 baseline-v1 data foundation only. The installed detector-reader smoke test is deliberately deferred to Chat 03 / Defect Detection; this does not close the overall multi-dataset M1 milestone. All paths below are repository-relative, verified to exist, and describe retained evidence rather than regenerated splits. Prior baseline finalization: 89 tests passed; two clean runs were byte-identical. **Final current suite: 98 tests passed, 0 failed** (89 existing + nine documentation tests); log: `outputs/validation/gyu_det_v3/m1_evidence/documentation_tests.log`.

The V3-specific dataset license is CC BY-NC-SA 4.0. The DOI defaults to V4, whose license metadata differs; select V3 in History. Acquisition hashes were verified previously and matched to the V3 page; large archives were not rehashed in this pass. Raw archives remain external and immutable. Historical dry-run blockers were resolved for baseline-v1 by human-approved exclusion, not by modifying their original evidence.

## A Acquisition

| Artifact | Repository-relative path | Purpose | Status | Key result |
|---|---|---|---|---|
| archives | `data/raw/gyu_det/v3/archives` | External immutable source files | PRESENT / PATH VERIFIED | Four source files; no redistribution |
| classes.txt | `data/raw/gyu_det/v3/archives/classes.txt` | Acquired source file | PRESENT / PATH VERIFIED | Verified acquisition MD5 F078630BF0D0614B07C9DC990DA40801; official V3 listing matches |
| test.zip | `data/raw/gyu_det/v3/archives/test.zip` | Acquired source file | PRESENT / PATH VERIFIED | Verified acquisition MD5 522A80C18CAA4A0030D7FFC9DDFA98B2; official V3 listing matches |
| train.zip | `data/raw/gyu_det/v3/archives/train.zip` | Acquired source file | PRESENT / PATH VERIFIED | Verified acquisition MD5 A8AAD1CC02E86C4857B8315EE9F1606E; official V3 listing matches |
| valid.zip | `data/raw/gyu_det/v3/archives/valid.zip` | Acquired source file | PRESENT / PATH VERIFIED | Verified acquisition MD5 D8EBE9C38D9D4D05DD9CFFB50A692086; official V3 listing matches |

## B Pairing

| Artifact | Repository-relative path | Purpose | Status | Key result |
|---|---|---|---|---|
| pairing_report.md | `outputs/validation/gyu_det_v3/pairing_report.md` | Exact-basename pairing audit | PRESENT / PATH VERIFIED | 10411 exact pairs; 712 unclassified; 21 orphan labels |
| pairing_summary.csv | `outputs/validation/gyu_det_v3/pairing_summary.csv` | Exact-basename pairing audit | PRESENT / PATH VERIFIED | 10411 exact pairs; 712 unclassified; 21 orphan labels |
| unmatched_images.csv | `outputs/validation/gyu_det_v3/unmatched_images.csv` | Exact-basename pairing audit | PRESENT / PATH VERIFIED | 10411 exact pairs; 712 unclassified; 21 orphan labels |
| unmatched_labels.csv | `outputs/validation/gyu_det_v3/unmatched_labels.csv` | Exact-basename pairing audit | PRESENT / PATH VERIFIED | 10411 exact pairs; 712 unclassified; 21 orphan labels |
| matched_pairs.csv | `outputs/validation/gyu_det_v3/matched_pairs.csv` | Exact-basename pairing audit | PRESENT / PATH VERIFIED | 10411 exact pairs; 712 unclassified; 21 orphan labels |

## C Orphan review

| Artifact | Repository-relative path | Purpose | Status | Key result |
|---|---|---|---|---|
| orphan_review | `outputs/validation/gyu_det_v3/orphan_review` | Visual/human review evidence | PRESENT / PATH VERIFIED | 21 triaged; zero confirmed mappings; no repairs |
| final_triage_summary.csv | `outputs/validation/gyu_det_v3/orphan_review/final_triage_summary.csv` | Visual/human review evidence | PRESENT / PATH VERIFIED | 21 triaged; zero confirmed mappings; no repairs |
| human_triage_decisions.csv | `outputs/validation/gyu_det_v3/orphan_review/human_triage_decisions.csv` | Visual/human review evidence | PRESENT / PATH VERIFIED | 21 triaged; zero confirmed mappings; no repairs |

## D Validation

| Artifact | Repository-relative path | Purpose | Status | Key result |
|---|---|---|---|---|
| validation_report.md | `outputs/validation/gyu_det_v3/full_validation/validation_report.md` | Full validated raw inventory | PRESENT / PATH VERIFIED | All primary frames readable; auxiliary MPO and boundary warnings retained |
| image_validation.csv | `outputs/validation/gyu_det_v3/full_validation/image_validation.csv` | Full validated raw inventory | PRESENT / PATH VERIFIED | All primary frames readable; auxiliary MPO and boundary warnings retained |
| label_validation.csv | `outputs/validation/gyu_det_v3/full_validation/label_validation.csv` | Full validated raw inventory | PRESENT / PATH VERIFIED | All primary frames readable; auxiliary MPO and boundary warnings retained |
| annotation_issues.csv | `outputs/validation/gyu_det_v3/full_validation/annotation_issues.csv` | Full validated raw inventory | PRESENT / PATH VERIFIED | All primary frames readable; auxiliary MPO and boundary warnings retained |
| class_statistics.csv | `outputs/validation/gyu_det_v3/full_validation/class_statistics.csv` | Full validated raw inventory | PRESENT / PATH VERIFIED | All primary frames readable; auxiliary MPO and boundary warnings retained |
| gyu_det_v3_raw_manifest.csv | `data/manifests/gyu_det_v3_raw_manifest.csv` | Raw inventory and SHA-256 provenance | PRESENT / PATH VERIFIED | d78f554660bd5fe6452842051f0a1fec0bbd299b61c52139da1c8208f1c0c772 |

## E Leakage

| Artifact | Repository-relative path | Purpose | Status | Key result |
|---|---|---|---|---|
| exact_duplicate_groups.csv | `outputs/validation/gyu_det_v3/leakage_audit/exact_duplicate_groups.csv` | Exact/perceptual audit and human decisions | PRESENT / PATH VERIFIED | 1 exact; 1 high-confidence; 1 conservative unresolved; 14 rejected cross-split candidates |
| cross_split_exact_duplicates.csv | `outputs/validation/gyu_det_v3/leakage_audit/cross_split_exact_duplicates.csv` | Exact/perceptual audit and human decisions | PRESENT / PATH VERIFIED | 1 exact; 1 high-confidence; 1 conservative unresolved; 14 rejected cross-split candidates |
| cross_split_near_duplicates.csv | `outputs/validation/gyu_det_v3/leakage_audit/cross_split_near_duplicates.csv` | Exact/perceptual audit and human decisions | PRESENT / PATH VERIFIED | 1 exact; 1 high-confidence; 1 conservative unresolved; 14 rejected cross-split candidates |
| leakage_report.md | `outputs/validation/gyu_det_v3/leakage_audit/leakage_report.md` | Exact/perceptual audit and human decisions | PRESENT / PATH VERIFIED | 1 exact; 1 high-confidence; 1 conservative unresolved; 14 rejected cross-split candidates |
| human_leakage_decisions.csv | `outputs/validation/gyu_det_v3/leakage_review/human_leakage_decisions.csv` | Exact/perceptual audit and human decisions | PRESENT / PATH VERIFIED | 1 exact; 1 high-confidence; 1 conservative unresolved; 14 rejected cross-split candidates |
| final_leakage_review.md | `outputs/validation/gyu_det_v3/leakage_review/final_leakage_review.md` | Exact/perceptual audit and human decisions | PRESENT / PATH VERIFIED | 1 exact; 1 high-confidence; 1 conservative unresolved; 14 rejected cross-split candidates |

## F EDA

| Artifact | Repository-relative path | Purpose | Status | Key result |
|---|---|---|---|---|
| eda_report.md | `outputs/eda/gyu_det_v3/eda_report.md` | Prior exact-pair EDA interpretation | PRESENT / PATH VERIFIED | 48447 prior supervised instances; 84 orphan instances separate |
| figures | `outputs/eda/gyu_det_v3/figures` | EDA figures | PRESENT / PATH VERIFIED | Nine figures; no new rendering required |
| annotation_count_distribution.csv | `outputs/eda/gyu_det_v3/annotation_count_distribution.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| annotation_count_examples.csv | `outputs/eda/gyu_det_v3/annotation_count_examples.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| aspect_ratio_distribution.csv | `outputs/eda/gyu_det_v3/aspect_ratio_distribution.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| box_examples.csv | `outputs/eda/gyu_det_v3/box_examples.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| box_measurements.csv | `outputs/eda/gyu_det_v3/box_measurements.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| box_size_distribution.csv | `outputs/eda/gyu_det_v3/box_size_distribution.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| box_statistics.csv | `outputs/eda/gyu_det_v3/box_statistics.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| box_statistics_by_class.csv | `outputs/eda/gyu_det_v3/box_statistics_by_class.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| box_statistics_by_split.csv | `outputs/eda/gyu_det_v3/box_statistics_by_split.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| class_combination_statistics.csv | `outputs/eda/gyu_det_v3/class_combination_statistics.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| class_cooccurrence.csv | `outputs/eda/gyu_det_v3/class_cooccurrence.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| class_cooccurrence_normalized.csv | `outputs/eda/gyu_det_v3/class_cooccurrence_normalized.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| class_distribution.csv | `outputs/eda/gyu_det_v3/class_distribution.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| class_distribution_by_split.csv | `outputs/eda/gyu_det_v3/class_distribution_by_split.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| dataset_overview.csv | `outputs/eda/gyu_det_v3/dataset_overview.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| image_statistics.csv | `outputs/eda/gyu_det_v3/image_statistics.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| output_inventory.csv | `outputs/eda/gyu_det_v3/output_inventory.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| resolution_distribution.csv | `outputs/eda/gyu_det_v3/resolution_distribution.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |
| split_comparison.csv | `outputs/eda/gyu_det_v3/split_comparison.csv` | EDA statistics/table | PRESENT / PATH VERIFIED | Prior EDA denominator 10411 exact pairs unless marked raw |

## G Splits

| Artifact | Repository-relative path | Purpose | Status | Key result |
|---|---|---|---|---|
| baseline_split_policy.md | `outputs/validation/gyu_det_v3/baseline_split/baseline_split_policy.md` | Historical dry-run policy | HISTORICAL EVIDENCE | Superseded in approval status by baseline-v1; retained unchanged |
| duplicate_annotation_consistency.csv | `outputs/validation/gyu_det_v3/baseline_split/duplicate_annotation_consistency.csv` | Conflict evidence | PRESENT / PATH VERIFIED | Five conflict groups; all ten members excluded by baseline-v1 human policy |
| class_statistics.csv | `data/manifests/gyu_det_v3_baseline_v1/class_statistics.csv` | Approved specification/provenance | APPROVED / HASH VERIFIED | 8305 / 1040 / 1053; 10398 images; 48392 annotations |
| excluded.csv | `data/manifests/gyu_det_v3_baseline_v1/excluded.csv` | Approved specification/provenance | APPROVED / HASH VERIFIED | 8305 / 1040 / 1053; 10398 images; 48392 annotations |
| excluded_orphan_labels.csv | `data/manifests/gyu_det_v3_baseline_v1/excluded_orphan_labels.csv` | Approved specification/provenance | APPROVED / HASH VERIFIED | 8305 / 1040 / 1053; 10398 images; 48392 annotations |
| manifest_metadata.json | `data/manifests/gyu_det_v3_baseline_v1/manifest_metadata.json` | Approved specification/provenance | APPROVED / HASH VERIFIED | 8305 / 1040 / 1053; 10398 images; 48392 annotations |
| split_statistics.csv | `data/manifests/gyu_det_v3_baseline_v1/split_statistics.csv` | Approved specification/provenance | APPROVED / HASH VERIFIED | 8305 / 1040 / 1053; 10398 images; 48392 annotations |
| test.csv | `data/manifests/gyu_det_v3_baseline_v1/test.csv` | Approved specification/provenance | APPROVED / HASH VERIFIED | 8305 / 1040 / 1053; 10398 images; 48392 annotations |
| train.csv | `data/manifests/gyu_det_v3_baseline_v1/train.csv` | Approved specification/provenance | APPROVED / HASH VERIFIED | 8305 / 1040 / 1053; 10398 images; 48392 annotations |
| valid.csv | `data/manifests/gyu_det_v3_baseline_v1/valid.csv` | Approved specification/provenance | APPROVED / HASH VERIFIED | 8305 / 1040 / 1053; 10398 images; 48392 annotations |
| VERSION.json | `data/manifests/gyu_det_v3_baseline_v1/VERSION.json` | Approved specification/provenance | APPROVED / HASH VERIFIED | 8305 / 1040 / 1053; 10398 images; 48392 annotations |
| train.txt | `data/processed/gyu_det_v3_baseline_v1/splits/train.txt` | Portable image-reference list | APPROVED / HASH VERIFIED | Raw references only; image/label paths verified |
| valid.txt | `data/processed/gyu_det_v3_baseline_v1/splits/valid.txt` | Portable image-reference list | APPROVED / HASH VERIFIED | Raw references only; image/label paths verified |
| test.txt | `data/processed/gyu_det_v3_baseline_v1/splits/test.txt` | Portable image-reference list | APPROVED / HASH VERIFIED | Raw references only; image/label paths verified |
| gyu_det_v3_baseline_v1.yaml | `configs/data/gyu_det_v3_baseline_v1.yaml` | Detector config interface | APPROVED / HASH VERIFIED | Absolute YAML input; six fixed IDs |

## H Documentation

| Artifact | Repository-relative path | Purpose | Status | Key result |
|---|---|---|---|---|
| gyu_det_v3.md | `docs/data/sources/gyu_det_v3.md` | Provenance/license/registry/handoff | PRESENT / PATH VERIFIED | GYU-DET data foundation only; reader gate deferred |
| gyu_det_v3_source_provenance.json | `data/manifests/gyu_det_v3_source_provenance.json` | Provenance/license/registry/handoff | PRESENT / PATH VERIFIED | GYU-DET data foundation only; reader gate deferred |
| gyu_det_v3.md | `docs/data/licenses/gyu_det_v3.md` | Provenance/license/registry/handoff | PRESENT / PATH VERIFIED | GYU-DET data foundation only; reader gate deferred |
| gyu_det_v3_baseline_v1.md | `docs/data/gyu_det_v3_baseline_v1.md` | Provenance/license/registry/handoff | PRESENT / PATH VERIFIED | GYU-DET data foundation only; reader gate deferred |
| DATASET_REGISTRY.md | `docs/data/DATASET_REGISTRY.md` | Provenance/license/registry/handoff | PRESENT / PATH VERIFIED | GYU-DET data foundation only; reader gate deferred |
| GYU_DET_M1_HANDOFF.md | `docs/data/GYU_DET_M1_HANDOFF.md` | Provenance/license/registry/handoff | PRESENT / PATH VERIFIED | GYU-DET data foundation only; reader gate deferred |

## I Tests and verification

| Artifact | Repository-relative path | Purpose | Status | Key result |
|---|---|---|---|---|
| baseline_v1_execution_checks.json | `outputs/validation/gyu_det_v3/m1_evidence/baseline_v1_execution_checks.json` | Execution or source-verification record | PRESENT / VERIFIED | Prior 89 tests; clean byte-identical finalization |
| baseline_v1_execution_checks.md | `outputs/validation/gyu_det_v3/m1_evidence/baseline_v1_execution_checks.md` | Execution or source-verification record | PRESENT / VERIFIED | Prior 89 tests; clean byte-identical finalization |
| baseline_v1_tests.log | `outputs/validation/gyu_det_v3/m1_evidence/baseline_v1_tests.log` | Execution or source-verification record | PRESENT / VERIFIED | Prior 89 tests; clean byte-identical finalization |
| consistency_check.json | `outputs/validation/gyu_det_v3/m1_evidence/consistency_check.json` | Execution or source-verification record | PRESENT / VERIFIED | Current source/documentation/consistency evidence |
| documentation_execution_checks.md | `outputs/validation/gyu_det_v3/m1_evidence/documentation_execution_checks.md` | Execution or source-verification record | PRESENT / VERIFIED | 98/0 tests; approved artifacts and raw files unchanged; read-only consistency PASS |
| documentation_tests.log | `outputs/validation/gyu_det_v3/m1_evidence/documentation_tests.log` | Execution or source-verification record | PASS | 98 tests passed; 0 failed (89 existing + 9 new) |
| source_verification.json | `outputs/validation/gyu_det_v3/m1_evidence/source_verification.json` | Execution or source-verification record | PRESENT / VERIFIED | Current source/documentation/consistency evidence |
| check_gyu_m1.py | `scripts/data/check_gyu_m1.py` | Read-only documentation/consistency regression checks | PRESENT / PATH VERIFIED | Run all data tests; never regenerate approved artifacts |
| test_gyu_m1_documentation.py | `tests/data/test_gyu_m1_documentation.py` | Read-only documentation/consistency regression checks | PRESENT / PATH VERIFIED | Run all data tests; never regenerate approved artifacts |
