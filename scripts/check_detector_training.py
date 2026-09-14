"""Run detector tests first, then unchanged required M1/full repository suites."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('before', 'after'), required=True)
    args = parser.parse_args()
    from detection.data.raw_guard import sha256
    from detection.training.provenance import configure_runtime, write_json
    from detection.training.trainer import implementation_identity
    from detection.test_evidence import generate
    configure_runtime(ROOT)
    out = ROOT/'outputs/validation/defect_detection/training_pipeline'/args.stage
    out.mkdir(parents=True, exist_ok=True)
    write_json(out/'ready.json', {'status': 'FAIL'}, ROOT)
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(str(ROOT/p) for p in ('src', 'ros2_ws/src/aegisinspect_mapping'))
    command = [sys.executable, '-B', '-m', 'pytest', 'tests/detection', '-q', '-p', 'no:cacheprovider', '--junitxml='+str(out/'detector.xml')]
    print('Running:', subprocess.list2cmdline(command), flush=True)
    process = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (out/'detector_tests.txt').write_text(process.stdout+process.stderr, encoding='utf-8')
    print(process.stdout+process.stderr, flush=True)
    if process.returncode:
        raise SystemExit(process.returncode)
    print('Running required M1 and full Python suite...', flush=True)
    result = generate(ROOT, out)
    record = dict(status=result['status'], implementation=implementation_identity(ROOT),
                  detector_command=command, required_tests=result,
                  evidence_sha256={p.relative_to(ROOT).as_posix(): sha256(p) for p in out.iterdir()
                                   if p.name != 'ready.json' and p.is_file()})
    write_json(out/'ready.json', record, ROOT)
    print(json.dumps({k: v for k, v in result.items() if k in ('status', 'm1', 'detector', 'full_python_suite')}, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
