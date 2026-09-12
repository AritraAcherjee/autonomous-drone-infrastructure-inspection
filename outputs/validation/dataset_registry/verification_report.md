# Dataset registry verification report

Verified 2026-09-11. **M1 Data Foundation can close for the documented pre-Chat03, non-commercial research scope. No additional dataset must be downloaded before Chat 03.** This is based on preserved approved GYU evidence, passing checks, identified CODEBRIM research terms and isolation, and explicit later-workstream gates; it is not a blanket certification of all future dataset rights.

## Validation

- 112 tests passed, 0 failed, 0 errors, 0 skipped (98 existing tests plus 14 registry tests).
- The one existing pending-only registry assertion was updated to require actual evidence and current decisions. All its approved GYU assertions remain; no test was skipped or weakened to conceal a failure.
- All 113 protected existing evidence files match their pre-edit SHA-256 hashes; the approved GYU registry subsection is byte-for-byte unchanged.
- All 21,559 raw file paths, byte lengths and modification times match the pre-edit inventory. No raw writes were performed. This is a metadata inventory guard, not a fresh full-byte hash audit of the large raw archives.
- No large dataset downloaded, no raw split changed, no processed dataset created, no model trained, no ML framework installed. Existing pinned EDA test dependencies were installed only in an isolated task-workspace directory.
- GYU remains train 8,305 / valid 1,040 / test 1,053; 10,398 supervised images and 48,392 annotations. Existing installed-reader/MPO smoke test stays a Chat 03 pre-training gate.

## Decisions

| Dataset | Verification status | Decision | Timing | Dataset license / terms | Intended role |
|---|---|---|---|---|---|
| GYU-DET | APPROVED_UNCHANGED | USE_NOW | NOW | CC-BY-NC-SA-4.0 | Approved first structural-defect detector baseline |
| CODEBRIM | SOURCE_AND_TERMS_VERIFIED | DEFER_TO_WORKSTREAM | LATER | LicenseRef-CODEBRIM-NC | Protected external/domain-shift evaluation after detector baseline freeze |
| SDNET2018 | SOURCE_AND_TERMS_VERIFIED | OPTIONAL | NOT_REQUIRED | CC-BY-4.0 | Auxiliary crack classification and robustness analysis |
| DeepCrack | SOURCE_AND_TERMS_VERIFIED | DEFER_TO_WORKSTREAM | LATER | LicenseRef-DeepCrack-NC | Crack segmentation benchmark |
| 2D Structural Damage Dataset | SOURCE_IDENTIFIED_PROJECT_IDENTITY_AND_LICENSE_UNRESOLVED | HOLD | DO_NOT_ACQUIRE_YET | LICENSE_UNRESOLVED | Potential auxiliary detection/generalization only after provenance clearance |
| LOL-v2 | SOURCE_VERIFIED_LICENSE_UNRESOLVED | HOLD | DO_NOT_ACQUIRE_YET | LICENSE_UNRESOLVED | Paired enhancement evaluation after rights clarification |
| ExDark | SOURCE_AND_TERMS_VERIFIED | OPTIONAL | NOT_REQUIRED | LicenseRef-ExDark-NC | Optional low-light object-detection domain shift experiments |
| VisDrone | SOURCE_VERIFIED_LICENSE_SCOPE_UNRESOLVED | HOLD | DO_NOT_ACQUIRE_YET | LICENSE_UNRESOLVED | Video/tracking methodology; optional aerial detection robustness |
| EuRoC MAV | SOURCE_AND_TERMS_VERIFIED | DEFER_TO_WORKSTREAM | LATER | InC-NC | VIO / localization benchmark |
| TUM RGB-D | SOURCE_AND_TERMS_VERIFIED | DEFER_TO_WORKSTREAM | LATER | CC-BY-4.0 | Depth / RGB-D SLAM validation |
| Hilti SLAM 2022 | SOURCE_AND_TERMS_VERIFIED | DEFER_TO_WORKSTREAM | LATER | CC-BY-NC-SA-3.0 | Construction SLAM and sensor-fusion evaluation |
| Hilti SLAM 2023 | SOURCE_AND_TERMS_VERIFIED | DEFER_TO_WORKSTREAM | LATER | CC-BY-NC-SA-3.0 | Construction SLAM and sensor-fusion evaluation |
| Hilti x Trimble SLAM 2026 | SOURCE_AND_TERMS_VERIFIED | DEFER_TO_WORKSTREAM | LATER | CC-BY-NC-SA-3.0 | Construction VIO and floor-plan localization; not LiDAR-input benchmarking |
| TU Delft ODA | SOURCE_AND_TERMS_VERIFIED | DEFER_TO_WORKSTREAM | LATER | CC0-1.0 | Obstacle detection/avoidance and aerial perception validation |
| FLIR ADAS | SOURCE_VERIFIED_LICENSE_UNRESOLVED | HOLD | DO_NOT_ACQUIRE_YET | LICENSE_UNRESOLVED | Optional thermal/multimodal object-perception extension only |
| AegisInspect Gazebo-generated dataset | INTERNAL_PLANNED_ASSET_LICENSE_UNRESOLVED | DEFER_TO_WORKSTREAM | LATER | LICENSE_UNRESOLVED | REQUIRED_LATER for integrated system verification |

- **USE_NOW: 1** — GYU-DET.
- **DEFER_TO_WORKSTREAM: 9** — CODEBRIM, DeepCrack, EuRoC MAV, TUM RGB-D, Hilti SLAM 2022, Hilti SLAM 2023, Hilti x Trimble SLAM 2026, TU Delft ODA, AegisInspect Gazebo-generated dataset.
- **OPTIONAL: 2** — SDNET2018, ExDark.
- **HOLD: 4** — 2D Structural Damage Dataset, LOL-v2, VisDrone, FLIR ADAS.
- **REJECT: 0** — none.

USE_NOW applies only to the already acquired GYU-DET baseline. No new acquisition is authorized by this sweep.

## Source and licensing findings

- CODEBRIM: original Zenodo 1.0 record and its custom license verified. Research/education only; commercial gain and dataset redistribution restricted. Selected as protected external evaluation data, never baseline training/tuning. Full-resolution boxes and multi-label crops require a predeclared class crosswalk; no six-class equivalence assumed.
- SDNET2018: institutional dataset metadata explicitly CC BY 4.0. Classification patches are optional robustness data, not detector box ground truth.
- DeepCrack: this registry selects Liu et al. Neurocomputing 2019 / 537-image dataset. The distinct Zou et al. TIP benchmark is documented, not conflated. Dataset NC terms are separate from DeepSegmentor software terms. Mixed image ownership limits broader reuse/redistribution.
- ExDark: the dataset subfolder README explicitly permits only non-commercial research. It resolves the root README's ambiguous project-level BSD label; BSD is not substituted for dataset terms. Optional low-light object detection, not defect annotations.
- 2D structural damage: Xin Peng's matching repository combines SDNET, PEER Hub and self-collected images. No explicit dataset grant found. Project-history identity is inferred from the name, not confirmed by an older project URL. HOLD pending both provenance and license clearance.
- LOL-v2: author links identify the TIP 2021 extension with real/synthetic paired data. No explicit dataset grant recovered. SGM's linked paper endpoint returned a different Band Representation-Based paper, so exact subset counts remain UNKNOWN rather than copied from secondary sources. HOLD for license; do not conflate the extra unpaired collections or LOL-v1.
- VisDrone: original 2019 source/scale/tasks verified. A newer search-indexed project page labels a VisDrone entry MIT, but the current page body was not retrievable and the original 2019 repository lacks an explicit dataset grant. Record the MIT lead without claiming it licenses the selected 2019 payload. HOLD for release-specific scope clarification, not a claim that the dataset has no possible license.
- EuRoC: official files have moved to ETH Research Collection. Institutional rights state In Copyright - Non-Commercial Use Permitted, not an unrestricted CC license. Future VIO owner must preserve the institutional terms and clarify redistribution beyond the grant.
- TUM RGB-D: current site explicitly states dataset CC BY 4.0, software BSD-2-Clause. Historical workshop text says dataset CC BY 3.0; preserve acquisition-time and sequence-specific terms. Paper copyright is not used as a data license.
- Hilti 2022, 2023 and 2026: each release's own homepage independently states CC BY-NC-SA 3.0. 2026 supplies 360 camera/IMU/floor-plan data; its reference LiDAR stream is not in the distributed ROS2 bags. It belongs to VIO/localization rather than LiDAR-input benchmarking.
- TU Delft ODA: exact institutional DOI v1 and CC0 verified from the live 4TU HTML and deposited DataCite metadata; 1,369 trials and approximately 98.19 GB archive. Missing obstacle coordinates for samples 593-629 need handling later.
- FLIR: current supplier page exposes specifications and a sign-in/registration form, not a verified public dataset license. Access/terms were not accepted. HOLD for actual dataset agreement; optional thermal role does not imply unrestricted use.
- Gazebo: internal planned dataset, REQUIRED_LATER for system verification. Its redistribution license is intentionally unresolved until upstream asset licenses are inventoried. This does not mean Gazebo itself lacks a software license; software licensing cannot settle rights in all imported content.

## M1 boundary and future blockers

No immediate detector acquisition blocker remains. Closing M1 does not close future acquisition gates. Four external datasets remain HOLD: 2D structural damage, LOL-v2, VisDrone, FLIR. Gazebo generated-data rights remain unresolved pending the asset manifest. DeepCrack mixed-image provenance and EuRoC/ExDark redistribution scope require care if later use exceeds the recorded research permission.

Deferred owners: Chat 03 external evaluation (CODEBRIM; optional SDNET experiments); Chat 06 segmentation (DeepCrack); VIO/localization (EuRoC and Hilti 2026); RGB-D/depth (TUM); Chat 10 mapping and Chat 11 fusion (Hilti 2022/2023); navigation/obstacle detection (ODA); simulation/integration/system tests (Gazebo). Chat 05 owns held LOL-v2 and optional ExDark. Video/Tracking owns held VisDrone. Thermal extension owns held FLIR. Auxiliary detection owns held 2D damage. No future owner may use a HOLD dataset without clearing its documented blocker.

## Evidence and reproducibility

The authoritative registry is `docs/data/DATASET_REGISTRY.md`; JSON/CSV are synchronized representations. Each fact has field-level URL references in `source_evidence.csv` and JSON `field_sources`. Project roles/decisions are explicitly distinguished from published claims. License records separate dataset, software and paper terms. UNKNOWN means not established, not zero or permission.

Availability here means the authoritative metadata/page or listing was reached, including indexed page evidence where disclosed. It does not assert every archive link works, requires no account, or contains validated payloads. Bulk reachability/checksums and release pinning must be recorded by the later acquisition task. No mirror was used as licensing authority. Author-linked Drive/Baidu/Hugging Face destinations are access mechanisms, not independent license authorities.

Run offline checks from the repository with `python -m unittest discover -s tests/data -v`, using the existing pinned EDA dependencies. Evidence: `test_results.json`, `data_tests.log`, `preservation_snapshot.json`, `integrity_check.json`. The integrity fixture captures this sweep's initial approved state; do not silently refresh it after a future data change.

Required documents:

- `C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection\docs\data\DATASET_REGISTRY.md`
- `C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection\data\manifests\dataset_registry.json`
- `C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection\data\manifests\dataset_registry.csv`
- `C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection\docs\data\M1_DATASET_ACQUISITION_PLAN.md`
- `C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection\docs\data\M1_DATA_FOUNDATION_SCOPE_DECISION.md`
- `C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection\docs\data\CODEBRIM_EXTERNAL_HOLDOUT_POLICY.md`
- `C:\Users\Aritra\Documents\autonomous-drone-infrastructure-inspection\outputs\validation\dataset_registry\verification_report.md`
