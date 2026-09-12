"""Read-only checks; never regenerate approved baseline artifacts."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from data.validators.gyu_m1_documentation import check_approved, check_documentation

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-only', action='store_true')
    args = parser.parse_args()
    try:
        result = check_approved(ROOT)
        if not args.approved_only:
            check_documentation(ROOT)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'Consistency failure: {exc}\n')
    print(json.dumps(result, indent=2))
