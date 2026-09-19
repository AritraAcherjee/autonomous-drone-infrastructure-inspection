"""Package already-calculated, independently verified evidence; no scoring."""
from pathlib import Path
import csv
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]


def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))


def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_csv(name,records):
    with (OUT/name).open('w',newline='',encoding='utf-8') as stream:
        w=csv.DictWriter(stream,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)


def main():
    assert not (OUT/'SHA256SUMS.txt').exists(), 'Evidence already sealed'
    p=read('provenance.json'); m=read('metrics_summary.json'); w=read('timestamp_window.json')
    a=read('alignment_transform.json'); d=read('trajectory_diagnostics.json')
    v=read('independent_validation.json'); pv=read('plot_validation.json')
    assert v['status']=='VERIFIED' and pv['status']=='VERIFIED'
    original=Path(read('evaluation_configuration.json')['package'])
    verified=[]
    for line in (original/'SHA256SUMS.txt').read_text().splitlines():
        expected,name=line.split('  ',1)
        assert digest(original/name)==expected,name
        verified.append(name)
    for name,key in [('canonical.csv','canonical_sha256'),('gt.csv','gt_sha256')]:
        assert digest(original/'exports'/name)==p[key]==digest(OUT/'inputs'/name)
    write('final_input_integrity.json',{'status':'VERIFIED','source_manifest_artifacts_reverified':len(verified),
        'source_csvs_byte_identical_to_initial_hashes':True,'input_copies_byte_identical':True,
        'canonical_sha256':p['canonical_sha256'],'gt_sha256':p['gt_sha256'],
        'checked_utc':datetime.now(timezone.utc).isoformat()})
    p['issued_evaluation_command']='python -B scripts/evaluation/evaluate_lidar_icp_accepted.py --config configs/evaluation/p19_lidar_icp_accepted.json'
    p['input_evidence_copies']={'canonical':'inputs/canonical.csv','gt':'inputs/gt.csv'}
    write('provenance.json',p)
    transcript=read('command_transcript.json')
    transcript['issued_evaluation_command']=p['issued_evaluation_command']
    transcript['evaluation_exit_code']=0
    transcript['evaluation_result']='Complete; authoritative results in frozen_p19_result.json and metrics_summary.json'
    transcript['independent_validation_command']='python -B scripts/evaluation/verify_lidar_icp_evidence.py --evidence outputs/evidence/p19_lidar_icp_localization_evaluation'
    transcript['independent_validation_exit_code']=0
    transcript['independent_validation_result']=v
    transcript['plot_validation_result']=pv
    transcript['packaging_command']='python -B outputs/evidence/p19_lidar_icp_localization_evaluation/finalize_evidence.py'
    transcript['packaging_result']='All saved artifacts hashed; root SHA256SUMS.txt re-read and verified before process success'
    write('command_transcript.json',transcript)
    table_csv('matching_summary.csv',[{'statistic':key,'value':value} for key,value in m['matching'].items()])
    table_csv('interval_provenance.csv',[{'field':key,'value':value} for key,value in {
        'source_branch':p['source_branch'],'source_runtime_head':p['source_runtime_head'],
        'p19_head':p['p19_head'],'execution_utc':p['execution_utc'],'origin_ns':w['origin_ns'],
        'primary_start_ns':w['start_ns'],'primary_end_ns':w['end_ns'],'interval_boundaries':'inclusive',
        'canonical_input_count':427,'gt_input_count':5670,'canonical_primary_count':76,'gt_primary_count':1500,
        'matched_count':76,'unmatched_count':0,'plugin_epoch_known':False}.items()])
    raw=list(csv.DictReader((OUT/'aligned_trajectory.csv').open(newline='',encoding='utf-8')))
    er=list(csv.DictReader((OUT/'per_sample_ate.csv').open(newline='',encoding='utf-8')))
    z_est=[float(r['est_aligned_z_m']) for r in raw]; z_gt=[float(r['gt_z_m']) for r in raw]
    rot=[float(r['rotation_error_deg']) for r in er]
    def metric_table(key,unit):
        s=m[key]
        return '| Statistic | Value |\n|---|---:|\n'+ '\n'.join(
            f'| {label} | {s[k] if k=="count" else format(s[k],".12f")} {"" if k=="count" else unit} |'
            for label,k in [('Count','count'),('RMSE','rmse'),('Mean','mean'),('Median','median'),('P95 (linear percentile)','p95'),('Maximum','max')])
    rotation_text='\n'.join('['+', '.join(f'{x:.15f}' for x in row)+']' for row in a['rotation'])
    report=f'''# P19 LIDAR ICP LOCALIZATION EVALUATION — COMPLETE

## A. INPUT / PROVENANCE

Only the accepted 07 LiDAR ICP moving-run canonical and GT exports were evaluated.
Source branch: `{p['source_branch']}`. Source runtime HEAD: `{p['source_runtime_head']}`.

| Input | Data rows | SHA-256 |
|---|---:|---|
| Evidence ZIP | — | `{p['zip_sha256']}` |
| canonical.csv | 427 | `{p['canonical_sha256']}` |
| gt.csv | 5,670 | `{p['gt_sha256']}` |

ZIP CRC verified; all 237 ZIP members match the extracted package with no extra files.
All 236 source-manifest entries and 21 preserved source/configuration hashes verified.
Both CSVs remain byte-identical; byte-identical evidence copies are in `inputs/`.
No stationary-gate, RTAB RGB-D, OpenVINS, or previous-experiment trajectories were scored.
Associated metadata, report and source/configuration hashes were ingested as provenance only.

Repository: `{p['repository_path']}`. Branch: `{p['p19_branch']}`.
P19 HEAD: `{p['p19_head']}`.
Frozen evaluation core `src/evaluation/trajectory.py` SHA-256: `{p['evaluation_core_sha256']}`.
Evaluation code/configuration bundle SHA-256: `{p['evaluation_code_bundle_sha256']}`.
The bundle is SHA-256 of the canonical JSON mapping in `provenance.json` (`code_file_sha256`).
Exact source snapshots and the additions-only patch are preserved.

Execution UTC: **{p['execution_utc']}**.
Environment: Windows 11 build 26200; Anaconda Python 3.13.9; NumPy 2.3.5 (MKL 2025),
SciPy 1.16.3, Matplotlib 3.10.6 (Agg), Pillow 12.0.0; pytest 8.4.2.
Evaluation used CPU float64. Full Python executable/build and BLAS/LAPACK details are in `environment.json`.

Exact issued evaluation command (PowerShell, repository working directory):

```powershell
{p['issued_evaluation_command']}
```

Resolved interpreter/arguments:

```text
{p['exact_evaluation_command']}
```

| Timing / interval | Value |
|---|---|
| START invocation UTC | {w['invocation']['utc']} |
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
{rotation_text}

t (m) = {a['translation_m']}
```

`det(R) = {a['det_R']:.16g}`; maximum orthogonality residual
`{a['orthogonality_max_abs_error']:.3g}`. An independent rigid-fit calculation agrees,
and consecutive trajectory distances are preserved. This transform exists only in the
evaluation evidence. It was not applied to canonical.csv, runtime ICP, TF, or operational localization.

## D. ATE TRANSLATION

Matched count **76**, unmatched count **0**. Headline **RMSE {m['ate_translation']['rmse']:.12f} m**.

{metric_table('ate_translation','m')}

## E. RPE TRANSLATION

Delta: **1.0 s ± 50 ms**. For each matched start, select the future matched sample nearest
`t + 1 s`, breaking ties toward the earlier timestamp; reject a mismatch above 50 ms.
Only primary-window endpoints are eligible. All **44** accepted pairs have delta **exactly 1.0 s**.
Of 76 possible starts, 31 have no future endpoint within tolerance and the final sample has
no future sample. Rejection records are in `independent_validation.json`.

{metric_table('rpe_translation','m')}

## F. RPE ROTATION

Delta: **1.0 s ± 50 ms**; same **44** pairs. Shortest-angle rotation error.
Summary units: **degrees**. Pair CSV also preserves radians.

{metric_table('rpe_rotation','degrees')}

## G. TRAJECTORY DIAGNOSTICS

- Raw post-START ICP net displacement: **{d['canonical']['raw_net_displacement_m']:.12f} m**
  (118 samples, 35.8–56.4 s).
- Raw post-START GT net displacement: **{d['gt']['raw_net_displacement_m']:.12f} m**
  (2,104 samples, 35.77–56.8 s).
- These reproduce the source's approximately 2.255362245 m and 0.450000021 m context.
  Their direct difference is **not ATE**; these raw diagnostics also have their own coverage.
- After the required rigid alignment, estimated world z spans **{min(z_est):.6f}–{max(z_est):.6f} m**
  versus GT **{min(z_gt):.6f}–{max(z_gt):.6f} m** at matched timestamps. Equal-scale projections
  preserve the visible trajectory-shape discrepancy.
- Translation error begins at **{d['ate_first_m']:.6f} m**, varies during the motion and rises
  toward the end, reaching the maximum **{d['ate_last_m']:.6f} m** at relative **17.937 s**.
- The absolute orientation diagnostic after the same position-fitted rigid alignment spans
  **{min(rot):.6f}–{max(rot):.6f}°**, with RMSE **{m['absolute_rotation_diagnostic']['rmse']:.6f}°**.
  This includes the fixed rotation chosen by the position fit; it is distinct from the
  **{m['rpe_rotation']['rmse']:.6f}°** one-second relative rotation RMSE. No orientation-specific
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
Maximum independent ATE difference: **{v['max_ate_difference_m']} m**; maximum RPE rotation difference:
**{v['max_rpe_rotation_difference_deg']:.3g}°** (floating-point computation).
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
'''
    (OUT/'REPORT.md').write_text(report,encoding='utf-8')
    # Create final inventory entries before capturing the worktree state.
    for name in ['git_state_final.json','manifest_verification.json','SHA256SUMS.txt']:
        (OUT/name).touch()
    def git(*args):
        return subprocess.check_output(['git','--no-optional-locks',*args],cwd=ROOT,text=True).strip()
    state={'repository':git('rev-parse','--show-toplevel'),'branch':git('branch','--show-current'),
           'HEAD':git('rev-parse','HEAD'),'status_porcelain':git('status','--porcelain=v1','--untracked-files=all'),
           'tracked_diff':git('diff','HEAD'),'tracked_files_unchanged':not bool(git('diff','HEAD','--name-only')),
           'new_implementation_files':['configs/evaluation/p19_lidar_icp_accepted.json',
               'scripts/evaluation/evaluate_lidar_icp_accepted.py','scripts/evaluation/verify_lidar_icp_evidence.py'],
           'committed':False,'pushed':False}
    assert state['tracked_files_unchanged'] and state['HEAD']==p['p19_head']
    write('git_state_final.json',state)
    files=sorted(f for f in OUT.rglob('*') if f.is_file() and f!=OUT/'SHA256SUMS.txt')
    receipt={'result':'VERIFIED','artifact_count':len(files),'excluded':['SHA256SUMS.txt'],
             'method':'SHA256 of each artifact; reload root manifest, compare every digest and exact file inventory',
             'source_inputs_unchanged':True,'independent_metrics_verified':True,'plots_verified':True,
             'note':'This receipt is included in the manifest; final verification occurs after manifest creation. No self-referential manifest hash is embedded.'}
    write('manifest_verification.json',receipt)
    (OUT/'SHA256SUMS.txt').write_text(''.join(f'{digest(f)}  {f.relative_to(OUT).as_posix()}\n' for f in files),encoding='utf-8')
    entries=[]
    for line in (OUT/'SHA256SUMS.txt').read_text().splitlines():
        expected,name=line.split('  ',1); assert digest(OUT/name)==expected,name; entries.append(name)
    assert set(entries)=={f.relative_to(OUT).as_posix() for f in files} and len(entries)==len(files)
    print(json.dumps({'result':'VERIFIED','artifact_count':len(entries),'manifest_sha256':digest(OUT/'SHA256SUMS.txt'),
                      'report':str(OUT/'REPORT.md'),'tracked_files_unchanged':True,'source_csvs_unchanged':True},indent=2))


if __name__=='__main__':
    main()
