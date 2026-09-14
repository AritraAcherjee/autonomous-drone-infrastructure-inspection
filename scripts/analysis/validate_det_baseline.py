"""One guarded validation-only pass to export reproducible analysis evidence."""
from __future__ import annotations
import argparse
from copy import copy
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch
from det_baseline_common import *

def main(root, out):
    check_output(root,out)
    run=root/'outputs/training/defect_detection/DET-BASELINE'
    for name,digest in EXPECTED.items():
        if sha(run/'weights'/name)!=digest:
            raise RuntimeError('Checkpoint mismatch: STOP')
    dest=out/'validation_replay'
    dest.mkdir(parents=True,exist_ok=False)
    runtime=out/'runtime'
    for p in ('settings/Ultralytics','matplotlib','temp'):
        (runtime/p).mkdir(parents=True,exist_ok=True)
    shutil.copyfile('C:/Windows/Fonts/arial.ttf',runtime/'settings/Ultralytics/Arial.ttf')
    os.environ.update(YOLO_CONFIG_DIR=str(runtime/'settings'),MPLCONFIGDIR=str(runtime/'matplotlib'),
        TEMP=str(runtime/'temp'),TMP=str(runtime/'temp'),YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',
        NO_ALBUMENTATIONS_UPDATE='1',WANDB_MODE='disabled',COMET_MODE='DISABLED',PYTHONDONTWRITEBYTECODE='1')
    sys.path.insert(0,str(root/'src'))
    install_guard(root,out)
    import numpy as np
    import torch
    import ultralytics
    from ultralytics.models.yolo.detect import DetectionValidator
    from ultralytics.data import build_dataloader
    from ultralytics.utils import SETTINGS, callbacks, ops
    from ultralytics.utils.metrics import smooth
    from detection.training.config import load_development_data
    from detection.training.dataset import ReadOnlyDetectionDataset
    assert ultralytics.__version__=='8.4.145'
    assert torch.__version__=='2.14.0+cu130'
    SETTINGS.update({k:False for k in ('sync','wandb','comet','clearml','mlflow','neptune','raytune','tensorboard','dvc') if k in SETTINGS})
    _,records=load_development_data(root)
    data=read_json(run/'development_data.yaml')
    data['names']={int(k):v for k,v in data['names'].items()}
    assert set(data)=={'path','train','val','names','nc','channels'}
    assert [str(r['image']) for r in records['valid']] == (run/'valid.txt').read_text().splitlines()
    original=read_json(run/'resolved_config.json')['ultralytics']
    args=dict(original)
    args.update(mode='val',model=str(run/'weights/best.pt'),data=str(run/'development_data.yaml'),
        batch=8,rect=True,quantize=16,device='0',workers=0,cache=False,imgsz=640,conf=.001,iou=.7,
        max_det=300,nms=False,augment=False,plots=True,save_json=False,save_txt=False,compile=False,
        project=str(out),name='validation_replay',save_dir=str(dest),exist_ok=False,visualize=False)
    image_records=[];pred_arrays=[];gt_arrays=[];pred_offsets=[0];gt_offsets=[0]
    class CaptureValidator(DetectionValidator):
        def update_metrics(self,preds,batch):
            for si,pred in enumerate(preds):
                b=self._prepare_batch(si,batch)
                pg=ops.scale_boxes(b['imgsz'],pred['bboxes'].clone(),b['ori_shape'],b['ratio_pad'])
                gg=ops.scale_boxes(b['imgsz'],b['bboxes'].clone(),b['ori_shape'],b['ratio_pad'])
                pred_arrays.append(torch.cat((pg,pred['conf'][:,None],pred['cls'][:,None]),1).cpu().numpy())
                gt_arrays.append(torch.cat((gg,b['cls'][:,None]),1).cpu().numpy())
                pred_offsets.append(pred_offsets[-1]+len(pg));gt_offsets.append(gt_offsets[-1]+len(gg))
                image_records.append(dict(image_relative_path=Path(b['im_file']).relative_to(root).as_posix(),
                    oriented_height=int(b['ori_shape'][0]),oriented_width=int(b['ori_shape'][1]),
                    input_height=int(b['imgsz'][0]),input_width=int(b['imgsz'][1]),
                    predictions=len(pg),annotations=len(gg)))
            super().update_metrics(preds,batch)
        def get_stats(self):
            self.metrics.process(save_dir=self.save_dir,plot=self.args.plots,on_plot=self.on_plot)
            b=self.metrics.box
            np.savez_compressed(dest/'curves.npz',x=b.px,p=b.p_curve,r=b.r_curve,f1=b.f1_curve,
                                precision_recall=b.prec_values,all_ap=b.all_ap)
            idx=int(smooth(b.f1_curve.mean(0),.1).argmax())
            per_class=[]
            for i,c in enumerate(self.metrics.ap_class_index):
                per_class.append(dict(class_id=int(c),class_name=CLASSES[int(c)],
                    precision=float(b.p[i]),recall=float(b.r[i]),ap50=float(b.ap50[i]),ap50_95=float(b.ap[i]),
                    ap75=float(b.all_ap[i,5]),instances=int(self.metrics.nt_per_class[c]),
                    images=int(self.metrics.nt_per_image[c]),metric_source='new_validation_replay'))
            write_csv(dest/'per_class_metrics_full_precision.csv',per_class)
            write_json(dest/'metric_summary.json',dict(metrics=self.metrics.results_dict,
                automatic_max_mean_f1_confidence=float(b.px[idx]),confusion_confidence=self.confusion_matrix_conf,
                confusion_iou=.45,metric_iou=list(np.arange(.5,1,.05)),per_class=per_class,
                note='Fresh validation inference, not recovered historical precision. No deployment threshold selected.'))
            return self.metrics.results_dict
    validator=CaptureValidator(args=args,save_dir=dest,_callbacks=callbacks.get_default_callbacks())
    dataset=ReadOnlyDetectionDataset(records=records['valid'],img_path=data['val'],imgsz=640,batch_size=8,
        augment=False,hyp=copy(validator.args),rect=True,cache=False,single_cls=False,stride=32,pad=.5,
        prefix='analysis val: ',task='detect',classes=None,data=data,fraction=1.0)
    validator.dataloader=build_dataloader(dataset,8,0,shuffle=False,rank=-1,drop_last=False,pin_memory=True,device=torch.device('cuda:0'))
    ckpt=torch.load(run/'weights/best.pt',map_location='cpu',weights_only=False)
    write_json(dest/'checkpoint_metadata.json',{k:v for k,v in ckpt.items() if k not in ('model','ema','optimizer','train_results','scaler')})
    del ckpt
    write_json(dest/'inference_config.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),args=args,
        data=data,checkpoint_sha256=EXPECTED['best.pt'],loader='existing ReadOnlyDetectionDataset',
        rectangular=True,pad=.5,batch=8,workers=0,image_cache=False,label_cache=False,
        evaluation_precision='FP16; final trainer validator retained quantize=16 from CUDA validation',
        installed_version=ultralytics.__version__,torch=torch.__version__,gpu=torch.cuda.get_device_name(0),
        heldout_access=False,codebrim_access=False,training_executed=False,
        source_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}))
    started=time.perf_counter()
    with patch('ultralytics.engine.validator.check_det_dataset',return_value=data),patch.object(callbacks,'add_integration_callbacks',lambda _:None),patch('ultralytics.utils.downloads.safe_download',side_effect=RuntimeError('Downloads prohibited')):
        metrics=validator(model=run/'weights/best.pt')
    np.savez_compressed(dest/'predictions_valid.npz',predictions=np.concatenate(pred_arrays),ground_truth=np.concatenate(gt_arrays),
        prediction_offsets=np.array(pred_offsets),ground_truth_offsets=np.array(gt_offsets))
    write_json(dest/'images.json',image_records)
    write_json(dest/'confusion_matrix.json',dict(rows_predicted=CLASSES+['background'],columns_truth=CLASSES+['background'],
        confidence=validator.confusion_matrix_conf,iou=.45,matrix=validator.confusion_matrix.matrix,
        source='new_validation_replay'))
    write_json(dest/'completion.json',dict(status='PASS',images=len(image_records),instances=gt_offsets[-1],
        predictions=pred_offsets[-1],seconds=time.perf_counter()-started,speed=validator.speed,metrics=metrics,
        checkpoint_sha_after=sha(run/'weights/best.pt'),finished_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(metrics,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.root.resolve(),a.out.resolve())
