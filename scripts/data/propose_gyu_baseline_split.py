"""Generate a dry-run baseline split proposal; never materialize data."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY/'src'))
from data.validators.gyu_baseline_split import run_proposal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        result = run_proposal(REPOSITORY)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f'Dry-run proposal failed: {exc}\n')
    print(json.dumps({k: result[k] for k in ('status', 'baseline_eligible_before_handling',
        'equivalent_duplicate_groups', 'conflicting_duplicate_groups', 'proposed_images_by_split',
        'excluded_by_reason', 'assertions')}, indent=2))
    print('Manifest proposal only; no samples materialized. M1 remains incomplete.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
