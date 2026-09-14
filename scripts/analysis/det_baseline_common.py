"""Read-only DET-BASELINE analysis helpers; no training entry point."""
from __future__ import annotations
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

CLASSES = ['Crack', 'Breakage', 'Honeycombing', 'Hole', 'Exposed Reinforcement', 'Seepage']
EXPECTED = {'best.pt': '4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3',
            'last.pt': '7cb24d3d7397b045330fbf24f2aa54949cfc055c4931cc45ef4eb2302dff1982'}
COMMIT = '8ee410771c8be794d366e5e014f14f748edca97f'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False,
                              default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x))+'\n', encoding='utf-8')

def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def size_bin(area):
    return 'tiny' if area < .001 else 'small' if area < .01 else 'medium' if area < .1 else 'large'

def within(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False

def check_output(root, out):
    if within(out, root/'data') or within(out, root/'outputs/training'):
        raise ValueError('Analysis output must be outside data and frozen training outputs')

def install_guard(root, out):
    """Restrict Python opens to development raw reads and analysis-only writes.

    Native decoder reads are supplied only manifest-approved paths. This is
    defense in depth, not a substitute for OS permissions or integrity checks.
    """
    check_output(root, out)
    allowed = [root/'data/raw/gyu_det/v3/extracted'/s/s for s in ('train', 'valid')]
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            p, mode, flags = Path(os.fsdecode(args[0])), args[1], args[2]
            write = bool(mode and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            if write and not within(p, out):
                raise PermissionError(f'Analysis write outside output: {p}')
            if within(p, root/'data/raw') and not any(within(p, a) for a in allowed):
                raise PermissionError(f'Unapproved raw read: {p}')
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime', 'os.truncate'):
            if not within(Path(args[0]), out):
                raise PermissionError(f'Analysis mutation outside output: {args[0]}')
        elif event in ('os.rename', 'os.link'):
            if any(not within(Path(p), out) for p in args[:2]):
                raise PermissionError('Analysis rename/link outside output')
        elif event == 'socket.connect':
            raise PermissionError('Analysis must remain offline')
    sys.addaudithook(audit)

def inventory(tree):
    return {p.relative_to(tree).as_posix(): dict(size=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns, sha256=sha(p))
            for p in sorted(tree.rglob('*')) if p.is_file()}
