"""Finalize the human-approved baseline-v1 specification; never copy raw samples."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY/'src'))
from data.validators.gyu_baseline_v1 import finalize


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-reproducibility', action='store_true', help='Compare two clean temporary output trees without changing repository outputs')
    args = parser.parse_args()
    try:
        result = finalize(REPOSITORY, args.check_reproducibility)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'Finalization failed: {exc}\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
