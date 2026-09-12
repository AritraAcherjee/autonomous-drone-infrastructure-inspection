# M1 Data Foundation scope decision

Decision date: 2026-09-11. Recommended boundary: M1 may close once this sweep's integrity and data-test checks pass. No further dataset acquisition is needed before Chat 03. This conclusion applies to the non-commercial research/capstone scope; it does not certify commercial rights for the complete future system.

## Evidence required to leave M1

| Requirement | Evidence and assessment |
|---|---|
| Immediate detector data acquired, licensed and approved | User-approved GYU-DET V3 baseline-v1; 8,305 train / 1,040 valid / 1,053 test; 10,398 supervised images and 48,392 annotations. Existing V3 source/license/provenance records are retained, not re-audited. |
| Validation, EDA, leakage-safe split and handoff | Existing `GYU_DET_M1_HANDOFF.md`, GYU M1 evidence index, manifests and provenance. This sweep verifies preservation rather than reopening their decisions. |
| Authoritative dataset registry and scoped permissions | 16 entries in `DATASET_REGISTRY.md` and JSON/CSV; field-level URLs in `source_evidence.csv`; unresolved licenses explicitly restrict later use. Not all sources are certified usable. |
| External generalization benchmark identified and protected | CODEBRIM original record/custom terms and `CODEBRIM_EXTERNAL_HOLDOUT_POLICY.md`; excluded from all baseline training/tuning. Payload acquisition and annotation adaptation belong to external evaluation after model freeze. |
| Future work bounded and owned | `M1_DATASET_ACQUISITION_PLAN.md`: no unacquired dataset is an immediate detector prerequisite; all later/optional/held data have owners and acquisition gates. |
| Approved evidence remains intact and checks pass | `outputs/validation/dataset_registry/integrity_check.json`, `preservation_snapshot.json`, `test_results.json` and `data_tests.log`. Closure is contingent on their successful final results, not this document's existence. |

The approved installed-reader/MPO smoke test remains intentionally deferred to Chat 03. It is a pre-training gate there, not an unfinished M1 acquisition. This sweep does not install the detector framework, train or waive that gate.

## Why later acquisition is defensible

The first model estimates structural defects from RGB images and boxes. Stereo/IMU trajectories, RGB-D sequences, tracking objects, thermal traffic scenes and simulation sensor streams do not supply missing supervision for that model. Downloading them now would add storage and validation work without satisfying an immediate dependency. Their release, sensor and evaluation-subset choices are better fixed by the owning workstream. GYU-DET baseline completion is already approved and is not conditional on those downloads.

CODEBRIM acquisition can also wait: independent evaluation requires a documented source, usable research terms and isolation policy now, but no inspection or model-driven tuning of its payload before the initial model is fixed. Later acquisition must still verify content, overlap and taxonomy compatibility before reporting external results.

## Deferred work and explicit future blockers

- Chat 03 external evaluation: acquire/validate CODEBRIM after model freeze, record terms acceptance, establish crosswalk and leakage checks. Optional SDNET2018 classification/robustness experiment only if needed.
- Chat 06 Defect Segmentation: DeepCrack (explicitly Liu et al., 537-image benchmark); preserve NC restrictions and examine mixed original-image provenance before redistribution or broader use.
- Chat 05 Low-Light Vision: clear LOL-v2 dataset license; ExDark is an optional non-commercial research extension under its dataset-specific terms (not its software BSD license).
- Video/Tracking: VisDrone2019 held pending clarification that current MIT project labeling applies to the selected dataset release. It is not structural-defect ground truth.
- Visual-Inertial SLAM/Localization: acquire selected EuRoC sequences under institutional NC rights; Hilti 2026 for 360 VIO/floor-plan localization, not LiDAR input.
- Depth/RGB-D SLAM: acquire selected TUM RGB-D sequences, preserving acquisition-time license and sequence exceptions.
- Chat 10 LiDAR SLAM + Mapping / Chat 11 Sensor Fusion: select Hilti 2022/2023 sequences under their individually verified NC-SA terms; handle sparse ground truth and platform differences.
- Autonomous Navigation/Obstacle Detection: TU Delft ODA v1, with sensor adaptation and missing-obstacle-coordinate handling; no claim it proves field navigation safety.
- Thermal/Multimodal extension: FLIR remains optional in purpose but HOLD in acquisition policy until actual dataset terms are obtained.
- Auxiliary structural detection: 2D Structural Damage remains HOLD for explicit license and upstream provenance; repository identity is a best-name match, not a proven historical project reference.
- Simulation/Integration/System Testing: internally generated Gazebo data are REQUIRED_LATER. Before generation intended for distribution, maintain an asset-license manifest for every world/model/mesh/texture/plugin/import. Record origin URL, author, version/commit, checksum, license/terms URL, attribution, modifications, dependencies and redistribution assessment. Until cleared, no blanket generated-data license or redistribution claim is allowed. Record scenario seeds, simulator configuration, sensors, coordinate frames and ground truth when generating later.

Unresolved future-dataset rights do not block M1 closure because those datasets are excluded from immediate use. They remain real blockers to their own acquisition/use, not automatically waived by closing M1. If scope changes to require one before Chat 03, reopen that prerequisite decision and clear it first.

There are no additional immediate acquisition blockers under this boundary. A failed preservation or test check would block closure until resolved. The final verification report records the actual result.
