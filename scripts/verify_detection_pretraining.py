"""Run the approved GYU-DET read-only gate; never download weights or train."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from detection.pretraining_gate import run

if __name__ == '__main__':
    result = run(ROOT)
    print(json.dumps({k: v for k, v in result.items() if k != 'environment'}, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
