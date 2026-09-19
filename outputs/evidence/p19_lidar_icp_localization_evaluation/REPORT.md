# P19 LIDAR ICP LOCALIZATION EVALUATION — COMPLETE

## A. INPUT / PROVENANCE

Only the accepted 07 LiDAR ICP moving-run canonical and GT exports were evaluated.
Source branch: `07/lidar-icp-fallback`. Source runtime HEAD: `8ff6f6ed842333565ada94b87327dfcd1a1923c2`.

| Input | Data rows | SHA-256 |
|---|---:|---|
| Evidence ZIP | — | `e9f4545c11c415675a53f0bf46da3b33d5477ad5dba939dfe63075e993e980bf` |
| canonical.csv | 427 | `0198293d29ad5746ebb889431333d9de9374afb456fb0bcc0198bb8415dbdbc3` |
| gt.csv | 5,670 | `7e44a9558d62c8cedb2fa272fe47709f5dbf18d7e30c74ad7ff12cba631f62e2` |

ZIP CRC verified; all 237 ZIP members match the extracted package with no extra files.
All 236 source-manifest entries and 21 preserved source/configuration hashes verified.
Both CSVs remain byte-identical; byte-identical evidence copies are in `inputs/`.
No stationary-gate, RTAB RGB-D, OpenVINS, or previous-experiment trajectories were scored.
Associated metadata, report and source/configuration hashes were ingested as provenance only.

Repository: `C:\Dev\aegisinspect-p19-lidar-eval`. Branch: `p19/lidar-icp-localization-eval`.
P19 HEAD: `013067277d331246959af1f6176584b5305828f4`.
Frozen evaluation core `src/evaluation/trajectory.py` SHA-256: `3a0484cad0065f404025ac9d7e48d8ed18cea32960ed6823321a4502bb5411bd`.
Evaluation code/configuration bundle SHA-256: `9733fc6b7f31fcc3a00dddf98b56acb0e64bcdb20b087ee2aed5f50861799aa2`.
The bundle is SHA-256 of the canonical JSON mapping in `provenance.json` (`code_file_sha256`).
Exact source snapshots and the additions-only patch are preserved.

Execution UTC: **2026-09-19T03:10:59.834981+00:00**.
Environment: Windows 11 build 26200; Anaconda Python 3.13.9; NumPy 2.3.5 (MKL 2025),
SciPy 1.16.3, Matplotlib 3.10.6 (Agg), Pillow 12.0.0; pytest 8.4.2.
Evaluation used CPU float64. Full Python executable/build and BLAS/LAPACK details are in `environment.json`.

Exact issued evaluation command (PowerShell, repository working directory):

```powershell
python -B scripts/evaluation/evaluate_lidar_icp_accepted.py --config configs/evaluation/p19_lidar_icp_accepted.json
```

Resolved interpreter/arguments:

```text
C:\Users\Aritra\anaconda3\python.exe -B C:\Dev\aegisinspect-p19-lidar-eval\scripts\evaluation\evaluate_lidar_icp_accepted.py --config C:\Dev\aegisinspect-p19-lidar-eval\configs\evaluation\p19_lidar_icp_accepted.json
```

| Timing / interval | Value |
|---|---|
| START invocation UTC | 2026-09-19T01:50:21.154478+00:00 |
| Recorded START origin | **35,763,000,000 ns = 35.763 s simulation time** |
| Response observed clock | 35.805 s (42 ms after invocation reference) |
| Primary selection | **[38,763,000,000, 53,763,000,000] ns**, inclusive |
| Relative interval | **[3, 18] s** from recorded START origin |
| Selected estimator timestamps | 38.8–53.7 s; relative 3.037–17.937 s |
| Selected estimator span | 14.9 s |
| Canonical candidates / GT in interval | 76 / 1,500 |
| Canonical excluded before / after interval | 339 / 12 |

**Timing limitation:** the accepted package explicitly records the latest observed `/clock`
at START invocation. The plugin adopts its epoch on a later simulation update and that exact
epoch was not instrumented. Thus the selection above is exact against the preserved reference;
it is not asserted to be exact against an unknown plugin epoch. The 42 ms clock difference is
an observed difference, not a proven error bound. No temporal fitting or GT-derived correction
was performed. The first CSV timestamp (4.6 s) was not used as the origin.

## B. MATCHING

| Statistic | Value |
|---|---:|
| Candidate canonical samples | 76 |
| Matched | 76 |
| Unmatched | 0 |
| Coverage | 100% |
| Exact GT timestamp matches | 76 |
| Between-sample interpolations needed | 0 |
| Distinct GT samples used | 76 |
| GT samples available inside primary interval | 1,500 |
| GT adjacent-sample gap in primary interval | 10 ms |
| Maximum accepted temporal separation | 0 ms (all exact) |
| Maximum accepted nonzero interpolation bracket | Not applicable; none required |
| Maximum primary canonical timestamp gap | 400 ms |

Unmatched reasons: none. The unchanged frozen P19 rule accepts exact timestamps directly;
otherwise it requires a containing GT bracket no wider than 50 ms, linear translation,
and shortest-path quaternion SLERP. No nearest-neighbor substitution or extrapolation occurred.
Plot labels referring to interpolated GT include these exact values of the GT interpolant.
GT PoseStamped exports omit child-frame text; the adapter assigns `base_link` from the frozen
producer's explicit `worldPose(linkEntity_)` / `message.set_name("base_link")` and the P19 contract.
No pose values or source rows were changed.

## C. ALIGNMENT

**SE(3) no-scale Umeyama**, fit once to the 76 matched primary samples.
**Scale fixed at 1.0; scale was not estimated.**
Convention: `p_world_aligned = R @ p_odom + t`; the same R acts on pose orientation.

```text
R =
[0.983782004709675, 0.062335684226241, 0.168188078297660]
[-0.176832311619423, 0.179943190615873, 0.967652200802702]
[0.030054962597631, -0.981699908639614, 0.188047835936043]

t (m) = [0.029472395633596438, 0.2071506730330161, 1.0817462405773695]
```

`det(R) = 1.000000000000001`; maximum orthogonality residual
`1.11e-15`. An independent rigid-fit calculation agrees,
and consecutive trajectory distances are preserved. This transform exists only in the
evaluation evidence. It was not applied to canonical.csv, runtime ICP, TF, or operational localization.

## D. ATE TRANSLATION

Matched count **76**, unmatched count **0**. Headline **RMSE 0.595396782192 m**.

| Statistic | Value |
|---|---:|
| Count | 76  |
| RMSE | 0.595396782192 m |
| Mean | 0.481032528925 m |
| Median | 0.422610002620 m |
| P95 (linear percentile) | 1.432588156280 m |
| Maximum | 1.790711049682 m |

## E. RPE TRANSLATION

Delta: **1.0 s ± 50 ms**. For each matched start, select the future matched sample nearest
`t + 1 s`, breaking ties toward the earlier timestamp; reject a mismatch above 50 ms.
Only primary-window endpoints are eligible. All **44** accepted pairs have delta **exactly 1.0 s**.
Of 76 possible starts, 31 have no future endpoint within tolerance and the final sample has
no future sample. Rejection records are in `independent_validation.json`.

| Statistic | Value |
|---|---:|
| Count | 44  |
| RMSE | 0.340604743330 m |
| Mean | 0.295421080613 m |
| Median | 0.269450513069 m |
| P95 (linear percentile) | 0.593363150783 m |
| Maximum | 0.697756193683 m |

## F. RPE ROTATION

Delta: **1.0 s ± 50 ms**; same **44** pairs. Shortest-angle rotation error.
Summary units: **degrees**. Pair CSV also preserves radians.

| Statistic | Value |
|---|---:|
| Count | 44  |
| RMSE | 1.707265244063 degrees |
| Mean | 1.109437940072 degrees |
| Median | 0.511219104797 degrees |
| P95 (linear percentile) | 4.375270769288 degrees |
| Maximum | 4.712332013603 degrees |

## G. TRAJECTORY DIAGNOSTICS

- Raw post-START ICP net displacement: **2.255362245090 m**
  (118 samples, 35.8–56.4 s).
- Raw post-START GT net displacement: **0.450000021465 m**
  (2,104 samples, 35.77–56.8 s).
- These reproduce the source's approximately 2.255362245 m and 0.450000021 m context.
  Their direct difference is **not ATE**; these raw diagnostics also have their own coverage.
- After the required rigid alignment, estimated world z spans **0.936472–3.258139 m**
  versus GT **1.500000–1.679933 m** at matched timestamps. Equal-scale projections
  preserve the visible trajectory-shape discrepancy.
- Translation error begins at **0.467676 m**, varies during the motion and rises
  toward the end, reaching the maximum **1.790711 m** at relative **17.937 s**.
- The absolute orientation diagnostic after the same position-fitted rigid alignment spans
  **74.824222–82.798258°**, with RMSE **79.734133°**.
  This includes the fixed rotation chosen by the position fit; it is distinct from the
  **1.707265°** one-second relative rotation RMSE. No orientation-specific
  alignment was substituted and neither result is hidden.

Required deterministic plots are supplied as PNG and SVG. All three PNGs were visually inspected.
The images are generated solely from saved CSVs; all 608 plotted coordinate pairs were verified
against those files. Re-rendering the saved data reproduced all six image files byte-for-byte.
Spatial projections use equal physical scale within each panel; error axes are linear and start at zero.

## H. INTERPRETATION

**07 runtime acceptance: PASS**

**P19 localization accuracy: QUANTIFIED — NO ACCEPTANCE THRESHOLD AUTHORIZED**

Supported by 07: the frozen LiDAR ICP backend demonstrated sustained operational local odometry
through meaningful deterministic P13 motion while preserving the Aegis canonical odometry and TF contracts.
Localization accuracy was not established by 07. P19 now provides the quantitative evidence above.
There is no authorized accuracy acceptance threshold and no accuracy PASS/FAIL verdict is assigned.

The repository's historical `real_project_metrics_authorized: false` flag belongs to its tooling-only
freeze. The current explicit 00 user authorization permits this one accepted-run evaluation; the
frozen protocol file and every scientific rule remain unchanged.

## I. ARTIFACTS

All paths below are relative to this evidence directory.

| Artifact | Path |
|---|---|
| Report | [REPORT.md](REPORT.md) |
| Summary | [metrics_summary.json](metrics_summary.json), [CSV](metrics_summary.csv) |
| Original P19 result | [frozen_p19_result.json](frozen_p19_result.json) |
| Per-sample ATE / absolute rotation | [per_sample_ate.csv](per_sample_ate.csv) |
| Pair-level RPE translation | [rpe_translation.csv](rpe_translation.csv) |
| Pair-level RPE rotation | [rpe_rotation.csv](rpe_rotation.csv) |
| Aligned trajectory / GT / original poses | [aligned_trajectory.csv](aligned_trajectory.csv) |
| Trajectory plot | [PNG](plots/aligned_trajectory_vs_gt.png), [SVG](plots/aligned_trajectory_vs_gt.svg) |
| Translation error plot | [PNG](plots/translation_error_over_time.png), [SVG](plots/translation_error_over_time.svg) |
| Absolute rotation error plot | [PNG](plots/rotation_error_over_time.png), [SVG](plots/rotation_error_over_time.svg) |
| Provenance and configuration | [provenance.json](provenance.json), [evaluation_configuration.json](evaluation_configuration.json) |
| Window derivation | [timestamp_window.json](timestamp_window.json), [table](interval_provenance.csv) |
| Matching | [matching_statistics.json](matching_statistics.json), [per sample](matching_samples.csv), [table](matching_summary.csv) |
| Alignment transform | [alignment_transform.json](alignment_transform.json) |
| Input validation | [input_integrity.json](input_integrity.json), [schema_validation.json](schema_validation.json), [final integrity](final_input_integrity.json) |
| Input copies | [canonical.csv](inputs/canonical.csv), [gt.csv](inputs/gt.csv) |
| Independent numerical audit | [independent_validation.json](independent_validation.json) |
| Plot audit | [plot_validation.json](plot_validation.json), [plot_series.csv](plot_series.csv) |
| Commands / environment | [command_transcript.json](command_transcript.json), [environment.json](environment.json) |
| Git state | [initial](git_state_initial.json), [final](git_state_final.json) |
| Narrow implementation additions | [implementation_additions.patch](implementation_additions.patch), `code_snapshot/` |
| Accepted source context | `source_context/` (includes report, metadata, timing, source hashes and original manifest) |
| Complete evidence manifest | [SHA256SUMS.txt](SHA256SUMS.txt), [verification receipt](manifest_verification.json) |

Validation: **132 existing P19 tests passed**. Independent saved-output recomputation reconciles
counts, GT association, ATE, temporal RPE pairing, translation/rotation RPE and all summaries.
Maximum independent ATE difference: **0.0 m**; maximum RPE rotation difference:
**6.39e-12°** (floating-point computation).
No numerical or provenance inconsistency was found. Input hashes were rechecked after evaluation.

Manifest verification: **VERIFIED**. Every evidence artifact, including nested source-manifest
copies and code snapshots, is hashed; only the root `SHA256SUMS.txt` excludes itself.
The sealing command re-reads and verifies the final manifest before returning success.

Worktree began clean. Existing tracked files remain unchanged. Three narrowly scoped files were
added: the offline runner, independent verifier, and accepted-run configuration; the evidence tree
contains the outputs and this packaging script. Exact additions are recorded in the patch.
No commit or push occurred. No new MSI/localization run, tuning, runtime publication or second
localization experiment occurred. The source attempt remains consumed at exactly one START.

**STOP AND RETURN TO 00.**
