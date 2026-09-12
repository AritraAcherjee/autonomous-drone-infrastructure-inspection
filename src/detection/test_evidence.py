"""Fresh subprocess evidence; no model construction or dataset writes."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

from detection.data.raw_guard import mutable_path, sha256


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def counts(cases):
    if not cases:
        raise ValueError('No test cases in fresh JUnit evidence')
    failed = sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
    skipped = sum(c.find('skipped') is not None for c in cases)
    return dict(passed=len(cases)-failed-skipped, failed=failed, skipped=skipped)


def generate(root: Path, out: Path, timeout=1800) -> dict:
    """Always execute both suites, using a new XML path unavailable to old runs."""
    raw = root / 'data/raw'
    out = mutable_path(out, raw)
    result = dict(status='FAIL', run_id=uuid.uuid4().hex, started_at=timestamp(), commands=[])
    try:
        out.mkdir(parents=True, exist_ok=True)
        # Invalidate any previous PASS before launching commands. An interrupted
        # run must leave an incomplete FAIL, not apparently current success.
        mutable_path(out / 'test_results.json', raw).write_text(json.dumps(result) + '\n', encoding='utf-8')
        for name in ('m1_tests.txt', 'full_tests.txt', 'pytest_results.xml'):
            mutable_path(out / name, raw).unlink(missing_ok=True)
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True,
                              text=True, check=True, timeout=30).stdout.strip()
        if not re.fullmatch(r'[0-9a-f]{40}', head):
            raise ValueError('Cannot determine current Git SHA')
        result['git_sha'] = head
        env = os.environ.copy()
        env.update(PYTHONPATH=os.pathsep.join(str(root / p) for p in ('src', 'ros2_ws/src/aegisinspect_mapping')),
                   PYTHONDONTWRITEBYTECODE='1', YOLO_AUTOINSTALL='false', YOLO_OFFLINE='true')
        result['PYTHONPATH'] = env['PYTHONPATH'].split(os.pathsep)
        with tempfile.TemporaryDirectory(prefix='test-run-', dir=out) as folder:
            xml = Path(folder) / 'pytest_results.xml'
            commands = [
                ('m1', 'm1_tests.txt', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/data', '-v']),
                ('full_python_suite', 'full_tests.txt', [sys.executable, '-m', 'pytest', 'tests',
                 'ros2_ws/src/aegisinspect_mapping/test', 'ros2_ws/src/aegisinspect_system_tests/test',
                 '-q', '-p', 'no:cacheprovider', '--junitxml=' + str(xml)]),
            ]
            for name, log, argv in commands:
                record = dict(suite=name, command=argv, cwd=str(root), started_at=timestamp(), returncode=None)
                result['commands'].append(record)
                try:
                    process = subprocess.run(argv, cwd=root, env=env, capture_output=True,
                                             text=True, encoding='utf-8', errors='replace', timeout=timeout)
                    record['returncode'] = process.returncode
                    output = process.stdout + process.stderr
                except (OSError, subprocess.TimeoutExpired) as exc:
                    record['error'] = f'{type(exc).__name__}: {exc}'
                    output = record['error']
                record['finished_at'] = timestamp()
                path = mutable_path(out / log, raw)
                path.write_text(output, encoding='utf-8')
                # Parse the written evidence, not an old file or retained count.
                output = path.read_text(encoding='utf-8')
                if name == 'm1':
                    match = re.search(r'^Ran (\d+) tests? in ', output, re.M)
                    summary = re.search(r'^(OK(?: \([^\n]*\))?|FAILED \([^\n]*\))\s*$', output, re.M)
                    if not match or not summary or int(match[1]) < 112:
                        record['error'] = 'Missing, malformed or incomplete M1 test summary'
                    else:
                        failures = sum(int(n) for n in re.findall(r'(?:failures|errors)=(\d+)', summary[1]))
                        skipped = re.search(r'skipped=(\d+)', summary[1])
                        skipped = int(skipped[1]) if skipped else 0
                        result['m1'] = dict(passed=int(match[1])-failures-skipped, failed=failures, skipped=skipped)
                        if not summary[1].startswith('OK'):
                            record['error'] = 'M1 summary reports failure'
            # This path was created in this invocation; an absent file is fatal.
            tree = ET.parse(xml)
            cases = tree.findall('.//testcase')
            result['full_python_suite'] = counts(cases)
            result['detector'] = counts([c for c in cases if 'detection.' in c.get('classname', '')])
            declared = sum(int(s.get('tests', '-1')) for s in tree.iter('testsuite'))
            # Pytest 9 counts successful unittest subtests in the suite total,
            # without emitting separate testcase elements for those successes.
            subtests = re.search(r'\b(\d+) subtests passed\b', output)
            subtests = int(subtests[1]) if subtests else 0
            result['full_python_suite']['subtests_passed'] = subtests
            if declared != len(cases) + subtests:
                raise ValueError('JUnit declared test count differs from recorded cases')
            mutable_path(out / 'pytest_results.xml', raw).write_bytes(xml.read_bytes())
            result['artifacts'] = {name: sha256(out / name) for name in ('m1_tests.txt', 'full_tests.txt', 'pytest_results.xml')}
            suites = [result.get(k, {}) for k in ('m1', 'detector', 'full_python_suite')]
            if (all(c['returncode'] == 0 and not c.get('error') for c in result['commands'])
                    and all(s.get('passed', 0) > 0 and s.get('failed') == 0 and s.get('skipped') == 0 for s in suites)):
                result['status'] = 'PASS'
    except Exception as exc:
        result.update(status='FAIL', reason=f'{type(exc).__name__}: {exc}')
    result['finished_at'] = timestamp()
    try:
        path = mutable_path(out / 'test_results.json', raw)
        path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        if json.loads(path.read_text(encoding='utf-8')) != result:
            raise ValueError('Test evidence readback differs')
    except Exception as exc:
        result.update(status='FAIL', reason=f'Cannot publish fresh test evidence: {exc}')
    return result


def validate(out: Path, expected: dict | None, git_sha: str | None) -> dict:
    """Require the exact in-memory result from this invocation and intact files."""
    try:
        if not expected or expected.get('status') != 'PASS':
            raise ValueError('Fresh successful execution is required')
        evidence = json.loads((out / 'test_results.json').read_text(encoding='utf-8'))
        if evidence != expected or not evidence.get('run_id') or evidence.get('git_sha') != git_sha:
            raise ValueError('Test evidence does not match this invocation/Git SHA')
        for name in ('m1_tests.txt', 'full_tests.txt', 'pytest_results.xml'):
            if sha256(out / name) != evidence['artifacts'][name]:
                raise ValueError(f'Fresh evidence changed: {name}')
        return evidence
    except Exception as exc:
        return dict(status='FAIL', reason=str(exc), execution=expected)
