"""Full read-only GYU-DET V3 validation and raw image manifest CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / 'src'))
from data.validators.gyu_full_validation import validate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = dict(root='data/raw/gyu_det/v3/extracted',audit='outputs/validation/gyu_det_v3',
        classes='data/raw/gyu_det/v3/archives/classes.txt',output='outputs/validation/gyu_det_v3/full_validation',
        manifest='data/manifests/gyu_det_v3_raw_manifest.csv')
    for name, default in defaults.items():
        parser.add_argument('--'+name,type=Path,default=Path(default))
    parser.add_argument('--workers',type=int,default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    try:
        data = validate_dataset(args.root,args.audit,args.classes,args.output,args.manifest,REPOSITORY,args.workers,
                                progress=lambda message: print(message,flush=True))
    except (OSError,ValueError,RuntimeError,KeyError) as exc:
        parser.exit(2,f'Validation could not complete: {exc}\n')
    print(data['summary'],flush=True)
    s = data['summary']
    return 1 if s['corrupted_unreadable_images'] or s['invalid_label_files'] or s['inventory_discrepancies'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
