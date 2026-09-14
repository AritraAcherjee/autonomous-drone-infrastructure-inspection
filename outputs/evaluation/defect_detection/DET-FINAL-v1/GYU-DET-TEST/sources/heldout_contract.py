"""Fail-closed receipt, identity and file-access contract for one held-out run."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

FREEZE = 'd9cd2f5b58559d45e5d4a42ce702c595345e292b'
MANIFEST = 'configs/detection/det_final_v1.yaml'
MANIFEST_SHA = '5883001e9b8ad7738612280d1a717157291d1655a47100aa75ba9298832ff560'
CHECKPOINT = 'outputs/training/defect_detection/DET-BASELINE/weights/best.pt'
CHECKPOINT_SHA = '4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3'
LIST = 'data/processed/gyu_det_v3_baseline_v1/splits/test.txt'
LIST_SHA = '8c973b5ddd8269e81bc13a8f42040f48fa3dfd1edcdcb838ce325d7d0cac6413'
TABLE = 'data/manifests/gyu_det_v3_baseline_v1/test.csv'
TABLE_SHA = '6a60c2b97387b3e9849f28b11163f3a4f184ea129ae074664549564a9cac98cb'
OUTPUT = 'outputs/evaluation/defect_detection/DET-FINAL-v1/GYU-DET-TEST'
CLASSES = ['Crack','Breakage','Honeycombing','Hole','Exposed Reinforcement','Seepage']
THRESHOLD = 0.18618618618618618

def require(condition, message):
    if not condition: raise ValueError(message)

def now(): return datetime.now(timezone.utc).isoformat()

def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def json_bytes(value):
    return (json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')

def durable_write(path, value, exclusive=False):
    """Flush before publication; exclusive receipt creation never overwrites."""
    path=Path(path); raw=json_bytes(value)
    if exclusive:
        with path.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    else:
        temporary=path.with_name(path.name+'.next')
        with temporary.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,path)

def start_receipt(out, payload):
    out=Path(out)
    require(not out.exists(),'Output already exists: one-time operation refused')
    out.mkdir(parents=True,exist_ok=False)
    require(payload['state']=='STARTED' and payload['test_accessed'] is True and payload['retry_allowed'] is False,
            'Invalid STARTED receipt')
    durable_write(out/'ONE_TIME_RECEIPT.json',payload,exclusive=True)
    durable_write(out/'STARTED_RECEIPT.json',payload,exclusive=True)

def finish_receipt(out, initial, state, **details):
    require(state in ('COMPLETED','FAILED'),'Invalid final state')
    current=read_json(Path(out)/'ONE_TIME_RECEIPT.json')
    require(current['state']=='STARTED' and current['started_at']==initial['started_at'],'Receipt state transition refused')
    value=dict(initial,**details)
    value.update(state=state,retry_allowed=False,test_accessed=True)
    durable_write(Path(out)/'ONE_TIME_RECEIPT.json',value)
    return value

def git(root,*args):
    return subprocess.check_output(['git','-c',f'safe.directory={Path(root).as_posix()}',*args],cwd=root,text=True).strip()

def verify_clean_freeze(root):
    require(git(root,'branch','--show-current')=='chat02/detector-training','Wrong branch')
    require(git(root,'rev-parse','HEAD')==FREEZE,'Freeze HEAD mismatch')
    require(git(root,'rev-parse','refs/remotes/origin/chat02/detector-training')==FREEZE,'Remote-tracking freeze mismatch')
    require(not git(root,'status','--porcelain=v1','--untracked-files=all'),'Working tree must be clean before STARTED')
    require(sha(Path(root)/MANIFEST)==MANIFEST_SHA,'Manifest hash mismatch')
    require(sha(Path(root)/CHECKPOINT)==CHECKPOINT_SHA,'Checkpoint hash mismatch')
    require((Path(root)/CHECKPOINT).stat().st_size==20301573,'Checkpoint size mismatch')
    require(not (Path(root)/OUTPUT).exists(),'Existing held-out output: STOP')

def bind_records(root, listing_bytes, table_bytes, *, expected_count=1053):
    """Resolve metadata only; do not open or decode any source image or label."""
    root=Path(root).resolve(); listing=root/LIST
    lines=listing_bytes.decode('utf-8-sig').splitlines()
    rows=list(csv.DictReader(io.StringIO(table_bytes.decode('utf-8-sig'))))
    require(len(rows)==len(lines)==expected_count,'Held-out membership count mismatch')
    image_root=root/'data/raw/gyu_det/v3/extracted/test/test/images'
    label_root=image_root.parent/'labels'
    by_image={}
    for row in rows:
        require(row['processed_split']==row['raw_split']=='test','Train/validation substitution prohibited')
        im=(root/row['image_relative_path']).resolve(); label=(root/row['label_relative_path']).resolve()
        require(im.parent==image_root and label.parent==label_root,'Source path escapes exact held-out directories')
        require(label.stem==im.stem and label.suffix=='.txt','Image-label association mismatch')
        require(im not in by_image,'Duplicate manifest image')
        require(int(row['annotation_count'])>0,'Invalid annotation count')
        ids=json.loads(row['class_ids']); require(all(type(c) is int and 0<=c<6 for c in ids),'Invalid class IDs')
        by_image[im]=dict(row,image=im,label=label,split='test')
    ordered=[]; seen=set()
    for line in lines:
        require(line.startswith('./') and '\\' not in line,'Nonportable/unapproved list entry')
        im=(listing.parent/line[2:]).resolve()
        require(im in by_image and im not in seen,'Duplicate or substituted list membership')
        seen.add(im); ordered.append(by_image[im])
    require(len({r['label'] for r in ordered})==expected_count,'Duplicate label membership')
    require(len({r['image_sha256'] for r in ordered})==expected_count,'Duplicate approved image content')
    return ordered

def load_test_metadata(root):
    listing=(Path(root)/LIST).read_bytes(); table=(Path(root)/TABLE).read_bytes()
    require(hashlib.sha256(listing).hexdigest()==LIST_SHA,'Held-out list hash mismatch')
    require(hashlib.sha256(table).hexdigest()==TABLE_SHA,'Held-out manifest hash mismatch')
    records=bind_records(root,listing,table)
    for r in records:
        for key in ('image','label'):
            p=r[key]; require(p.is_file(),'Approved source missing')
            # Refuse Windows junctions/reparse points as well as symlinks.
            for component in (p,*p.parents):
                if component==Path(root).resolve(): break
                require(not component.is_symlink() and not (getattr(component.lstat(),'st_file_attributes',0)&0x400),
                        'Aliased source path prohibited')
    return records

class AccessGuard:
    """Python defense in depth; native loader reads are exact-record bound."""
    def __init__(self,root,out,runtime):
        self.root=Path(root).resolve(); self.out=Path(out).resolve(); self.runtime=Path(runtime).resolve()
        self.started=False; self.allowed=set(); self.images=set(); self.opened_images=set()
        self.content_accessed=False; self.first_content_access_at=None
    def activate(self, records):
        require(read_json(self.out/'ONE_TIME_RECEIPT.json')['state']=='STARTED','Durable STARTED required')
        self.allowed={r[k].resolve() for r in records for k in ('image','label')}
        self.images={r['image'].resolve() for r in records}; self.started=True
    def may_write(self,p): return p.is_relative_to(self.out) or p.is_relative_to(self.runtime)
    def audit(self,event,args):
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(args[0])).resolve(); mode,flags=args[1:3]
            writing=bool(mode and any(c in mode for c in 'wax+')) or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            if writing and not self.may_write(p): raise PermissionError('Write outside dedicated output/runtime')
            if p.is_relative_to(self.root/'data/raw'):
                if writing or not self.started or p not in self.allowed: raise PermissionError('Unapproved raw access')
                self.content_accessed=True
                if self.first_content_access_at is None:self.first_content_access_at=now()
                if p in self.images:self.opened_images.add(p)
        elif event in ('os.remove','os.rmdir','os.mkdir','os.chmod','os.utime','os.truncate'):
            p=Path(args[0]).resolve()
            # mkdir of output's existing parent directories can occur through parents=True.
            if not self.may_write(p) and not (event=='os.mkdir' and self.out.is_relative_to(p) and p.exists()):
                raise PermissionError('Mutation outside dedicated output/runtime')
        elif event in ('os.rename','os.link'):
            if any(not self.may_write(Path(p).resolve()) for p in args[:2]):raise PermissionError('Mutation outside output/runtime')
        elif event=='socket.connect':raise PermissionError('Network prohibited during evaluator preparation/execution')
    def install(self):sys.addaudithook(self.audit)

def fixed_ap_function(metrics_module):
    """Preserve installed AP math exactly; replace only its operating-point argmax."""
    import inspect
    source=inspect.getsource(metrics_module.ap_per_class)
    selection='i = smooth(f1_curve.mean(0), 0.1).argmax()  # max F1 index'
    require(source.count(selection)==1,'Installed AP selector differs from inspected version')
    source=source.replace(selection,'i = 186  # Frozen validation diagnostic grid index; no test search')
    require('.argmax(' not in source,'Unexpected AP threshold optimization')
    namespace=dict(metrics_module.ap_per_class.__globals__)
    exec(compile(source,'<frozen-ap-fixed-index>','exec'),namespace)
    return namespace['ap_per_class'],source
