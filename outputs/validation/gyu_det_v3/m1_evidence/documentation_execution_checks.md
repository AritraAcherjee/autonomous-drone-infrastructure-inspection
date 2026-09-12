# GYU-DET M1 documentation execution checks

- Final test suite: **98 passed, 0 failed**; 89 existing tests plus nine new documentation tests.
- Read-only consistency check: PASS. Approved counts 8305 / 1040 / 1053; 10,398 images; 48,392 annotations.
- Source and three split manifest SHA-256 values match approved VERSION.json; every approved artifact hash in manifest_metadata.json also matches.
- All 10,398 image/label paths resolve; exclusions and SHA/scene-group assertions pass.
- All 76 indexed evidence paths exist.
- The supplied acquisition MD5 values match the official Version 3 file listing. classes.txt was rehashed locally; large archives were not rehashed again.
- Official V3 dataset license is CC BY-NC-SA 4.0; default V4 is CC BY 4.0. The article independently uses CC BY-NC-ND 4.0. Version selection resolves the apparent default-page discrepancy.
- During final read-only verification, 21559 raw paths/sizes/modification times were unchanged. All preceding documentation work also used raw inputs read-only.
- Approved artifacts were neither rebuilt nor altered. No raw files were copied, modified or linked.
- Raw files are untracked by Git; /data/raw/ is now explicitly ignored to prevent accidental redistribution.
- Prior finalization evidence was retained: 89 tests passed and two clean output trees were byte-identical. No split construction was rerun.
- Ultralytics is absent and was not installed; no weights downloaded, no training or installed reader smoke test performed.
- No GYU-DET M1 data-foundation blocker remains. Detector environment/reader, MPO decoding, raw-safe caches, count/class checks and no-training loader smoke test belong to Defect Detection.
- This closes only the GYU-DET evidence package. Overall multi-dataset M1 remains incomplete.
