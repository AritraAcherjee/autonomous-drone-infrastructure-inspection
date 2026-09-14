"""Execute exactly one authorized DET-FINAL-v1 test; never retry after STARTED."""
from __future__ import annotations
import argparse
from copy import copy
import csv
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
from unittest.mock import patch
import zipfile
from heldout_contract import *

SOURCE=Path(__file__).resolve().parent
RUNTIME=SOURCE/'runtime'

def configure_runtime(runtime):
    runtime=Path(runtime)
    for name in ('settings/Ultralytics','matplotlib','temp','torch','cuda','cache'):
        (runtime/name).mkdir(parents=True,exist_ok=True)
    font=runtime/'settings/Ultralytics/Arial.ttf'
    if not font.exists():shutil.copyfile('C:/Windows/Fonts/arial.ttf',font)
    os.environ.update(YOLO_CONFIG_DIR=str(runtime/'settings'),MPLCONFIGDIR=str(runtime/'matplotlib'),
        TEMP=str(runtime/'temp'),TMP=str(runtime/'temp'),TORCH_HOME=str(runtime/'torch'),
        CUDA_CACHE_PATH=str(runtime/'cuda'),XDG_CACHE_HOME=str(runtime/'cache'),YOLO_OFFLINE='true',
        YOLO_AUTOINSTALL='false',NO_ALBUMENTATIONS_UPDATE='1',WANDB_MODE='disabled',COMET_MODE='DISABLED',
        PYTHONDONTWRITEBYTECODE='1',MPLBACKEND='Agg')

def write_csv(path,rows):
    rows=list(rows)
    with Path(path).open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def modules(root):
    sys.path.insert(0,str(Path(root)/'src'))
    sys.path.insert(0,str(Path(root)/'scripts/analysis'))
    import torch, numpy as np, ultralytics
    import ultralytics.utils.metrics as metrics
    from ultralytics.models.yolo.detect import DetectionValidator
    from ultralytics.data.dataset import YOLODataset
    from detection.training.dataset import ReadOnlyDetectionDataset
    from verify_det_final_v1 import verify_package,fixed_diagnostic_pr
    require(ultralytics.__version__=='8.4.145' and torch.__version__=='2.14.0+cu130','Framework version mismatch')
    require(torch.cuda.is_available(),'Required CUDA unavailable')
    from ultralytics.utils import SETTINGS
    SETTINGS.update({k:False for k in ('sync','wandb','comet','clearml','mlflow','neptune','raytune','tensorboard','dvc') if k in SETTINGS})
    ap_function,ap_source=fixed_ap_function(metrics)
    class HeldoutReadOnlyDataset(ReadOnlyDetectionDataset):
        def __init__(self, *, records, **kwargs):
            require(records and all(r['split']=='test' for r in records),'Only explicitly bound test records')
            require(kwargs.get('cache') is False and kwargs.get('fraction')==1.0,'No cache/fraction override')
            self.records=records
            # Reuse every frozen loading/geometry method; only split admission differs.
            YOLODataset.__init__(self,**kwargs)
    return dict(torch=torch,np=np,ultralytics=ultralytics,metrics=metrics,validator=DetectionValidator,
        dataset=HeldoutReadOnlyDataset,verify_package=verify_package,fixed_pr=fixed_diagnostic_pr,
        ap_function=ap_function,ap_source=ap_source)

def frozen_args(root,out):
    args=dict(read_json(Path(root)/'outputs/analysis/defect_detection/DET-BASELINE/validation_replay/inference_config.json')['args'])
    args.update(model=str(Path(root)/CHECKPOINT),data=str(Path(out)/'evaluation_data.yaml'),
        split='test',project=str(Path(out).parent),name=Path(out).name,save_dir=str(out),exist_ok=False)
    expected=dict(imgsz=640,batch=8,device='0',workers=0,rect=True,quantize=16,conf=.001,iou=.7,max_det=300,
        nms=False,augment=False,agnostic_nms=False,single_cls=False,fraction=1.0,cache=False,compile=False,
        channels_last=False,dnn=False,plots=True,visualize=False,save_json=False,save_txt=False)
    require(all(args[k]==v for k,v in expected.items()),'Frozen evaluation arguments differ')
    return args

def evaluate_bound_records(root,out,records,m,progress):
    """One dataloader traversal. Called only after the durable receipt exists."""
    require(read_json(out/'ONE_TIME_RECEIPT.json')['state']=='STARTED','STARTED required before source loading')
    torch,np=m['torch'],m['np']
    from ultralytics.data import build_dataloader
    from ultralytics.utils import callbacks,ops
    from ultralytics.nn.autobackend import AutoBackend
    data=dict(path=str(root),test=str(root/LIST),nc=6,channels=3,names=dict(enumerate(CLASSES)))
    durable_write(out/'evaluation_data.yaml',data,exclusive=True)
    args=frozen_args(root,out)
    durable_write(out/'evaluation_config.json',dict(args=args,loader=dict(batch=8,workers=0,rect=True,pad=.5,stride=32,
        shuffle=False,drop_last=False,pin_memory=True,rank=-1,cache=False),
        diagnostic_threshold=THRESHOLD,diagnostic_grid_index=186,ap_selector='Installed source with argmax replaced by fixed index 186',
        geometry_adapter='Frozen ReadOnlyDetectionDataset methods; dedicated test-only admission',
        plot_policy='Curves and confusion only; no source-image montages or test-optimum annotations'),exclusive=True)
    (out/'predictions').mkdir()
    image_records=[]
    class Capture(m['validator']):
        @staticmethod
        def _check_max_det(args,datasets):
            require(args.max_det==300,'max_det change prohibited')
        def preprocess(self,batch):
            value=super().preprocess(batch)
            progress['phase']='inference'
            return value
        def update_metrics(self,preds,batch):
            arrays=[];ground=[];po=[0];go=[0];names=[]
            for si,pred in enumerate(preds):
                b=self._prepare_batch(si,batch)
                pg=ops.scale_boxes(b['imgsz'],pred['bboxes'].clone(),b['ori_shape'],b['ratio_pad'])
                gg=ops.scale_boxes(b['imgsz'],b['bboxes'].clone(),b['ori_shape'],b['ratio_pad'])
                arrays.append(torch.cat((pg,pred['conf'][:,None],pred['cls'][:,None]),1).float().cpu().numpy())
                ground.append(torch.cat((gg,b['cls'][:,None]),1).float().cpu().numpy())
                po.append(po[-1]+len(pg));go.append(go[-1]+len(gg))
                name=Path(b['im_file']).relative_to(root).as_posix(); names.append(name)
                image_records.append(dict(image_relative_path=name,oriented_height=int(b['ori_shape'][0]),
                    oriented_width=int(b['ori_shape'][1]),input_height=int(b['imgsz'][0]),input_width=int(b['imgsz'][1]),
                    predictions=len(pg),annotations=len(gg)))
            super().update_metrics(preds,batch)
            part=out/'predictions'/f'batch_{self.batch_i:04d}.npz'
            with part.open('xb') as stream:
                np.savez_compressed(stream,predictions=np.concatenate(arrays),ground_truth=np.concatenate(ground),
                    prediction_offsets=np.array(po),ground_truth_offsets=np.array(go),image_paths=np.array(names))
                stream.flush();os.fsync(stream.fileno())
            progress.update(images_processed=int(self.seen),batches_processed=int(self.batch_i)+1,partial_predictions_exist=True)
            durable_write(out/'progress.json',progress)
        def get_stats(self):
            progress['phase']='metrics'
            stats=self.metrics.process(save_dir=out,plot=False)
            b=self.metrics.box
            np.savez_compressed(out/'metric_stats.npz',**stats)
            np.savez_compressed(out/'curves.npz',x=b.px,p=b.p_curve,r=b.r_curve,f1=b.f1_curve,
                precision_recall=b.prec_values,all_ap=b.all_ap,class_ids=self.metrics.ap_class_index)
            fixed=m['fixed_pr'](b.p_curve,b.r_curve,[int(c) for c in self.metrics.ap_class_index])
            require(fixed['confidence']==THRESHOLD,'Fixed threshold mismatch')
            require(np.array_equal(b.p,b.p_curve[:,186]) and np.array_equal(b.r,b.r_curve[:,186]),'Unexpected operating-point selection')
            lookup={int(c):i for i,c in enumerate(self.metrics.ap_class_index)}
            perclass=[]
            for c,name in enumerate(CLASSES):
                i=lookup.get(c)
                perclass.append(dict(class_id=c,class_name=name,images=int(self.metrics.nt_per_image[c]),
                    instances=int(self.metrics.nt_per_class[c]),precision=None if i is None else float(b.p[i]),
                    recall=None if i is None else float(b.r[i]),f1=None if i is None else float(b.f1[i]),
                    ap50=None if i is None else float(b.ap50[i]),ap50_95=None if i is None else float(b.ap[i]),
                    ap75=None if i is None else float(b.all_ap[i,5])))
            aggregate=dict(dataset='GYU-DET V3 baseline-v1',split='test',model_version='DET-FINAL-v1',
                images=int(self.seen),instances=int(self.metrics.nt_per_class.sum()),
                primary_test_metrics=dict(mAP50=float(b.map50),mAP50_95=float(b.map)),
                fixed_validation_threshold_metrics=dict(precision=fixed['precision'],recall=fixed['recall'],f1=fixed['f1'],
                    confidence=THRESHOLD,grid_index=186,grid_size=1000,label='VALIDATION DIAGNOSTIC THRESHOLD',
                    aggregation='Macro over classes with GT; F1 is mean per-class F1',iou=.5),
                threshold_optimized_on_test=False)
            durable_write(out/'aggregate_metrics.json',aggregate,exclusive=True)
            durable_write(out/'fixed_threshold_metrics.json',fixed,exclusive=True)
            durable_write(out/'per_class_metrics.json',perclass,exclusive=True)
            write_csv(out/'per_class_metrics.csv',perclass)
            durable_write(out/'evaluator_metrics.json',dict(self.metrics.results_dict,
                note='P/R use fixed validation index 186; AP unchanged; no per-test argmax evaluated'),exclusive=True)
            rows=[]
            for i,c in enumerate(self.metrics.ap_class_index):
                for j,x in enumerate(b.px):
                    rows.append(dict(class_id=int(c),confidence=float(x),precision=float(b.p_curve[i,j]),
                        recall=float(b.r_curve[i,j]),f1=float(b.f1_curve[i,j]),precision_at_recall_grid=float(b.prec_values[i,j])))
            write_csv(out/'curves.csv',rows)
            progress.update(partial_metrics_exist=True,metrics_complete=True)
            return self.metrics.results_dict
        def plot_val_samples(self,*args,**kwargs):pass
        def plot_predictions(self,*args,**kwargs):pass
    validator=Capture(args=args,save_dir=out,_callbacks=callbacks.get_default_callbacks())
    progress['phase']='dataset_headers_and_labels'
    dataset=m['dataset'](records=records,img_path=data['test'],imgsz=640,batch_size=8,augment=False,
        hyp=copy(validator.args),rect=True,cache=False,single_cls=False,stride=32,pad=.5,
        prefix='frozen test: ',task='detect',classes=None,data=data,fraction=1.0)
    validator.dataloader=build_dataloader(dataset,8,0,shuffle=False,rank=-1,drop_last=False,pin_memory=True,device=torch.device('cuda:0'))
    original_forward=AutoBackend.forward
    def forward(self,*args,**kwargs):
        if progress['phase']=='inference':
            progress['model_inference_began']=True
            progress['inference_batch_calls']=progress.get('inference_batch_calls',0)+1
        return original_forward(self,*args,**kwargs)
    start=time.perf_counter()
    with patch('ultralytics.engine.validator.check_det_dataset',return_value=data), \
         patch.object(callbacks,'add_integration_callbacks',lambda _:None), \
         patch('ultralytics.utils.downloads.safe_download',side_effect=RuntimeError('Downloads prohibited')), \
         patch.object(m['metrics'],'ap_per_class',m['ap_function']), \
         patch.object(m['metrics'],'plot_mc_curve',side_effect=RuntimeError('Test-optimum plot prohibited')), \
         patch.object(AutoBackend,'forward',forward):
        validator(model=root/CHECKPOINT)
    require(validator.seen==len(records),'Incomplete image traversal')
    names=[r['image_relative_path'] for r in image_records]
    require(len(set(names))==len(records) and set(names)=={r['image'].relative_to(root).as_posix() for r in records},
            'Missing/repeated/substituted image')
    require(validator.args.max_det==300 and validator.args.batch==8 and validator.args.quantize==16 and validator.end2end,
            'Evaluator mutated frozen settings')
    durable_write(out/'images.json',image_records,exclusive=True)
    matrix=validator.confusion_matrix.matrix
    durable_write(out/'confusion_matrix.json',dict(rows_predicted=CLASSES+['background'],columns_truth=CLASSES+['background'],
        confidence=.001,confidence_comparison='>',iou=.45,iou_comparison='>',matching='class-agnostic geometry',matrix=matrix.tolist()),exclusive=True)
    durable_write(out/'timing.json',dict(ms_per_image=validator.speed,evaluator_seconds=time.perf_counter()-start,
        images=len(records),gpu=torch.cuda.get_device_name(0),inference_batch_calls=progress.get('inference_batch_calls',0)),exclusive=True)
    progress['inference_complete']=True
    return validator

def plot_curves(out,m):
    import matplotlib.pyplot as plt
    np=m['np']
    with np.load(out/'curves.npz',allow_pickle=False) as curves:
        x=curves['x'];ids=curves['class_ids']
        for key,label in [('p','Precision'),('r','Recall'),('f1','F1'),('precision_recall','Precision-Recall')]:
            fig,ax=plt.subplots(figsize=(8,5),layout='constrained')
            for i,c in enumerate(ids):ax.plot(x,curves[key][i],label=CLASSES[int(c)],linewidth=1.2)
            if key!='precision_recall':ax.axvline(THRESHOLD,color='black',linestyle='--',label='Fixed validation threshold')
            ax.set(xlim=(0,1),ylim=(0,1),xlabel='Recall' if key=='precision_recall' else 'Confidence',
                ylabel='Precision' if key=='precision_recall' else label,title='DET-FINAL-v1 held-out '+label)
            ax.legend(fontsize=8);fig.savefig(out/(label.replace('-','_')+'_curve.png'),dpi=140);plt.close(fig)

def raw_snapshot(root,records,verify_images=False):
    result={}
    for row in records:
        for key in ('image','label'):
            p=row[key]; stat=p.stat(); digest=sha(p)
            if key=='image' and verify_images:require(digest==row['image_sha256'],'Approved raw image hash mismatch')
            result[p.relative_to(root).as_posix()]=dict(size_bytes=stat.st_size,mtime_ns=stat.st_mtime_ns,sha256=digest)
    return result

def preflight(root):
    verify_clean_freeze(root)
    configure_runtime(RUNTIME)
    guard=AccessGuard(root,root/OUTPUT,RUNTIME);guard.install()
    m=modules(root);verification=m['verify_package'](root)
    records=load_test_metadata(root)
    # CPU checkpoint metadata inspection; no image inference during preflight.
    checkpoint=m['torch'].load(root/CHECKPOINT,map_location='cpu',weights_only=False)
    require(checkpoint['model'].names==dict(enumerate(CLASSES)) and checkpoint['model'].model[-1].nc==6,'Checkpoint class head mismatch')
    require(checkpoint['model'].model[-1].end2end,'Checkpoint is not end-to-end')
    del checkpoint
    metadata=dict(verified_at=now(),freeze_commit_sha=FREEZE,remote_tracking_head=git(root,'rev-parse','refs/remotes/origin/chat02/detector-training'),
        remote_confirmation='User verified actual remote in PowerShell 02A; this process reverified matching origin tracking ref',
        verifier=verification,expected_images=1053,expected_instances=sum(int(r['annotation_count']) for r in records),
        test_split_sha256=LIST_SHA,test_manifest_sha256=TABLE_SHA,metadata_only=True,test_accessed=False,codebrim_accessed=False,
        torch=m['torch'].__version__,ultralytics=m['ultralytics'].__version__,python=sys.version.split()[0],
        cuda_runtime=m['torch'].version.cuda,gpu=m['torch'].cuda.get_device_name(0),
        gpu_memory_bytes=m['torch'].cuda.get_device_properties(0).total_memory,
        source_sha256={n:sha(SOURCE/n) for n in ('heldout_contract.py','evaluate_det_final_v1_test.py')})
    return metadata,records,m,guard

def execute_once(root):
    # Empty ancestor directories are setup metadata, not held-out content.
    (root/OUTPUT).parent.mkdir(parents=True,exist_ok=True)
    pre,records,m,guard=preflight(root);out=root/OUTPUT
    tests=read_json(SOURCE/'PRESTART_TESTS.json')
    require(tests['status']=='PASS' and tests['source_sha256']==pre['source_sha256'],'Runner tests missing or stale')
    # Recheck immutable state immediately before consuming authorization.
    verify_clean_freeze(root)
    started=now(); receipt=dict(schema_version=1,evaluation_id='DET-FINAL-v1_GYU-DET-TEST_001',model_version='DET-FINAL-v1',
        state='STARTED',started_at=started,freeze_commit_sha=FREEZE,manifest_sha256=MANIFEST_SHA,
        checkpoint_path=CHECKPOINT,checkpoint_sha256=CHECKPOINT_SHA,checkpoint_size_bytes=20301573,
        dataset='GYU-DET V3 baseline-v1',split='test',expected_image_count=1053,test_split_sha256=LIST_SHA,
        test_manifest_sha256=TABLE_SHA,evaluation_config=read_json(root/MANIFEST)['evaluation_config'],
        split_binding='Exact approved test records; evaluator split=test',diagnostic_threshold=THRESHOLD,
        test_accessed=True,first_access_authorized=True,retry_allowed=False,codebrim_accessed=False,
        det_improved_executed=False,source_sha256=pre['source_sha256'],images_processed=0,metrics_complete=False,
        inference_complete=False,model_inference_began=False,evaluation_count=1)
    progress=dict(phase='STARTED',images_processed=0,batches_processed=0,model_inference_began=False,
        partial_predictions_exist=False,partial_metrics_exist=False,metrics_complete=False,inference_complete=False)
    timer=time.perf_counter()
    try:
        start_receipt(out,receipt)
        guard.activate(records)
        durable_write(out/'preaccess_verification.json',pre,exclusive=True)
        durable_write(out/'prestart_tests.json',tests,exclusive=True)
        (out/'sources').mkdir()
        for name in ('heldout_contract.py','evaluate_det_final_v1_test.py','test_heldout_runner.py'):
            shutil.copyfile(SOURCE/name,out/'sources'/name)
        (out/'sources/frozen_ap_fixed_index.py').write_text(m['ap_source'],encoding='utf-8')
        (out/'.gitignore').write_text('/predictions/\n/*.npz\n/raw_before.json\n/raw_after.json\n/images.json\n/result_payload.zip\n',encoding='utf-8')
        progress['phase']='raw_integrity_before'
        before=raw_snapshot(root,records,verify_images=True)
        durable_write(out/'raw_before.json',before,exclusive=True)
        evaluate_bound_records(root,out,records,m,progress)
        progress['phase']='evidence_and_integrity'
        plot_curves(out,m)
        after=raw_snapshot(root,records)
        durable_write(out/'raw_after.json',after,exclusive=True)
        require(before==after,'Raw source modified during evaluation')
        require(sha(root/CHECKPOINT)==CHECKPOINT_SHA and sha(root/MANIFEST)==MANIFEST_SHA,'Frozen identity changed')
        require(git(root,'rev-parse','HEAD')==FREEZE and not git(root,'diff','--name-only'),'Frozen tracked files changed')
        aggregate=read_json(out/'aggregate_metrics.json')
        require(aggregate['images']==1053 and aggregate['instances']==pre['expected_instances'],'Evaluation count mismatch')
        require(progress['inference_batch_calls']==132,'Unexpected number of inference batches')
        durable_write(out/'integrity.json',dict(status='PASS',raw_files=len(before),raw_sha_size_mtime_unchanged=True,
            checkpoint_sha256=CHECKPOINT_SHA,manifest_sha256=MANIFEST_SHA,freeze_commit_sha=FREEZE,
            images_processed=1053,unique_images=1053,inference_batch_calls=132,threshold=THRESHOLD,
            test_threshold_optimized=False,training_executed=False,codebrim_accessed=False,det_improved_executed=False),exclusive=True)
        durable_write(out/'provenance.json',dict(preaccess=pre,started_at=started,first_content_access_at=guard.first_content_access_at,
            test_images_opened=len(guard.opened_images),evaluator_source_reference='Frozen evidence_index.json',
            runner_source_sha256=pre['source_sha256'],ap_selector='Only installed AP argmax replaced with constant186; AP and matching unchanged',
            total_seconds_since_started=time.perf_counter()-timer,read_only_source_guard=True,retry_allowed=False),exclusive=True)
        write_report_and_review(out,aggregate)
        payload_paths=[p for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ('ONE_TIME_RECEIPT.json','test_evidence_index.json','result_payload.zip')]
        index=dict(schema_version=1,scope='All result payload files; final receipt and index/package excluded to avoid self-reference',
            files=[dict(path=p.relative_to(out).as_posix(),sha256=sha(p),size_bytes=p.stat().st_size) for p in payload_paths])
        durable_write(out/'test_evidence_index.json',index,exclusive=True)
        with zipfile.ZipFile(out/'result_payload.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in payload_paths+[out/'test_evidence_index.json']:z.write(p,p.relative_to(out).as_posix())
        with zipfile.ZipFile(out/'result_payload.zip') as z:require(z.testzip() is None,'Result archive corrupt')
        for item in index['files']:require(sha(out/item['path'])==item['sha256'],'Result payload hash mismatch')
        final=finish_receipt(out,receipt,'COMPLETED',completed_at=now(),images_expected=1053,images_processed=1053,
            metrics_complete=True,inference_complete=True,model_inference_began=True,heldout_metrics_calculated=True,
            actual_test_content_accessed=guard.content_accessed,images_opened=len(guard.opened_images),
            first_content_access_at=guard.first_content_access_at,total_seconds_since_started=time.perf_counter()-timer,
            artifact_index_sha256=sha(out/'test_evidence_index.json'),result_package_sha256=sha(out/'result_payload.zip'))
        print(json.dumps(dict(receipt=final,aggregate=aggregate),indent=2))
    except BaseException as exc:
        # Any persisted STARTED receipt consumes authorization, even if source access has not yet begun.
        if (out/'ONE_TIME_RECEIPT.json').exists():
            details=dict(failed_at=now(),failure_stage=progress['phase'],error=f'{type(exc).__name__}: {exc}',
                traceback=traceback.format_exc(),images_processed=progress['images_processed'],
                model_inference_began=progress['model_inference_began'],partial_predictions_exist=progress['partial_predictions_exist'],
                partial_metrics_exist=progress['partial_metrics_exist'],metrics_complete=progress['metrics_complete'],
                inference_complete=progress['inference_complete'],actual_test_content_accessed=guard.content_accessed,
                images_opened=len(guard.opened_images),first_content_access_at=guard.first_content_access_at)
            try:finish_receipt(out,receipt,'FAILED',**details)
            except BaseException:durable_write(out/'FAILURE_FALLBACK.json',dict(receipt,**details,state='FAILED'),exclusive=True)
        raise

def write_report_and_review(out,aggregate):
    per=read_json(out/'per_class_metrics.json');fixed=aggregate['fixed_validation_threshold_metrics'];primary=aggregate['primary_test_metrics']
    baseline=dict(precision=.47223142096534465,recall=.4130733263020834,mAP50=.3884237740581788,mAP50_95=.21699306833671056)
    test=dict(precision=fixed['precision'],recall=fixed['recall'],**primary)
    comparison={k:dict(validation=v,test=test[k],test_minus_validation=test[k]-v,absolute_gap=abs(test[k]-v)) for k,v in baseline.items()}
    durable_write(out/'validation_vs_test.json',dict(descriptive_only=True,tuning_performed=False,metrics=comparison),exclusive=True)
    confusion=read_json(out/'confusion_matrix.json');mat=confusion['matrix']
    pairs=sorted([dict(truth=CLASSES[c],predicted=CLASSES[r],count=int(mat[r][c])) for c in range(6) for r in range(6) if r!=c and mat[r][c]],key=lambda r:-r['count'])
    summary=dict(confidence=.001,iou=.45,major_class_confusions=pairs[:10],
        misses_to_background={CLASSES[c]:int(mat[6][c]) for c in range(6)},
        background_false_positives={CLASSES[c]:int(mat[c][6]) for c in range(6)},
        interpretation='Frozen low-floor confusion evidence; distinct from fixed-threshold P/R. Descriptive only; no tuning proposed.')
    durable_write(out/'confusion_summary.json',summary,exclusive=True)
    timing=read_json(out/'timing.json')
    report=f'''# DET-FINAL-v1 one-time held-out evaluation

Frozen model: `{FREEZE}`. GYU-DET V3 baseline-v1 TEST, {aggregate['images']} images and {aggregate['instances']} instances.

Primary test metrics: mAP50 **{primary['mAP50']!r}**; mAP50-95 **{primary['mAP50_95']!r}**.

At the previously selected **VALIDATION DIAGNOSTIC THRESHOLD {THRESHOLD!r}**, index186/1000: macro P **{fixed['precision']!r}**, R **{fixed['recall']!r}**, mean per-class F1 **{fixed['f1']!r}**. These are interpolated evaluator curves at IoU0.5. No test threshold optimization was executed; AP computation retained installed ranked integration semantics.

| Class | Instances | P | R | F1 | AP50 | AP50-95 | AP75 |
|---|---:|---:|---:|---:|---:|---:|---:|
'''
    for r in per:report+='| '+str(r['class_name'])+' | '+' | '.join(str(r[k]) for k in ('instances','precision','recall','f1','ap50','ap50_95','ap75'))+' |\n'
    report+='\n## Descriptive validation comparison\n\n| Metric | Validation | Test | Test - validation | Absolute gap |\n|---|---:|---:|---:|---:|\n'
    for k,v in comparison.items():report+='| '+k+' | '+' | '.join(str(v[n]) for n in ('validation','test','test_minus_validation','absolute_gap'))+' |\n'
    report+='\nThis comparison does not select a model, threshold or future experiment setting. Deployment threshold remains unresolved and must not be selected from held-out results.\n'
    report+='\n## Frozen confusion evidence\n\nConfusion uses confidence>0.001 and class-agnostic IoU>0.45; it is separate from the fixed diagnostic threshold.\n\n'
    report+='\n'.join(f"- Truth {r['truth']} -> predicted {r['predicted']}: {r['count']}" for r in pairs[:5])+'\n'
    report+='\nMisses to background: '+json.dumps(summary['misses_to_background'])+'.\n'
    report+='\n## Timing and integrity\n\n'+json.dumps(timing,indent=2)+'\n'
    report+='\nAll 1053 images were processed exactly once in 132 batches. Checkpoint, manifest and raw SHA/size/mtime checks passed. No training, CODEBRIM access or DET-IMPROVED execution occurred. The exclusive ONE_TIME_RECEIPT.json is authoritative for final COMPLETED/FAILED state and timestamps. No retry is authorized.\n'
    report+='\n## Evidence\n\nFull metrics, per-class values, fixed-threshold metrics, curves, confusion, timing, provenance, integrity, prediction batches and the evidence index are retained in this directory. The result ZIP excludes the final receipt to avoid self-referential hashing; its hash is in that receipt. No evaluation closeout commit is authorized.\n'
    (out/'HELDOUT_REPORT.md').write_text(report,encoding='utf-8')
    rows=[]
    for p in sorted(out.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(out).as_posix()
        kind='REMAIN IGNORED' if rel.startswith('predictions/') or p.suffix=='.npz' or p.name in ('raw_before.json','raw_after.json','images.json','result_payload.zip') else 'MAY COMMIT' if p.suffix=='.png' else 'MUST COMMIT'
        rows.append(dict(path=rel,classification=kind))
    for rel in ('test_evidence_index.json','commit_review.json'):rows.append(dict(path=rel,classification='MUST COMMIT'))
    rows.append(dict(path='result_payload.zip',classification='REMAIN IGNORED'))
    durable_write(out/'commit_review.json',dict(no_commit_authorized=True,files=rows),exclusive=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight',action='store_true');mode.add_argument('--execute-once',action='store_true')
    args=parser.parse_args();root=args.root.resolve()
    if args.preflight:print(json.dumps(preflight(root)[0],indent=2))
    else:execute_once(root)
