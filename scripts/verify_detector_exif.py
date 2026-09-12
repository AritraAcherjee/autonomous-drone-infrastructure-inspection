"""Verify the approved development split's EXIF geometry without training."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

if __name__ == '__main__':
    from detection.training.exif import run
    result = run(ROOT)
    print(f'EXIF TRAINING GEOMETRY = {result["status"]}')
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
