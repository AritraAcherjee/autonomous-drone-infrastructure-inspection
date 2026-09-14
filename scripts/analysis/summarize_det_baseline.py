"""Descriptive validation error strata; preserves existing metric definitions."""
from __future__ import annotations
import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
import sys
import numpy as np
from det_baseline_common import *

def ious(a,b):
    a=np.asarray(a,dtype=np.float64).reshape(-1,4);b=np.asarray(b,dtype=np.float64).reshape(-1,4)
    inter=np.maximum(0,np.minimum(a[:,None,2:],b[None,:,2:])-np.maximum(a[:,None,:2],b[None,:,:2])).prod(2)
    aa=np.maximum(0,a[:,2:]-a[:,:2]).prod(1);bb=np.maximum(0,b[:,2:]-b[:,:2]).prod(1)
    return inter/(aa[:,None]+bb[None,:]-inter+1e-7)

def match(iou,gcls,pcls,threshold=.5):
    """Greedy descending IoU, one-to-one and class-aware for diagnostic counts.

    These integer operating-point diagnostics are not interpolated official
    P/R and do not replace the installed evaluator's AP calculation.
    """
    candidates=np.argwhere((iou>=threshold)&(gcls[:,None]==pcls[None,:]))
    candidates=sorted(candidates.tolist(),key=lambda pair:(-iou[tuple(pair)],pair[0],pair[1]))
    usedg=set();usedp=set();pairs=[]
    for g,p in candidates:
        if g not in usedg and p not in usedp:
            usedg.add(g);usedp.add(p);pairs.append((g,p))
    return pairs

def summary_rows(rows,keys):
    groups=defaultdict(list)
    for r in rows:groups[tuple(r[k] for k in keys)].append(r)
    result=[]
    for key,group in sorted(groups.items()):
        n=len(group);tp=sum(r['detected'] for r in group);low=sum(r['detected_at_floor'] for r in group)
        result.append(dict(zip(keys,key),instances=n,tp=tp,fn=n-tp,recall=tp/n,fn_rate=1-tp/n,
                           tp_at_floor=low,recall_at_floor=low/n,share_of_all_fn=(n-tp)/max(1,sum(1-r['detected'] for r in rows))))
    return result

def main(root,out):
    check_output(root,out)
    dest=out/'validation_replay';meta=read_json(dest/'metric_summary.json');images=read_json(dest/'images.json')
    d=np.load(dest/'predictions_valid.npz'); conf=float(meta['automatic_max_mean_f1_confidence'])
    # Counts at the evaluator's automatically reported point are descriptive;
    # no deployment threshold is optimized or selected.
    gts=[];prs=[];imrows=[];train_counts=Counter()
    sys.path.insert(0,str(root/'src'))
    for r in csv.DictReader((root/'data/manifests/gyu_det_v3_baseline_v1/train.csv').open()):
        p=root/r['label_relative_path']
        if not within(p,root/'data/raw/gyu_det/v3/extracted/train/train/labels'):raise ValueError('Unapproved training label')
        train_counts.update(int(line.split()[0]) for line in p.read_text().splitlines() if line.strip())
    for i,im in enumerate(images):
        name=im['image_relative_path'];h=im['oriented_height'];w=im['oriented_width']
        if not within(root/name,root/'data/raw/gyu_det/v3/extracted/valid/valid/images'):raise ValueError('Unapproved validation path')
        gt=d['ground_truth'][d['ground_truth_offsets'][i]:d['ground_truth_offsets'][i+1]]
        pred=d['predictions'][d['prediction_offsets'][i]:d['prediction_offsets'][i+1]]
        label_path=(root/name).parent.parent/'labels'/((root/name).stem+'.txt')
        labels=np.loadtxt(label_path,ndmin=2)
        assert len(labels)==len(gt) and np.array_equal(labels[:,0],gt[:,4])
        iou=ious(gt[:,:4],pred[:,:4]);mask=pred[:,4]>=conf;selected=np.flatnonzero(mask)
        pairs=match(iou[:,mask],gt[:,4],pred[mask,5]);lowpairs=match(iou,gt[:,4],pred[:,5])
        matched_g={g for g,p in pairs};matched_p={selected[p] for g,p in pairs};low_g={g for g,p in lowpairs}
        dense='sparse_1_2' if len(gt)<=2 else 'typical_3_6' if len(gt)<=6 else 'dense_7_plus'
        multi='multi_class' if len(set(gt[:,4]))>1 else 'single_class'
        mp=h*w/1e6;aspect=max(h,w)/min(h,w)
        res='<1MP' if mp<1 else '1_to_4MP' if mp<4 else '4_to_12MP' if mp<12 else '12MP_plus'
        ar='up_to_1.5' if aspect<=1.5 else '1.5_to_2' if aspect<=2 else 'over_2'
        for j,g in enumerate(gt):
            same=pred[:,5]==g[4];best_same=float(iou[j,same].max()) if same.any() else 0
            same_op=same&mask;wrong_op=(~same)&mask
            bs=float(iou[j,same_op].max()) if same_op.any() else 0
            bw=float(iou[j,wrong_op].max()) if wrong_op.any() else 0
            ba=float(iou[j,mask].max()) if mask.any() else 0
            kind='detected' if j in matched_g else 'score_suppressed' if j in low_g else 'class_confusion' if bw>=.5 else 'localization_0.1_to_0.5' if .1<=bs<.5 else 'weak_or_wrong_class_overlap' if ba>=.1 else 'no_overlap_at_operating_point'
            area=float(labels[j,3]*labels[j,4]);iw=float(labels[j,3]*w*640/max(h,w));ih=float(labels[j,4]*h*640/max(h,w));mins=min(iw,ih)
            pix='<4px' if mins<4 else '4_to_8px' if mins<8 else '8_to_16px' if mins<16 else '16_to_32px' if mins<32 else '32px_plus'
            overlaps=ious(gt[j:j+1,:4],gt[:,:4])[0];overlaps[j]=0
            row=dict(image=name,gt_index=j,class_id=int(g[4]),class_name=CLASSES[int(g[4])],
                size=size_bin(area),relative_area=area,input_width_approx=iw,input_height_approx=ih,
                min_input_side_bin=pix,detected=int(j in matched_g),detected_at_floor=int(j in low_g),
                error_category=kind,best_same_class_iou_at_floor=best_same,best_same_class_iou_at_point=bs,
                best_wrong_class_iou_at_point=bw,density=dense,class_mix=multi,resolution=res,
                source_width=w,source_height=h,source_megapixels=mp,aspect_bin=ar,annotation_count=len(gt),
                overlapping_gt=int(float(overlaps.max(initial=0))>=.1))
            gts.append(row)
        for j in selected:
            pg=pred[j];same=gt[:,4]==pg[5];bs=float(iou[same,j].max()) if same.any() else 0
            wrong=~same;bw=float(iou[wrong,j].max()) if wrong.any() else 0
            kind='tp' if j in matched_p else 'duplicate_candidate' if bs>=.5 else 'class_confusion' if bw>=.5 else 'localization_0.1_to_0.5' if bs>=.1 else 'unmatched_or_ambiguous'
            prs.append(dict(image=name,prediction_index=int(j),class_id=int(pg[5]),class_name=CLASSES[int(pg[5])],
                confidence=float(pg[4]),tp=int(j in matched_p),error_category=kind,best_same_class_iou=bs,best_wrong_class_iou=bw))
        imrows.append(dict(im,analysis_confidence=conf,tp=len(matched_g),fn=len(gt)-len(matched_g),
            fp=int(mask.sum())-len(matched_g),recall=len(matched_g)/len(gt),density=dense,class_mix=multi,
            resolution=res,aspect_bin=ar,tiny_small=sum(size_bin(float(r[3]*r[4])) in ('tiny','small') for r in labels)))
    write_csv(out/'ground_truth_errors.csv',gts);write_csv(out/'prediction_errors.csv',prs);write_csv(out/'image_error_summary.csv',imrows)
    for filename,keys in [('size_analysis',['size']),('class_size_analysis',['class_name','size']),
        ('density_analysis',['density']),('density_size_analysis',['density','size']),('class_mix_analysis',['class_mix']),
        ('source_resolution_analysis',['resolution']),('resolution_size_analysis',['resolution','size']),
        ('source_aspect_analysis',['aspect_bin']),('input_detail_analysis',['min_input_side_bin']),
        ('overlap_analysis',['overlapping_gt'])]:
        write_csv(out/(filename+'.csv'),summary_rows(gts,keys))
    per_class=[]
    for r in meta['per_class']:
        c=r['class_id'];cg=[x for x in gts if x['class_id']==c];cp=[x for x in prs if x['class_id']==c]
        per_class.append(dict(r,train_instances=train_counts[c],validation_instances=len(cg),
            diagnostic_tp=sum(x['detected'] for x in cg),diagnostic_fn=sum(1-x['detected'] for x in cg),
            diagnostic_fp=sum(1-x['tp'] for x in cp),tiny_small_instances=sum(x['size'] in ('tiny','small') for x in cg),
            analysis_confidence=conf,ap50_to_ap5095_drop=r['ap50']-r['ap50_95']))
    write_csv(out/'per_class_metrics.csv',per_class)
    matrix=read_json(dest/'confusion_matrix.json');m=np.array(matrix['matrix'],int)
    original=np.array([[288,58,20,0,17,3,23108],[31,1398,114,26,98,65,64245],
        [14,297,307,2,9,10,20667],[0,24,3,96,19,0,3907],[6,68,1,61,1008,20,28008],
        [0,85,13,2,7,186,7391],[27,199,21,41,169,94,0]])
    write_json(out/'confusion_summary.json',dict(matrix,original_matrix_visual_transcription=original,
        original_transcription_matches_replay=bool(np.array_equal(m,original)),
        background_fp_total=int(m[:6,6].sum()),background_fn_total=int(m[6,:6].sum()),
        class_confusions_total=int(m[:6,:6].sum()-np.trace(m[:6,:6])),
        note='Rows predicted, columns truth; confidence >0.001 and IoU >0.45. Original PNG counts visually transcribed; zero blanks verified against replay. Not a deployment operating point.'))
    confusions=[dict(truth=CLASSES[c],predicted=CLASSES[r],count=int(m[r,c]),fraction_of_truth=float(m[r,c]/m[:,c].sum()))
                for c in range(6) for r in range(6) if r!=c and m[r,c]]
    write_csv(out/'confusion_pairs.csv',sorted(confusions,key=lambda x:-x['count']))
    write_csv(out/'confusion_class_summary.csv',[dict(class_name=CLASSES[c],truth=int(m[:,c].sum()),correct=int(m[c,c]),
        missed_to_background=int(m[6,c]),missed_fraction=float(m[6,c]/m[:,c].sum()),
        predicted_background_fp=int(m[c,6]),wrong_class_predictions=int(m[c,:6].sum()-m[c,c]),
        truth_confused_to_other=int(m[:6,c].sum()-m[c,c])) for c in range(6)])
    curves=np.load(dest/'curves.npz');curve_rows=[]
    for c in range(6):
        for threshold in (.001,.05,.1,conf,.25,.5):
            idx=int(np.abs(curves['x']-threshold).argmin())
            curve_rows.append(dict(class_name=CLASSES[c],requested_confidence=threshold,curve_grid_confidence=float(curves['x'][idx]),
                precision=float(curves['p'][c,idx]),recall=float(curves['r'][c,idx]),f1=float(curves['f1'][c,idx])))
    write_csv(out/'curve_diagnostic_points.csv',curve_rows)
    write_json(out/'error_analysis.json',dict(images=len(images),instances=len(gts),predictions_at_point=len(prs),
        analysis_confidence=conf,matching='Greedy descending IoU >=0.5, one-to-one same-class, native oriented coordinates; integer diagnostic counts, separate from evaluator interpolated P/R.',
        threshold_policy='Use automatic mean-F1 point from baseline replay; no deployment threshold selected. Additional curve readings only describe sensitivity.',
        tp=sum(r['detected'] for r in gts),fn=sum(1-r['detected'] for r in gts),fp=sum(1-r['tp'] for r in prs),
        fn_categories=dict(Counter(r['error_category'] for r in gts if not r['detected'])),
        fp_categories=dict(Counter(r['error_category'] for r in prs if not r['tp'])),
        size_convention='M1 relative box area: tiny <.001; small [.001,.01); medium [.01,.1); large >=.1.',
        size_ap_omitted='AP/precision by size not reported: a defensible size-specific ignore policy is not implemented; do not allocate unmatched FPs to ground-truth size.',
        density_convention='Analysis-only bins: 1-2 sparse, 3-6 typical, >=7 dense; distinct from M1 size convention.',
        uncertainty='Descriptive single-checkpoint validation associations; class, density and resolution confounded. No causal or across-seed uncertainty claim.',
        per_class=per_class,size=summary_rows(gts,['size']),density=summary_rows(gts,['density']),
        class_mix=summary_rows(gts,['class_mix']),resolution=summary_rows(gts,['resolution']),
        original_matrix_matches_replay=bool(np.array_equal(m,original))))
    print(json.dumps(read_json(out/'error_analysis.json'),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.root.resolve(),a.out.resolve())
