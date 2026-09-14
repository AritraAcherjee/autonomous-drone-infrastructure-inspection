"""Verify pre-access metadata/runtime and synthetic regressions; never run a detector."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'outputs/validation/defect_detection/generalization_infrastructure/codebrim_preaccess'


def write(name, value):
    (OUT/name).write_bytes((json.dumps(value, indent=2, allow_nan=False)+'\n').encode())


def guard(event, args):
    if event == 'socket.connect':
        raise PermissionError('Pre-access verification forbids network access')
    if event not in ('open','os.listdir','os.scandir') or not args or not isinstance(args[0], (str,bytes,os.PathLike)):
        return
    path = Path(os.fsdecode(args[0])).absolute()
    try:
        relative = path.relative_to(ROOT).as_posix().lower()
    except ValueError:
        return  # Synthetic fixtures in temporary directories are permitted.
    if (relative == 'data/raw' or relative.startswith('data/raw/')
            or relative.startswith('outputs/evaluation/defect_detection/det-final-v1/gyu-det-test')
            or relative in ('data/manifests/gyu_det_v3_baseline_v1/test.csv',
                            'data/processed/gyu_det_v3_baseline_v1/splits/test.txt')):
        raise PermissionError('Scientific payload access prohibited: '+relative)


def main():
    assert platform.python_version() == '3.12.14'
    assert os.path.samefile(sys.executable, ROOT/'outputs/cache/generalization/venv/Scripts/python.exe')
    sys.dont_write_bytecode = True
    OUT.mkdir(parents=True, exist_ok=True)
    runtime = ROOT/'outputs/cache/generalization/preaccess-runtime'
    (runtime/'settings/Ultralytics').mkdir(parents=True,exist_ok=True)
    os.environ.update(YOLO_CONFIG_DIR=str(runtime/'settings'), MPLCONFIGDIR=str(runtime/'matplotlib'),
        YOLO_OFFLINE='true', YOLO_AUTOINSTALL='false', NO_ALBUMENTATIONS_UPDATE='1',
        WANDB_MODE='disabled', COMET_MODE='DISABLED', PYTHONDONTWRITEBYTECODE='1')
    sys.addaudithook(guard)
    import ultralytics
    import torch
    assert ultralytics.__version__ == '8.4.145'
    assert torch.__version__ == '2.14.0+cu130'
    packages = {d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name']}
    before = {}
    for line in (ROOT/'requirements/generalization-test.txt').read_text().splitlines():
        if '==' in line and not line.startswith('#'):
            k,v = line.split('==')
            before[k] = v
    before['pip'] = '25.0.1'
    normalize = lambda name: name.lower().replace('_','-')
    old = {normalize(k):v for k,v in before.items()}
    current = {normalize(k):v for k,v in packages.items()}
    changes = {k:dict(before=old.get(k),after=v) for k,v in current.items() if old.get(k)!=v}
    assert {k for k in old if current[k] != old[k]} == {'numpy'}
    check = subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True)
    write('environment.json', dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),
        before=dict(python='3.12.14',packages=before,source='Initial pip list captured in pre-access task; matches generalization-test.txt plus pip 25.0.1'),
        after=dict(python=platform.python_version(),executable=sys.executable,platform=platform.platform(),packages=packages,
                   torch=torch.__version__,cuda_available=torch.cuda.is_available(),cuda_runtime=torch.version.cuda),
        installed_or_changed=changes, pip_check=dict(returncode=check.returncode,stdout=check.stdout,stderr=check.stderr),
        venv_recreated=False, inference_executed=False,
        evidence_sources=['requirements/detection.txt','requirements/generalization-test.txt',
            'outputs/validation/defect_detection/pretraining_gate/installed_packages.txt',
            'outputs/training/defect_detection/DET-BASELINE/provenance.json'],
        repair_notes=['Initial install failed with WinError 206 inside setuptools.',
            'Retried with verified Windows short-path alias of the same physical interpreter.',
            'Kept existing contourpy 1.4.0 and pip 25.0.1; NumPy changed to frozen detector 2.4.6.',
            'All added versions constrained to 02 evidence; no unrelated package upgrades.']))
    assert check.returncode == 0, check.stdout+check.stderr
    assert torch.cuda.is_available(), 'Frozen CUDA:0 runtime unavailable'
    import pytest
    args = ['tests/detection', 'tests/analysis', 'tests/evaluation', 'tests/data/test_dataset_registry.py',
        '-k','not test_gyu_approved_entry_and_artifacts_unchanged and not test_no_raw_inventory_modifications '
             'and not test_approved_yaml_lists_counts_and_mapping and not test_no_false_acquisition_claim',
        '-q', '-p','no:cacheprovider','--junitxml='+str(OUT/'pytest_results.xml')]
    capture = io.StringIO()
    with redirect_stdout(capture), redirect_stderr(capture):
        code = int(pytest.main(args))
    (OUT/'tests.txt').write_text(capture.getvalue(),encoding='utf-8')
    write('test_results.json',dict(exit_code=code,pytest_arguments=args,
        scope='Synthetic detector/generalization/analysis/evaluation tests plus metadata-only registry checks',
        exclusions={'test_gyu_approved_entry_and_artifacts_unchanged':'Hashes protected artifacts that can include held-out manifests',
                    'test_no_raw_inventory_modifications':'Would enumerate raw scientific payload',
                    'test_approved_yaml_lists_counts_and_mapping':'Initial run blocked before reading held-out manifest; requires prohibited payload identity access',
                    'test_no_false_acquisition_claim':'Initial run failed: expected local GYU raw-data directory absent; no fake directory created'},
        scientific_payload_guard=True, scientific_inference_executed=False))
    print(capture.getvalue())
    return code


if __name__ == '__main__':
    raise SystemExit(main())
