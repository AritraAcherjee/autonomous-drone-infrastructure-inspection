"""Run identity, JSON serialization, runtime capture and raw access boundaries."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

from detection.data.raw_guard import inside, mutable_path, readonly_raw, sha256


def write_json(path: Path, value: object, root: Path) -> None:
    """Write strict, human-readable machine evidence outside raw."""
    path = mutable_path(path, root/'data/raw')
    path.parent.mkdir(parents=True, exist_ok=True)
    def convert(obj):
        if isinstance(obj, Path):
            return str(obj)
        if hasattr(obj, 'tolist'):
            return obj.tolist()
        raise TypeError(f'Not JSON serializable: {type(obj).__name__}')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False, default=convert)+'\n', encoding='utf-8')


def configure_runtime(root: Path) -> None:
    """Route library settings/caches before importing Ultralytics; disable integrations."""
    cache = mutable_path(root/'outputs/cache/detection_training', root/'data/raw')
    (cache/'settings/Ultralytics').mkdir(parents=True, exist_ok=True)
    os.environ.update(YOLO_CONFIG_DIR=str(cache/'settings'), MPLCONFIGDIR=str(cache/'matplotlib'),
                      YOLO_AUTOINSTALL='false', YOLO_OFFLINE='true', NO_ALBUMENTATIONS_UPDATE='1',
                      WANDB_MODE='disabled', COMET_MODE='DISABLED', PYTHONDONTWRITEBYTECODE='1')


def git_provenance(root: Path) -> dict:
    """Capture current checkout and the tracked/untracked change inventory."""
    def git(*args):
        return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    status = git('status', '--porcelain=v1')
    return dict(branch=git('branch', '--show-current'), sha=git('rev-parse', 'HEAD'),
                origin_main=git('rev-parse', 'origin/main'), dirty=bool(status), status=status,
                diff=git('diff', '--no-ext-diff'))


def capture(root: Path, config: dict) -> dict:
    """Record requested experiment identity, software, CUDA, cuDNN and driver/GPU details."""
    from detection.pretraining_gate import environment
    now = datetime.now(timezone.utc)
    return dict(run_id=config['experiment']['id'], utc=now.isoformat(), local=now.astimezone().isoformat(),
                git=git_provenance(root), environment=environment(), requested=config,
                source_sha256={p.relative_to(root).as_posix(): sha256(p)
                    for folder in ('src/detection/training', 'configs/detection')
                    for p in (root/folder).rglob('*') if p.is_file() and p.suffix in {'.py', '.yaml'}},
                cli_sha256=sha256(root/'scripts/train_detector.py'),
                packages={d.metadata['Name']: d.version for d in importlib.metadata.distributions()})


@contextmanager
def development_access(root: Path):
    """Keep raw read-only and deny all raw content reads outside train/valid.

    Python audit hooks are defense in depth; native writes additionally require
    the inspected loader and before/after raw inventory verification.
    """
    raw = root/'data/raw'
    allowed = [raw/'gyu_det/v3/extracted'/split/split for split in ('train', 'valid')]
    active = [True]
    def audit(event, args):
        if active[0] and event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0]))
            if inside(path, raw) and not any(inside(path, p) for p in allowed):
                raise PermissionError(f'Development run cannot access this raw split/source: {path}')
    sys.addaudithook(audit)
    try:
        with readonly_raw(raw):
            yield
    finally:
        active[0] = False
