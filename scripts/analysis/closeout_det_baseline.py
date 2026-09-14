"""Verify frozen provenance and summarize the recorded learning curves."""
import argparse
import csv
from datetime import datetime, timezone
import statistics
import subprocess
from pathlib import Path
from det_baseline_common import *

def main(root, out):
    check_output(root, out)
    run = root/'outputs/training/defect_detection/DET-BASELINE'
    prov, ev, ident, resolved = [read_json(run/n) for n in ('provenance.json','run_evidence.json','dataset_identity.json','resolved_config.json')]
    assertions = {}
    def verify(name, actual, expected):
        assertions[name] = dict(actual=actual, expected=expected, match=actual == expected)
        if actual != expected:
            raise RuntimeError(f'PROVENANCE MISMATCH; STOP: {name}: {actual!r} != {expected!r}')
    verify('run_sha', prov['git']['sha'], COMMIT)
    git = ['git', '-c', f'safe.directory={root.as_posix()}']
    verify('current_sha', subprocess.check_output(git+['rev-parse','HEAD'], cwd=root, text=True).strip(), COMMIT)
    verify('branch', prov['git']['branch'], 'chat02/detector-training')
    for name, expected in EXPECTED.items():
        verify(name+'_stored_sha', ev['checkpoints'][name]['sha256'], expected)
        verify(name+'_current_sha', sha(run/'weights'/name), expected)
    acquisition = read_json(run/'checkpoint_acquisition.json')
    verify('initial_checkpoint', sha(acquisition['local_path']), acquisition['sha256'])
    for path, expected in {**prov['source_sha256'], **ident['hashes'], 'scripts/train_detector.py': prov['cli_sha256']}.items():
        verify(path, sha(root/path), expected)
    for s, count in [('train',8305),('valid',1040)]:
        actual = [Path(p).resolve().relative_to(root).as_posix() for p in (run/f'{s}.txt').read_text().splitlines()]
        verify(s+'_membership', actual == ident['selected'][s], True)
        verify(s+'_count', len(actual), count)
    rows = [{k: float(v) for k,v in r.items()} for r in csv.DictReader((run/'results.csv').open())]
    best = max(rows, key=lambda r:r['metrics/mAP50-95(B)'])
    verify('epochs_completed', len(rows), 92)
    verify('best_epoch_csv', int(best['epoch']), 62)
    verify('patience', resolved['ultralytics']['patience'], 30)
    verify('classes', list(ev['classes'].values()), CLASSES)
    frozen = inventory(run)
    write_json(out/'baseline_inventory_before.json', frozen)
    # Existing post-training evidence is reused; only approved development file
    # metadata is checked. No held-out paths are opened or enumerated here.
    before = read_json(run/'raw_after.json')
    changes, observed = [], 0
    for s in ('train','valid'):
        for row in csv.DictReader((root/f'data/manifests/gyu_det_v3_baseline_v1/{s}.csv').open()):
            for key in ('image_relative_path','label_relative_path'):
                p=root/row[key]; st=p.stat(); old=before[p.relative_to(root/'data/raw').as_posix()]
                observed += 1
                if (st.st_size,st.st_mtime_ns)!=(old['size'],old['mtime_ns']):
                    changes.append(row[key])
    verify('development_metadata_changes', changes, [])
    status = subprocess.check_output(git+['status','--porcelain=v1'],cwd=root,text=True)
    write_json(out/'baseline_provenance.json', dict(analysis_utc=datetime.now(timezone.utc).isoformat(), source_root=root,
        run=run, git=prov['git'], current_git_status=status, environment=prov['environment'], packages=prov['packages'],
        acquisition=acquisition, resolved_config=resolved, dataset_identity={k:v for k,v in ident.items() if k!='selected'},
        development_data=read_json(run/'development_data.yaml'), run_evidence=ev, best_epoch=int(best['epoch']),
        reported_hours=25.248, train_validation_hours=ev['train_validation_seconds']/3600,
        fit_hours=ev['fit_seconds']/3600, assertions=assertions, raw_existing_immutability=read_json(run/'raw_immutability.json'),
        current_development_metadata=dict(files=observed,changes=changes),
        original_per_class_precision='Only 3-significant-digit trainer.log/plot values persisted; fresh inference is separately labeled.'))
    columns=[k for k in rows[0] if k not in ('epoch','time')]
    windows=[(1,10),(21,30),(41,50),(53,62),(63,72),(73,82),(83,90),(91,92)]
    summaries=[]
    for start,end in windows:
        block=[r for r in rows if start<=r['epoch']<=end]
        summary=dict(start_epoch=start,end_epoch=end,epochs=len(block))
        for k in columns:
            summary[k+'_mean']=statistics.mean(r[k] for r in block)
        summaries.append(summary)
    write_csv(out/'learning_curve_windows.csv',summaries)
    points=[rows[e-1] for e in (1,10,20,30,40,50,60,62,70,80,89,90,91,92)]
    write_csv(out/'learning_curve_selected_epochs.csv',points)
    trends={k:dict(epoch_1=rows[0][k],best_epoch_62=best[k],last_epoch_92=rows[-1][k],
        change_62_to_92=rows[-1][k]-best[k],relative_change_62_to_92=(rows[-1][k]/best[k]-1) if best[k] else None,
        best_value=max(r[k] for r in rows) if 'metrics/' in k else min(r[k] for r in rows)) for k in columns}
    durations=[r['time']-(rows[i-1]['time'] if i else 0) for i,r in enumerate(rows)]
    write_json(out/'learning_curve_summary.json',dict(best_epoch=62,early_stop_epoch=92,patience=30,
        selection='Installed Metric.fitness weights mAP50-95 only', mosaic_shutdown_first_epoch=91,
        mosaic_note='Zero-based epoch==100-10; only epochs 91 and 92 completed without mosaic.',
        canonical_final_best_metrics=ev['metrics'],epoch62_csv_metrics={k:v for k,v in best.items() if 'metrics/' in k},
        original_final_vs_epoch62='Separate final best.pt FP16 validation vs in-training EMA/autocast; do not conflate.',
        metrics=trends,epoch_seconds=dict(median=statistics.median(durations),mean=statistics.mean(durations),
        last20_mean=statistics.mean(durations[-20:]),minimum=min(durations),maximum=max(durations)),windows=summaries))
    print(json.dumps(dict(provenance='PASS',frozen_files=len(frozen),development_metadata_files=observed,best=best,last=rows[-1],trends=trends),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.root.resolve(),a.out.resolve())
