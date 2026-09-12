# Baseline-v1 execution verification

- 89 data tests passed, zero failures: 79 existing plus 10 new.
- Final supervised images: train 8,305; valid 1,040; test 1,053; total 10,398.
- Final annotation instances: 48,392.
- Excluded raw images: 712 UNCLASSIFIED, 10 approved conflict exclusions, 2 equivalent duplicate exclusions, 1 conservative scene exclusion; total 725.
- Orphan labels excluded separately: 21. No labels transferred or repaired.
- Every included image resolves to the exact manifest label through the intended YOLO sibling-label convention (10,398 assertions).
- No SHA-identical content, high-confidence group or conservative unresolved group crosses splits. No approved conflict member, orphan or unlabeled image is included.
- Ultralytics smoke test skipped: package not installed, and not installed for this task. No model weights downloaded.
- Two clean temporary metadata-only trees were generated; all manifests, lists, YAML, statistics, documentation and metadata matched byte for byte.
- Output hashes match manifest_metadata.json and VERSION.json.
- All 21559 raw file paths, sizes and modification times unchanged. All 114 prior validation/triage/leakage/EDA artifact hashes unchanged.
- The processed baseline-v1 directory contains exactly three text image lists and no image/label copies or links.
- No model training occurred. M1 remains incomplete.

The ten conflict exclusions are human-approved for baseline-v1 only; previous evidence is preserved. No split-policy blocker remains. Before training, the eventual installed reader still needs a smoke/decode check (especially MPO primary images) and raw-safe cache/verification handling. The documentation records the absolute-YAML invocation and portable list-local path convention.
