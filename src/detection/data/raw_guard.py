"""Resolved-path output guards and before/after raw inventories."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from contextlib import contextmanager
import sys


def canonical(path: Path) -> str:
    # resolve follows existing symlinks/junctions and normalizes .. even when the
    # final output does not yet exist. normcase applies Windows case semantics.
    return os.path.normcase(str(Path(path).resolve()))


def inside(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath([canonical(path), canonical(parent)]) == canonical(parent)
    except ValueError:  # Different Windows drives.
        return False


def mutable_path(path: Path, raw: Path) -> Path:
    if inside(path, raw):
        raise ValueError(f'Mutable path resolves inside immutable raw data: {path}')
    return Path(path).resolve()


@contextmanager
def readonly_raw(raw: Path):
    """Reject Python-audited raw writes as defense in depth, not an OS sandbox.

    Native libraries do not necessarily emit audit events. Therefore the gate
    uses only the inspected decoder and read-only parser and verifies hashes.
    """
    active = [True]

    def audit(event, args):
        if not active[0]:
            return
        paths = []
        if event == 'open':
            path, mode, flags = args
            if (mode and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                paths = [path]
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime', 'os.truncate'):
            paths = [args[0]]
        elif event in ('os.rename', 'os.link'):
            paths = args[:2]
        elif event == 'os.symlink':
            paths = [args[1]]
        for path in paths:
            if isinstance(path, (str, bytes, os.PathLike)):
                mutable_path(Path(os.fsdecode(path)), raw)

    sys.addaudithook(audit)
    try:
        yield
    finally:
        active[0] = False


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def snapshot(raw: Path, baseline: set[Path]) -> dict:
    """Stat every raw file; hash baseline images and labels, never archives."""
    wanted = {canonical(p) for p in baseline}
    result = {}
    for path in sorted(raw.rglob('*')):
        if path.is_file():
            stat = path.stat()
            record = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
            if canonical(path) in wanted:
                record['sha256'] = sha256(path)
            result[path.relative_to(raw).as_posix()] = record
    return result


def compare(before: dict, after: dict) -> dict:
    added, removed = sorted(after.keys() - before.keys()), sorted(before.keys() - after.keys())
    result = {'files_added': added, 'files_removed': removed}
    for field in ('size', 'mtime_ns', 'sha256'):
        result[field + '_changes'] = [p for p in sorted(before.keys() & after.keys())
                                      if before[p].get(field) != after[p].get(field)]
    result['new_cache_files'] = [p for p in added if p.lower().endswith('.cache')]
    result['new_npy_files'] = [p for p in added if p.lower().endswith('.npy')]
    result['status'] = 'FAIL' if any(result.values()) else 'PASS'
    return result
