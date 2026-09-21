"""Run identity, JSON serialization, runtime capture and raw access boundaries."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import filecmp
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

from detection.data.raw_guard import inside, mutable_path, readonly_raw, sha256


OFFLINE_ARIAL_SOURCE = Path('/home/aritra/.config/Ultralytics/Arial.ttf')
APPROVED_OFFLINE_ARIAL_SHA256 = '525979822591a3447cfc49d943d6f7683508e25543407871c0ed8fed05fd2bd9'


def runtime_ultralytics_dir(root: Path) -> Path:
    """Return the only Ultralytics configuration directory permitted for a guarded run."""
    cache = mutable_path(root/'outputs/cache/detection_training', root/'data/raw')
    return cache/'settings'/'Ultralytics'


def _sha256_regular_file(path: Path) -> str:
    """Hash one already-validated regular file without following a symlink at the entry path."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_offline_arial_font(
    root: Path,
    *,
    source: Path = OFFLINE_ARIAL_SOURCE,
    approved_sha256: str = APPROVED_OFFLINE_ARIAL_SHA256,
) -> dict:
    """Stage the frozen local Arial font before Ultralytics can request an auxiliary download.

    The source is never distributed or recorded as bytes. Both source and destination
    fail closed on symlinks, non-regular files, hash drift, or byte inequality.
    """
    source = Path(source)
    if source.name != 'Arial.ttf' or source.is_symlink() or not source.exists():
        raise ValueError('approved offline Arial source must be an existing non-symlink Arial.ttf')
    source_stat = source.stat()
    if not stat.S_ISREG(source_stat.st_mode) or not os.access(source, os.R_OK):
        raise ValueError('approved offline Arial source must be a readable regular file')
    source_sha256 = _sha256_regular_file(source)
    if source_sha256 != approved_sha256:
        raise ValueError('approved offline Arial source SHA-256 mismatch')

    destination = runtime_ultralytics_dir(root)/'Arial.ttf'
    destination.parent.mkdir(parents=True, exist_ok=True)
    already_staged = destination.exists()
    if already_staged:
        if destination.is_symlink():
            raise ValueError('offline Arial destination must not be a symlink')
        destination_stat = destination.stat()
        if not stat.S_ISREG(destination_stat.st_mode):
            raise ValueError('offline Arial destination must be a regular file')
        if _sha256_regular_file(destination) != approved_sha256:
            raise ValueError('existing offline Arial destination SHA-256 mismatch')
    else:
        shutil.copyfile(source, destination)

    if destination.is_symlink() or not destination.is_file():
        raise ValueError('staged offline Arial destination must be a non-symlink regular file')
    destination_sha256 = _sha256_regular_file(destination)
    if destination_sha256 != approved_sha256:
        raise ValueError('staged offline Arial destination SHA-256 mismatch')
    if not filecmp.cmp(source, destination, shallow=False):
        raise ValueError('offline Arial source/destination bytes differ')
    return dict(
        source_path=str(source), source_size=source_stat.st_size, source_sha256=source_sha256,
        destination_path=str(destination), destination_size=destination.stat().st_size,
        destination_sha256=destination_sha256, already_staged=already_staged,
        source_destination_byte_equal=True,
    )


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
    cache = runtime_ultralytics_dir(root).parents[1]
    runtime_ultralytics_dir(root).mkdir(parents=True, exist_ok=True)
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
