"""Complete-inventory EDA using validated GYU-DET V3 artifacts; no raw writes."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / 'src'))
from data.validators.gyu_eda import run_eda


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = dict(manifest='data/manifests/gyu_det_v3_raw_manifest.csv',
        validation='outputs/validation/gyu_det_v3/full_validation',
        triage='outputs/validation/gyu_det_v3/orphan_review/final_triage_summary.csv',
        leakage='outputs/validation/gyu_det_v3/leakage_review/human_leakage_decisions.csv',
        policy='outputs/validation/gyu_det_v3/baseline_data_policy.md',
        classes_path='data/raw/gyu_det/v3/archives/classes.txt', output='outputs/eda/gyu_det_v3')
    for name, default in defaults.items():
        parser.add_argument('--'+name.replace('_', '-'), type=Path, default=Path(default))
    args = parser.parse_args()
    try:
        result = run_eda(REPOSITORY, **vars(args))
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f'EDA failed: {exc}\n')
    print(f"Analyzed {result['exact_pair_images']} exact pairs and {result['exact_pair_annotation_instances']} boxes.")
    print(f"Outputs: {args.output}; M1 remains incomplete.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
