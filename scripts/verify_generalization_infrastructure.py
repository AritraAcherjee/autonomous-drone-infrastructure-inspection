"""Run synthetic/generalization and safe regressions with a no-payload audit hook."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    out = ROOT / 'outputs/validation/defect_detection/generalization_infrastructure'
    out.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(ROOT / 'outputs/cache/generalization/matplotlib')
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    sys.dont_write_bytecode = True
    reads, denied = set(), []
    raw = (ROOT / 'data/raw').resolve()

    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path == raw or raw in path.parents:
                denied.append(str(path))
                raise RuntimeError('Real raw payload access prohibited during infrastructure tests')
            mode = args[1]
            if isinstance(mode, str) and 'r' in mode and ROOT in path.parents:
                relative = path.relative_to(ROOT).as_posix()
                if not relative.startswith(('outputs/cache/', '.git/')):
                    reads.add(relative)
        if event == 'socket.connect':
            denied.append('network connection')
            raise RuntimeError('Network prohibited during infrastructure tests')
        if event == 'import' and args[0].split('.')[0] in ('torch', 'ultralytics'):
            denied.append('detector import: ' + args[0])
            raise RuntimeError('Detector runtime prohibited during infrastructure tests')

    sys.addaudithook(audit)
    import pytest
    os.chdir(ROOT)
    argv = ['tests/detection', 'tests/data/test_gyu_m1_documentation.py',
            '-q', '-p', 'no:cacheprovider', '--junitxml=' + str(out / 'pytest_results.xml')]
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
        code = pytest.main(argv)
    (out / 'tests.log').write_text(capture.getvalue(), encoding='utf-8')
    (out / 'access_audit.json').write_text(json.dumps(dict(
        test_arguments=argv, returncode=int(code), repository_reads=sorted(reads), denied_attempts=denied,
        raw_payload_reads=0, network_connections=0, detector_runtime_imports=0,
        scope='This test process; excludes earlier shell inspection and environment installation'), indent=2) + '\n', encoding='utf-8')
    print(capture.getvalue())
    return int(code) or bool(denied)


if __name__ == '__main__':
    raise SystemExit(main())
