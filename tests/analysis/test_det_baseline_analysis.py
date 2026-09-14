"""Small synthetic checks of analysis matching, size boundaries, and paths."""
from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/analysis'))
from det_baseline_common import size_bin,check_output
from summarize_det_baseline import ious,match,summary_rows

def test_size_edges_match_m1():
    assert [size_bin(x) for x in [0,.00099,.001,.00999,.01,.09999,.1,1]]==['tiny','tiny','small','small','medium','medium','large','large']

def test_duplicate_and_wrong_class_cannot_inflate_recall():
    gt=np.array([[0,0,10,10],[20,20,30,30]])
    pred=np.array([[0,0,10,10],[0,0,10,10],[20,20,30,30]])
    pairs=match(ious(gt,pred),np.array([0,1]),np.array([0,0,0]))
    assert pairs==[(0,0)]

def test_overlap_assignment_uses_highest_iou():
    assert match(np.array([[.6,.9],[.8,.2]]),np.array([0,0]),np.array([0,0]))==[(0,1),(1,0)]

def test_no_predictions_and_boundary_iou():
    assert match(np.empty((1,0)),np.array([0]),np.array([]))==[]
    assert match(np.array([[.5]]),np.array([0]),np.array([0]))==[(0,0)]

def test_output_escape_into_frozen_or_raw_is_refused(tmp_path):
    for out in [tmp_path/'data/raw/a',tmp_path/'outputs/training/DET-BASELINE',tmp_path/'outputs/analysis/../../data/a']:
        with pytest.raises(ValueError):check_output(tmp_path,out)
    check_output(tmp_path,tmp_path/'outputs/analysis/DET-BASELINE')

def test_strata_are_weighted_by_instances():
    rows=[dict(size='tiny',detected=x,detected_at_floor=1) for x in [1,0,0]]
    r=summary_rows(rows,['size'])[0]
    assert (r['instances'],r['tp'],r['fn'],r['recall'])==(3,1,2,1/3)

def test_guard_blocks_dummy_holdout_reads_and_raw_writes(tmp_path):
    import subprocess
    root=tmp_path/'repo';out=tmp_path/'analysis';out.mkdir()
    valid=root/'data/raw/gyu_det/v3/extracted/valid/valid/a.txt'
    held=root/'data/raw/gyu_det/v3/extracted/test/test/a.txt'
    for f in (valid,held):f.parent.mkdir(parents=True,exist_ok=True);f.write_text('fixture')
    code='''
import sys
from pathlib import Path
from det_baseline_common import install_guard
root,out,valid,held=map(Path,sys.argv[1:])
install_guard(root,out)
assert valid.read_text()=='fixture'
for p,mode in ((valid,'w'),(held,'r')):
    try:
        p.open(mode)
    except PermissionError:
        pass
    else:
        raise AssertionError('guard failed')
(out/'evidence.txt').write_text('ok')
'''
    result=subprocess.run([sys.executable,'-B','-c',code,str(root),str(out),str(valid),str(held)],
                          cwd=Path(__file__).resolve().parents[2]/'scripts/analysis',capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert valid.read_text()=='fixture'
