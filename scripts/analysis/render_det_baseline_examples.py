"""Plot measured validation examples; source images/annotations are never saved."""
import argparse
import csv
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps,ImageDraw,ImageFont
from det_baseline_common import *

CASES=[('8622.JPG',4,'Tiny Hole miss'),('9217.jpg',10,'Thin reinforcement / scale loss'),
       ('11986.jpg',0,'Crack localization / weak contrast'),('9194.jpg',1,'Seepage misses / Honeycombing predictions'),
       ('9199.jpg',0,'Breakage / Reinforcement confusion'),('12001.jpg',0,'Broad texture / annotation ambiguity'),
       ('12297.jpg',3,'Overlapping Crack boxes'),('12254.jpg',0,'Dense image: 59 annotations'),
       ('12305.jpg',0,'Small source image / many defects'),('11992.jpg',1,'Clustered Breakage misses')]
SHORT=['Cr','Br','HoC','Hole','ER','See']
COLORS=['#00b9ff','#ff9800','#ba68c8','#e7cb1e','#1abc9c','#ff62aa']

def main(root,out):
    check_output(root,out)
    dest=out/'validation_replay';images=read_json(dest/'images.json');d=np.load(dest/'predictions_valid.npz')
    errs=list(csv.DictReader((out/'ground_truth_errors.csv').open()))
    conf=read_json(dest/'metric_summary.json')['automatic_max_mean_f1_confidence']
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',21);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    cases=[]
    for name,focus,title in CASES:
        i=next(i for i,r in enumerate(images) if Path(r['image_relative_path']).name==name);im=images[i]
        path=root/im['image_relative_path']
        if not within(path,root/'data/raw/gyu_det/v3/extracted/valid/valid/images'):raise ValueError('Only approved validation images')
        with Image.open(path) as opened:source=ImageOps.exif_transpose(opened).convert('RGB')
        assert source.size==(im['oriented_width'],im['oriented_height'])
        gt=d['ground_truth'][d['ground_truth_offsets'][i]:d['ground_truth_offsets'][i+1]]
        pred=d['predictions'][d['prediction_offsets'][i]:d['prediction_offsets'][i+1]]
        pred=pred[pred[:,4]>=conf]
        canvas=Image.new('RGB',(1600,1090),'#101923');draw=ImageDraw.Draw(canvas)
        draw.text((22,12),f'{name} | {title} | source {source.width} x {source.height}',font=font,fill='white')
        draw.text((22,44),'Left: approved GT (index:class). Right: best.pt predictions at confidence >= 0.186186.',font=small,fill='#c4d3e0')
        scale=min(770/source.width,545/source.height)
        thumb=source.resize((round(source.width*scale),round(source.height*scale)))
        for side,boxes in enumerate((gt,pred)):
            ox=20+side*800;oy=88
            canvas.paste(thumb,(ox,oy))
            for j,b in enumerate(boxes):
                c=int(b[4] if side==0 else b[5]);xy=[ox+b[0]*scale,oy+b[1]*scale,ox+b[2]*scale,oy+b[3]*scale]
                draw.rectangle(xy,outline=COLORS[c],width=2)
                text=f'{j}:{SHORT[c]}' if side==0 else f'{SHORT[c]} {b[4]:.2f}'
                tx=max(ox,min(xy[0],ox+630));ty=max(oy,min(xy[1]-17,oy+520))
                bbox=draw.textbbox((tx,ty),text,font=small);draw.rectangle(bbox,fill='#071016');draw.text((tx,ty),text,font=small,fill=COLORS[c])
        row=next(r for r in errs if r['image']==im['image_relative_path'] and int(r['gt_index'])==focus)
        draw.text((22,650),f'Focus GT #{focus}: {row["class_name"]} | {row["size"]} | {row["error_category"]}',font=font,fill='white')
        draw.text((22,682),f'Approximate target at 640: {float(row["input_width_approx"]):.1f} x {float(row["input_height_approx"]):.1f} px. Crops below are display-only; no extra inference.',font=small,fill='#c4d3e0')
        b=gt[focus,:4];cx=(b[0]+b[2])/2;cy=(b[1]+b[3])/2;bw=max(96,(b[2]-b[0])*2);bh=max(96,(b[3]-b[1])*2)
        box=(max(0,int(cx-bw/2)),max(0,int(cy-bh/2)),min(source.width,int(cx+bw/2)),min(source.height,int(cy+bh/2)))
        crop=source.crop(box);crop_scale=min(650/crop.width,310/crop.height)
        crop=crop.resize((round(crop.width*crop_scale),round(crop.height*crop_scale)),Image.Resampling.LANCZOS)
        canvas.paste(crop,(22,725));draw.text((22,1040),'Original-resolution crop (display resized)',font=small,fill='white')
        low=source.resize((round(source.width*640/max(source.size)),round(source.height*640/max(source.size))),Image.Resampling.BILINEAR)
        factor=640/max(source.size);lbox=tuple(round(v*factor) for v in box)
        lcrop=low.crop(lbox).resize(crop.size,Image.Resampling.NEAREST)
        canvas.paste(lcrop,(815,725));draw.text((815,1040),'640-scale crop enlarged with nearest-neighbor (approximation)',font=small,fill='white')
        draw.text((815,1063),'Cr=Crack Br=Breakage HoC=Honeycombing ER=Reinforcement See=Seepage',font=small,fill='#c4d3e0')
        output=out/'examples'/f'{Path(name).stem}_review.jpg';output.parent.mkdir(exist_ok=True)
        canvas.save(output,quality=91)
        cases.append(dict(image=im['image_relative_path'],focus_gt_index=focus,title=title,plot=output.relative_to(out).as_posix(),
                          target=row,selection='Purposive illustrative case, not a prevalence sample.'))
    write_json(out/'qualitative_example_candidates.json',cases)
    print(f'Rendered {len(cases)} validation review plates')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.root.resolve(),a.out.resolve())
