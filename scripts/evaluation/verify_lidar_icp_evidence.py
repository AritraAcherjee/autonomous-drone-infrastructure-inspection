"""Independent saved-evidence audit; deliberately does not import P19 metrics."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import math
import numpy as np
from scipy.spatial.transform import Rotation, Slerp


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    with path.open(newline='',encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def values(row,prefix,fields):
    return np.array([float(row[prefix+k]) for k in fields])


def pose(row,prefix):
    result=np.eye(4)
    result[:3,:3]=Rotation.from_quat(values(row,prefix,['qx','qy','qz','qw'])).as_matrix()
    result[:3,3]=values(row,prefix,['x_m','y_m','z_m'])
    return result


def check_summary(actual,summary):
    ordered=sorted(actual); n=len(actual); p=.95*(n-1); lo=math.floor(p); hi=math.ceil(p)
    expected={'count':n,'rmse':math.sqrt(math.fsum(x*x for x in actual)/n),
              'mean':statistics.fmean(actual),'median':statistics.median(actual),
              'p95':ordered[lo]+(p-lo)*(ordered[hi]-ordered[lo]),'max':max(actual)}
    for k,v in expected.items():
        assert math.isclose(v,summary[k],rel_tol=1e-12,abs_tol=1e-12),(k,v,summary[k])
    return expected


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--evidence',required=True)
    args=parser.parse_args(); out=Path(args.evidence).resolve()
    summary=load(out/'metrics_summary.json'); alignment=load(out/'alignment_transform.json')
    provenance=load(out/'provenance.json'); window=load(out/'timestamp_window.json')
    config=load(out/'evaluation_configuration.json'); package=Path(config['package'])
    trajectory=rows(out/'aligned_trajectory.csv'); ate=rows(out/'per_sample_ate.csv')
    translation=rows(out/'rpe_translation.csv'); rotation=rows(out/'rpe_rotation.csv')
    matching=rows(out/'matching_samples.csv')
    R=np.asarray(alignment['rotation']); t=np.asarray(alignment['translation_m'])
    assert alignment['scale']==1 and alignment['scale_estimated'] is False
    assert np.allclose(R.T@R,np.eye(3),atol=1e-12,rtol=0) and abs(np.linalg.det(R)-1)<1e-12
    canonical=rows(package/'exports/canonical.csv'); gt=rows(package/'exports/gt.csv')
    assert len(canonical)==427 and len(gt)==5670
    assert digest(package/'exports/canonical.csv')==provenance['canonical_sha256']
    assert digest(package/'exports/gt.csv')==provenance['gt_sha256']
    assert digest(Path(config['zip']))==provenance['zip_sha256']
    assert window['origin_ns']==load(package/'start_invocation.json')['simulation_stamp_ns']
    assert window['start_ns']==window['origin_ns']+3_000_000_000
    assert window['end_ns']==window['origin_ns']+18_000_000_000
    candidates=[r for r in canonical if window['start_ns']<=int(r['timestamp_ns'])<=window['end_ns']]
    assert len(candidates)==len(matching)==summary['matching']['estimator_sample_count']
    assert len(trajectory)==len(ate)==summary['matching']['aligned_sample_count']
    assert len(matching)-len(ate)==summary['matching']['dropped_sample_count']
    assert sum(window['start_ns']<=int(r['timestamp_ns'])<=window['end_ns'] for r in gt)==window['gt_primary_count']
    raw_by_time={int(r['timestamp_ns']):r for r in canonical}
    gt_ts=np.array([int(r['timestamp_ns']) for r in gt])
    max_translation_residual=0.; max_rotation_residual=0.
    for tr,er in zip(trajectory,ate):
        stamp=int(tr['timestamp_ns']); assert stamp==int(er['timestamp_ns'])
        assert window['start_ns']<=stamp<=window['end_ns']
        assert float(tr['relative_to_start_s'])==(stamp-window['origin_ns'])/1e9
        raw=raw_by_time[stamp]
        assert np.array_equal(values(tr,'est_raw_',['x_m','y_m','z_m']),values(raw,'',['px','py','pz']))
        assert np.array_equal(values(tr,'est_raw_',['qx','qy','qz','qw']),values(raw,'',['qx','qy','qz','qw']))
        j=int(np.searchsorted(gt_ts,stamp))
        if j<len(gt_ts) and gt_ts[j]==stamp:
            gp=values(gt[j],'',['px','py','pz']); gq=Rotation.from_quat(values(gt[j],'',['qx','qy','qz','qw']))
        else:
            assert 0<j<len(gt_ts) and gt_ts[j]-gt_ts[j-1]<=50_000_000
            f=(stamp-int(gt_ts[j-1]))/(int(gt_ts[j])-int(gt_ts[j-1]))
            gp=(1-f)*values(gt[j-1],'',['px','py','pz'])+f*values(gt[j],'',['px','py','pz'])
            gq=Slerp([0,1],Rotation.from_quat([values(gt[j-1],'',['qx','qy','qz','qw']),values(gt[j],'',['qx','qy','qz','qw'])]))(f)
        assert np.allclose(gp,values(tr,'gt_',['x_m','y_m','z_m']),atol=1e-12,rtol=0)
        assert (gq.inv()*Rotation.from_quat(values(tr,'gt_',['qx','qy','qz','qw']))).magnitude()<1e-10
        expected=R@values(tr,'est_raw_',['x_m','y_m','z_m'])+t
        assert np.allclose(expected,values(tr,'est_aligned_',['x_m','y_m','z_m']),atol=1e-12,rtol=0)
        expected_q=Rotation.from_matrix(R)*Rotation.from_quat(values(tr,'est_raw_',['qx','qy','qz','qw']))
        assert (expected_q.inv()*Rotation.from_quat(values(tr,'est_aligned_',['qx','qy','qz','qw']))).magnitude()<1e-10
        error=float(np.linalg.norm(expected-gp)); max_translation_residual=max(max_translation_residual,abs(error-float(er['translation_error_m'])))
        absolute_angle=float((gq.inv()*expected_q).magnitude()*180/np.pi)
        assert abs(absolute_angle-float(er['rotation_error_deg']))<1e-8
    assert max_translation_residual<1e-12
    # Independent optimality check using orthogonal Procrustes on saved positions.
    X=np.array([values(r,'est_raw_',['x_m','y_m','z_m']) for r in trajectory])
    Y=np.array([values(r,'gt_',['x_m','y_m','z_m']) for r in trajectory])
    u,s,vt=np.linalg.svd((X-X.mean(0)).T@(Y-Y.mean(0)))
    correction=np.diag([1,1,np.linalg.det(vt.T@u.T)])
    independent_R=vt.T@correction@u.T
    assert np.allclose(R,independent_R,atol=1e-12,rtol=0)
    assert np.allclose(t,Y.mean(0)-R@X.mean(0),atol=1e-12,rtol=0)
    # Rigid transforms preserve all consecutive distances; no trajectory scale fit.
    AX=np.array([values(r,'est_aligned_',['x_m','y_m','z_m']) for r in trajectory])
    assert np.allclose(np.linalg.norm(np.diff(X,axis=0),axis=1),np.linalg.norm(np.diff(AX,axis=0),axis=1),atol=1e-12,rtol=0)
    timestamps=[int(r['timestamp_ns']) for r in trajectory]
    expected_pairs=[]; rejected=[]
    for i,stamp in enumerate(timestamps):
        if i==len(timestamps)-1:
            rejected.append({'start_timestamp_ns':stamp,'reason':'no_future_sample'}); continue
        j=min(range(i+1,len(timestamps)),key=lambda j:(abs(timestamps[j]-(stamp+1_000_000_000)),timestamps[j]))
        if abs(timestamps[j]-stamp-1_000_000_000)>50_000_000:
            rejected.append({'start_timestamp_ns':stamp,'reason':'nearest_future_delta_outside_tolerance'}); continue
        expected_pairs.append((stamp,timestamps[j]))
    actual_pairs=[(int(r['start_timestamp_ns']),int(r['end_timestamp_ns'])) for r in translation]
    assert actual_pairs==expected_pairs
    assert actual_pairs==[(int(r['start_timestamp_ns']),int(r['end_timestamp_ns'])) for r in rotation]
    tr_by_stamp={int(r['timestamp_ns']):r for r in trajectory}
    for tr,rot in zip(translation,rotation):
        a=tr_by_stamp[int(tr['start_timestamp_ns'])]; b=tr_by_stamp[int(tr['end_timestamp_ns'])]
        est_delta=np.linalg.inv(pose(a,'est_aligned_'))@pose(b,'est_aligned_')
        gt_delta=np.linalg.inv(pose(a,'gt_'))@pose(b,'gt_')
        E=np.linalg.inv(gt_delta)@est_delta
        assert abs(np.linalg.norm(E[:3,3])-float(tr['translation_error_m']))<1e-12
        angle=float(Rotation.from_matrix(E[:3,:3]).magnitude()*180/np.pi)
        max_rotation_residual=max(max_rotation_residual,abs(angle-float(rot['rotation_error_deg'])))
        assert int(tr['actual_delta_ns'])==int(tr['end_timestamp_ns'])-int(tr['start_timestamp_ns'])
        assert abs(int(tr['actual_delta_ns'])-1_000_000_000)<=50_000_000
        assert abs(float(rot['rotation_error_rad'])-np.deg2rad(float(rot['rotation_error_deg'])))<1e-12
    assert max_rotation_residual<1e-6
    recalculated={k:check_summary([float(r[column]) for r in data],summary[k]) for k,data,column in [
        ('ate_translation',ate,'translation_error_m'),('rpe_translation',translation,'translation_error_m'),
        ('rpe_rotation',rotation,'rotation_error_deg'),('absolute_rotation_diagnostic',ate,'rotation_error_deg')]}
    series=rows(out/'plot_series.csv')
    tables={'aligned_trajectory.csv':trajectory,'per_sample_ate.csv':ate}
    for item in series:
        source=tables[item['source']][int(item['row'])]
        assert float(item['x'])==float(source[item['x_column']])
        assert float(item['y'])==float(source[item['y_column']])
    plot_provenance=load(out/'plot_provenance.json')
    for name,expected in plot_provenance['sources'].items(): assert digest(out/name)==expected
    for name,expected in provenance['code_file_sha256'].items():
        assert digest(Path(provenance['repository_path'])/name)==expected
        assert digest(out/'code_snapshot'/name)==expected
    for field in ['source_branch','source_runtime_head','zip_sha256','canonical_sha256','gt_sha256','input_rows',
                  'p19_head','evaluation_core_sha256','evaluation_code_bundle_sha256','exact_evaluation_command',
                  'environment','execution_utc','interval','matching','alignment','rpe_rule']:
        assert provenance.get(field) is not None,field
    result={'status':'VERIFIED','execution_utc':datetime.now(timezone.utc).isoformat(),
            'command':f'"{sys.executable}" -B scripts/evaluation/verify_lidar_icp_evidence.py --evidence "{out}"',
            'independent_of_frozen_evaluator':True,'checks':[
                'source input byte hashes and counts','metadata origin and inclusive interval',
                'candidate/matched/unmatched counts','saved GT exact matches / interpolation',
                'proper rigid transform and position/orientation application','independent no-scale optimum',
                'distance preservation','ATE recomputed from saved poses','RPE brute-force temporal pairing',
                'RPE recomputed with homogeneous transforms and SciPy rotation','summary metrics from saved errors',
                'plot series equal persisted CSV values','code snapshot hashes','required provenance'],
            'summary_recalculated':recalculated,'max_ate_difference_m':max_translation_residual,
            'max_rpe_rotation_difference_deg':max_rotation_residual,'plot_series_points_verified':len(series),
            'rpe_matched_start_count':len(expected_pairs),'rpe_rejected_starts':rejected,
            'position_covariance_singular_values':s.tolist(),
            'source_inputs_unchanged':True,'scale_fixed':1.0}
    (out/'independent_validation.json').write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
