"""Synthetic-only checks; never read a real held-out image or label."""
import csv
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
import pytest
import heldout_contract as c

def payload():
    return dict(state='STARTED',started_at='SYNTHETIC',test_accessed=True,retry_allowed=False)

def metadata(root,count=2):
    rows=[];lines=[]
    for i in range(count):
        rel=f'data/raw/gyu_det/v3/extracted/test/test/images/{i}.jpg'
        rows.append(dict(processed_split='test',raw_split='test',image_relative_path=rel,
            label_relative_path=rel.replace('/images/','/labels/').replace('.jpg','.txt'),
            image_sha256=str(i)*64,annotation_count='1',class_ids='[0]'))
        lines.append('./../../../'+rel.removeprefix('data/'))
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return ('\n'.join(lines)+'\n').encode(),stream.getvalue().encode(),rows

def test_exclusive_receipt_never_overwrites_any_existing_state(tmp_path):
    for state in ('STARTED','COMPLETED','FAILED'):
        out=tmp_path/state;c.start_receipt(out,payload())
        if state!='STARTED':c.finish_receipt(out,payload(),state,images_processed=0)
        before=(out/'ONE_TIME_RECEIPT.json').read_bytes()
        with pytest.raises(ValueError):c.start_receipt(out,payload())
        assert (out/'ONE_TIME_RECEIPT.json').read_bytes()==before

def test_failure_receipt_preserves_start_and_disallows_retry(tmp_path):
    out=tmp_path/'run';c.start_receipt(out,payload())
    final=c.finish_receipt(out,payload(),'FAILED',error='synthetic failure',images_processed=2,model_inference_began=True)
    assert final['started_at']=='SYNTHETIC' and final['test_accessed'] is True and final['retry_allowed'] is False
    assert c.read_json(out/'STARTED_RECEIPT.json')['state']=='STARTED'
    with pytest.raises(ValueError):c.finish_receipt(out,payload(),'COMPLETED')

def test_membership_is_exact_and_ordered_without_content_reads(tmp_path):
    listing,table,rows=metadata(tmp_path)
    bound=c.bind_records(tmp_path,listing,table,expected_count=2)
    assert [r['image'].name for r in bound]==['0.jpg','1.jpg']
    assert not bound[0]['image'].exists()
    with pytest.raises(ValueError):c.bind_records(tmp_path,listing,table,expected_count=1053)

@pytest.mark.parametrize('change',['train','escape','duplicate','label','class'])
def test_membership_substitution_rejected(tmp_path,change):
    listing,table,rows=metadata(tmp_path)
    if change=='train':rows[0]['processed_split']='train'
    elif change=='escape':rows[0]['image_relative_path']='data/raw/codebrim/a.jpg'
    elif change=='duplicate':rows[1]=deepcopy(rows[0])
    elif change=='label':rows[0]['label_relative_path']=rows[1]['label_relative_path']
    else:rows[0]['class_ids']='[6]'
    stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with pytest.raises(ValueError):c.bind_records(tmp_path,listing,stream.getvalue().encode(),expected_count=2)

def test_guard_refuses_prestart_raw_and_nonmember_sources(tmp_path):
    script=r'''
from pathlib import Path
import sys
import heldout_contract as c
root=Path(sys.argv[1]);out=root/'out';runtime=root/'runtime';runtime.mkdir()
image=root/'data/raw/gyu_det/v3/extracted/test/test/images/a.jpg'
label=image.parent.parent/'labels/a.txt'
other=root/'data/raw/codebrim/other.jpg'
for p in (image,label,other):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'synthetic')
g=c.AccessGuard(root,out,runtime);g.install()
try:image.read_bytes()
except PermissionError:pass
else:raise AssertionError('prestart read allowed')
c.start_receipt(out,dict(state='STARTED',started_at='SYNTHETIC',test_accessed=True,retry_allowed=False))
g.activate([dict(image=image,label=label)])
assert image.read_bytes()==b'synthetic'
for p,mode in ((image,'wb'),(other,'rb'),(root/'escape.json','wb')):
    try:p.open(mode)
    except PermissionError:pass
    else:raise AssertionError('guard failed')
assert g.content_accessed and len(g.opened_images)==1
'''
    result=subprocess.run([sys.executable,'-B','-c',script,str(tmp_path)],cwd=Path(__file__).parent,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr

def test_fixed_selector_preserves_ap_without_calling_argmax():
    import numpy as np
    import ultralytics.utils.metrics as metrics
    tp=np.array([[1]*10,[0]*10,[1]*10],dtype=bool)
    conf=np.array([.8,.5,.2]);pred=np.array([0,0,1]);target=np.array([0,1])
    original=metrics.ap_per_class(tp,conf,pred,target,plot=False)
    fixed,source=c.fixed_ap_function(metrics)
    assert '.argmax(' not in source
    with patch.object(metrics,'smooth',side_effect=AssertionError('threshold search')):
        actual=fixed(tp,conf,pred,target,plot=False)
    np.testing.assert_array_equal(actual[5],original[5])
    np.testing.assert_array_equal(actual[2],actual[7][:,186])
    np.testing.assert_array_equal(actual[3],actual[8][:,186])

def test_durable_json_failure_does_not_destroy_existing_receipt(tmp_path):
    out=tmp_path/'run';c.start_receipt(out,payload())
    original=(out/'ONE_TIME_RECEIPT.json').read_bytes()
    with pytest.raises(ValueError):c.durable_write(out/'ONE_TIME_RECEIPT.json',{'bad':float('nan')})
    assert (out/'ONE_TIME_RECEIPT.json').read_bytes()==original
