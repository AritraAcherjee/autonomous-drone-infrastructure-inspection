# M1 preservation contract correction

Base: `606f04670c53a9b1833a3a5f5bf8121d7e3e9c2a`.

The original preservation test failed identically on Chat 02 and a clean base worktree. The first mismatch was `configs/data/gyu_det_v3_baseline.yaml`: expected `aeee0038389d953b5928ab0beed22e45eb12ecd1d65d730c87f62cfe5f1734f4`, actual `c58d363fd29e94e9cb16398babba9afbef51264c7ffc6acd2f9ccb440e4e2766`.

## Contract

For the 111 existing tracked artifacts, the snapshot represents canonical LF working-tree bytes, enforced by the existing `* text=auto eol=lf` attribute. Each file remains subject to direct SHA-256 comparison of its actual bytes. Tests do not normalize content, read HEAD in place of the working file, skip missing files, or accept multiple hashes. No test code changes are needed.

The machine-readable `preservation_contract_audit.json` classifies all 113 original entries. Tracked generated reports retained as approved evidence are category A, with a separate generated-output flag; they are not disposable outputs. The two formerly ignored logs are category B at audit time and are explicitly promoted to tracked historical evidence by this correction. There are no unexplained missing entries.

The 111 original tracked files are byte-identical between the current Chat 02 working tree, the pristine base working tree, and canonical base Git blobs. Twenty-two snapshot digests exactly match uniform CRLF representations; only these verified expectations are changed to their canonical LF digests. All other matching hashes remain unchanged.

## Independent execution_checks.md investigation

Path: `outputs/validation/gyu_det_v3/full_validation/execution_checks.md`.

- Snapshot: `e7d99e0ca2f6ff4ee0f446e883df16932281ff2e20a6c74117b1707a9622b0c1`.
- Canonical base/current: `4b784fb633872c945b2b82f616ed2775d770d22acefeef925c206bc4279f9774`.

Uniform CRLF does not explain this mismatch. Reconstructing the file with LF after its first twelve lines and CRLF after its final line produces the snapshot digest exactly. The textual/content difference is **none**; only the final line terminator differs. This reconstruction is verified cryptographically, not accepted merely because a plausible textual explanation exists.

Git history introduces both file and snapshot in `5ef5578ea42128473b61c91940292f54b5a77942` (`feat(data): complete M1 data foundation`), merged into base `606f046`. There is no earlier or subsequent version of this path in available history, and `git fsck --full --no-reflogs --unreachable` finds no unreachable history. The canonical approved version is the LF Git blob in that merged M1 commit: it contains exactly the text represented by the snapshot hash. There is no evidence of a post-snapshot semantic edit or conflicting approval decision. The likely capture-before-Git-normalization sequence is an inference; the precise byte equivalence is proven. Only its snapshot hash changes; the report itself does not.

## Historical logs: option A

The evidence index already identifies these as retained M1 execution evidence:

- `outputs/validation/gyu_det_v3/m1_evidence/baseline_v1_tests.log`
- `outputs/validation/gyu_det_v3/m1_evidence/documentation_tests.log`

Both local files match their existing snapshot digests exactly. They are now intentionally tracked, retaining their original bytes and hashes. Exact-path `-text` attributes prevent Git from changing their historical CRLF bytes. The general `*.log` ignore rule continues to apply to ordinary logs; these two files are explicitly added. Existing evidence/index references and all 113 protected entries are retained. No evidence is fabricated or regenerated.

The preservation assertion now has all dependencies in a clean checkout. The whole M1 suite still deliberately requires locally acquired raw data, as its separate acquisition and inventory assertions already specify. This correction does not pretend raw data is distributed with Git or weaken those assertions.

## Data boundary

No approved manifests, split memberships, source images, labels, class IDs, or data decisions are changed. The original raw inventory and GYU registry-section digest in the snapshot are unchanged. Approved counts remain train 8305, valid 1040, test 1053, total 10398, annotations 48392, six classes.

Chat 02's uncommitted detector work and pretraining FAIL evidence are untouched. This M1 correction requires integration and a subsequent Chat 02 gate rerun; it does not authorize training or set the gate to PASS.
