"""Thin CLI for the approved baseline or explicit smoke configuration."""
import argparse
import json
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--download-pretrained', action='store_true', help='Acquire official yolo26s only after all gates pass')
    parser.add_argument('--check', action='store_true', help='Check configuration/data/gates without acquisition or training')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        from detection.training.trainer import run
        result = run(ROOT, ROOT/args.config, acquire=args.download_pretrained, check_only=args.check)
        print(json.dumps({k: v for k, v in result.items() if k != 'loss_history'}, indent=2))
        return 0 if result['status'] in ('PASS', 'READY') else 1
    except Exception:
        logging.exception('Detector training stopped')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
