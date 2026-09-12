# Full validation execution checks

- All 41 existing and new data tests passed; 0 failed.
- Final real-data command: bundled Python, scripts/data/validate_gyu_det.py --workers 8.
- The CLI completed and returned status 1 because 565 auxiliary-frame integrity errors were found. This is the documented data-issue exit status, not an incomplete run.
- All 11,123 primary images decode; all image bytes were SHA-256 hashed.
- All 10,432 labels were validated, including the 21 orphan labels.
- The 11,123 manifest rows reconcile with image, label, pairing and resolution outputs.
- Existing audit and human-triage input hashes are unchanged; raw extracted paths, sizes and modification times are unchanged.
- All 21 human decisions remain intact; no repairs or negative classifications were applied.
- PyArrow was not installed, so Parquet was not generated and no dependency was installed.
- Human intervention remains necessary to decide how to handle invalid MPO auxiliary frames, rounding-scale box overshoots, unresolved pairings, and negative-image identity. No automatic handling policy is accepted here.
- M1 remains incomplete.
