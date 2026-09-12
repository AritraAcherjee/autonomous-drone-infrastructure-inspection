Task: [L1][CHAT-02] Pre-training environment + reader gate

Branch: `chat02/pretraining-gate`

Base main SHA: `606f04670c53a9b1833a3a5f5bf8121d7e3e9c2a`

Commit SHA: **NONE**. The required M1 regression suite fails; the conditional
review/commit gate is not satisfied. Changes remain on the requested branch.

Tests:

```powershell
.venv-detection/Scripts/python.exe -m unittest discover -s tests/data -v
# 111 passed, 1 failed, 0 skipped (112 total)

.venv-detection/Scripts/python.exe -m unittest discover -s tests/detection -v
# Initial run: 31 passed, 0 failed, 0 skipped.
# A reporting regression was subsequently added; all 32 pass in the final suite below.

$env:PYTHONPATH=(Join-Path (Get-Location) 'src')+';'+(Join-Path (Get-Location) 'ros2_ws/src/aegisinspect_mapping')
.venv-detection/Scripts/python.exe -m pytest tests ros2_ws/src/aegisinspect_mapping/test ros2_ws/src/aegisinspect_system_tests/test -q --junitxml=outputs/validation/defect_detection/pretraining_gate/pytest_results.xml
# Final: 221 passed, 1 failed, 0 skipped; 26 warnings; 39 subtests passed.

.venv-detection/Scripts/python.exe -m pip check
# No broken requirements found.

.venv-detection/Scripts/python.exe -u scripts/verify_detection_pretraining.py
# Full measured runtime read and pre/post snapshot pass.
# Final report aggregation includes the failing M1 test evidence: FAIL.
```

Files changed:

- `.gitignore`: excludes the detector environment and disposable caches.
- `requirements/detection.txt`: pinned detector runtime.
- `src/detection/__init__.py`, `src/detection/data/__init__.py`.
- `src/detection/data/raw_guard.py`: canonical path guard, audited write protection, snapshots and comparison.
- `src/detection/data/readonly_verifier.py`: approved metadata consumer, installed-reader decode, existing M1 label parser.
- `src/detection/pretraining_gate.py`: environment, decode, MPO, label and immutability evidence; fail-closed test aggregation.
- `scripts/verify_detection_pretraining.py`: no-training entry point.
- `tests/detection/test_pretraining_gate.py`: 32 test methods.
- `outputs/validation/defect_detection/pretraining_gate/`: required reports/CSVs/JSON, raw inventories, installed-source hashes, package inventory, test logs/XML and pre-existing mismatch evidence.

Runtime validation:

| Check | Measured result |
|---|---|
| Environment | 3.11.15; torch 2.14.0+cu130; torchvision 0.29.0+cu130; Ultralytics 8.4.145; CUDA 13.0 available; cuDNN integer version 92400 |
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU; 8188 MiB; compute capability 8.9; driver 591.94 |
| Approved split counts | 8305 / 1040 / 1053 — PASS |
| Full image decode | 10398 / 10398; failures 0; unique resolutions 92 |
| Reader | Installed Ultralytics BaseDataset `imread` -> `ultralytics.utils.patches.imread` -> OpenCV 5.0.0, IMREAD_COLOR/BGR |
| MPO population | 565 source warning images; 543 included (482 train / 18 valid / 43 test) |
| MPO read | 543 tested, 543 successes, 0 failures |
| Label associations | 10398; 0 failures |
| Annotation rows | 48392; 1803 retained M1 warnings |
| Classes | 0 Crack; 1 Breakage; 2 Honeycombing; 3 Hole; 4 Exposed Reinforcement; 5 Seepage — unchanged |
| Raw files inventoried | 21559 |
| Baseline images + labels hashed | 20796 |
| Files added / removed | 0 / 0 |
| Size / mtime / content changes | 0 / 0 / 0 |
| New raw .cache / .npy | 0 / 0 |
| JPEG repairs / label rewrites | 0 / 0; inspected read-only code and unchanged hashes/mtimes |

Next step: resolve the pre-existing M1 preservation-snapshot discrepancy with
the M1 owner, without weakening the preservation test or rebuilding the dataset,
then rerun the required tests and review the combined gate before training approval.

Blockers: **PRETRAINING GATE = FAIL** because
`DatasetRegistryTests.test_gyu_approved_entry_and_artifacts_unchanged` fails.
The test stops first at `configs/data/gyu_det_v3_baseline.yaml` (the legacy
configuration, not the canonical baseline-v1 YAML). Expected SHA-256:
`aeee0038389d953b5928ab0beed22e45eb12ecd1d65d730c87f62cfe5f1734f4`;
actual and committed-base SHA-256:
`c58d363fd29e94e9cb16398babba9afbef51264c7ffc6acd2f9ccb440e4e2766`.

Read-only follow-up identified 23 protected artifact hash
discrepancies, all matching the committed base bytes. For 22, the retained hash
matches a CRLF representation of the committed LF text. The remaining mismatch,
`outputs/validation/gyu_det_v3/full_validation/execution_checks.md`, is not
explained by that simple conversion. Exact details are in
`preexisting_m1_discrepancies.json`. No protected file, snapshot or M1 test was
changed. The separate canonical baseline-v1 retained-hash and association checks
passed before the image reader ran.

The 26 warnings are existing Pillow `Image.getdata()` deprecations in
`src/data/validators/gyu_leakage.py`, not detector decode failures. No tests were
deleted, skipped or weakened. ROS/Gazebo build/runtime execution is outside this
detector gate; their Python contract and geometry tests were included.

The reader observed 92 distinct dimensions, compared with 82 stored M1
dimensions within this exact baseline population (the prior EDA's 85 describes
a different population). There are 648 axis-swapped image shapes: 351 have EXIF
orientation 6 and 297 have orientation 8. Every difference is a width/height
swap. This records actual backend behavior, not a source-image rewrite.
`reader_geometry_differences.csv` identifies every affected association.
This gate validates label paths and numeric annotation rows; it does not certify
spatial box alignment after the decoder's orientation handling. Preserve this
observation for review when integrating the actual training loader.

All 1,803 label warnings are the existing `derived_box_outside_frame` rounding
warnings allowed by the <=1e-6 M1 policy. They were retained without clipping.

Cache and scope: image caching is False; no label cache is created. The gate's
metadata consumer avoids stock YOLODataset initialization, JPEG repair and raw
`.npy` handling. Mutable settings are kept under the guarded repository cache.
Python audit checks are defense in depth; arbitrary native-code writes are not
claimed to be sandboxed. The inspected native decoder is read-only and its raw
effects were checked by inventories and hashes. No dataset was copied, repaired,
rebuilt or downloaded. No CODEBRIM benchmark was opened. No model was constructed,
trained, benchmarked or downloaded.

The baseline training plan was **not created**, because Phase 13 requires an
overall PASS. Actual trainer/augmentation/worker integration is not validated
by this reader-only gate; a future authorized trainer must preserve the raw
write/cache policy instead of using stock YOLODataset against raw paths.

Completion items:

1. Python version: 3.11.15 in `.venv-detection`.
2. PyTorch version: 2.14.0+cu130; torchvision 0.29.0+cu130.
3. CUDA availability: True; torch runtime 13.0; small CUDA tensor operation passed.
4. GPU: NVIDIA GeForce RTX 4070 Laptop GPU, 8188 MiB, compute capability 8.9.
5. Ultralytics version: 8.4.145.
6. Train count: 8305 — PASS.
7. Validation count: 1040 — PASS.
8. Test count: 1053 — PASS.
9. Total decoded images: 10398 / 10398.
10. Decode failures: 0.
11. MPO subset tested: 543 of 543 included; source population 565.
12. MPO failures: 0.
13. Label association failures: 0 of 10398; 48392 annotation rows.
14. Class-mapping result: PASS, exact six-class mapping and unchanged raw IDs.
15. Raw-data immutability result: PASS, no additions/removals/stat/hash changes or new raw caches.
16. Cache strategy: image cache False; no label cache; guarded settings/cache outside raw.
17. Tests passed / failed: detector 32 / 0; M1 111 / 1; final full Python suite 221 / 1; skipped 0.
18. PRETRAINING GATE = FAIL.
19. Blockers before actual model training: resolve the preservation-test failure, obtain a PASS and separate training/weight-download approval, and preserve read-only loader behavior in the eventual trainer.
20. Recommended first baseline model/config: retain the user-proposed YOLO26s / 640 target for future review; no plan approved or created, no weights downloaded, and no batch size selected or training executed.

Final Git status (no commit, no merge):

```text
M .gitignore
?? outputs/validation/defect_detection/pretraining_gate/PRETRAINING_GATE_REPORT.md
?? outputs/validation/defect_detection/pretraining_gate/dataset_loader_report.md
?? outputs/validation/defect_detection/pretraining_gate/dependency_versions.json
?? outputs/validation/defect_detection/pretraining_gate/environment_report.md
?? outputs/validation/defect_detection/pretraining_gate/full_tests.txt
?? outputs/validation/defect_detection/pretraining_gate/installed_packages.txt
?? outputs/validation/defect_detection/pretraining_gate/label_loader_results.csv
?? outputs/validation/defect_detection/pretraining_gate/m1_tests.txt
?? outputs/validation/defect_detection/pretraining_gate/mpo_reader_results.csv
?? outputs/validation/defect_detection/pretraining_gate/preexisting_m1_discrepancies.json
?? outputs/validation/defect_detection/pretraining_gate/pretraining_gate.json
?? outputs/validation/defect_detection/pretraining_gate/pytest_results.xml
?? outputs/validation/defect_detection/pretraining_gate/raw_immutability_check.json
?? outputs/validation/defect_detection/pretraining_gate/raw_snapshot_after.json
?? outputs/validation/defect_detection/pretraining_gate/raw_snapshot_before.json
?? outputs/validation/defect_detection/pretraining_gate/reader_decode_results.csv
?? outputs/validation/defect_detection/pretraining_gate/reader_geometry_differences.csv
?? outputs/validation/defect_detection/pretraining_gate/reader_geometry_notes.json
?? outputs/validation/defect_detection/pretraining_gate/test_results.json
?? outputs/validation/defect_detection/pretraining_gate/ultralytics_source_audit.json
?? requirements/detection.txt
?? scripts/verify_detection_pretraining.py
?? src/detection/__init__.py
?? src/detection/data/__init__.py
?? src/detection/data/raw_guard.py
?? src/detection/data/readonly_verifier.py
?? src/detection/pretraining_gate.py
?? tests/detection/test_pretraining_gate.py
```
