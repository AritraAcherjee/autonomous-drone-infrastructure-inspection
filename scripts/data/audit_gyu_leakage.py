"""Audit GYU-DET duplication and cross-split similarity without changing raw data."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPOSITORY=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPOSITORY/'src'))
from data.validators.gyu_leakage import run_audit


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    for name,default in dict(manifest='data/manifests/gyu_det_v3_raw_manifest.csv',
        validation='outputs/validation/gyu_det_v3/full_validation',output='outputs/validation/gyu_det_v3/leakage_audit',
        review='outputs/validation/gyu_det_v3/leakage_review').items():
        parser.add_argument('--'+name,type=Path,default=Path(default))
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args()
    if args.workers<1: parser.error('workers must be positive')
    try:
        result=run_audit(REPOSITORY,args.manifest,args.validation,args.output,args.review,args.workers,
                         lambda message:print(message,flush=True))
    except (OSError,ValueError,RuntimeError) as exc:
        parser.exit(2,f'Audit failed: {exc}\n')
    print(result['summary'])
    return 1 if result['summary']['fingerprint_failures'] or result['summary']['rendering_failures'] else 0


if __name__=='__main__': raise SystemExit(main())
