"""Write deterministic normalized DamSegment GT; never performs inference."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from detection.generalization.damsegment_prepare import (
    prepared_bytes,
)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--root',
        required=True,
        help='Extracted DamSegment Damage Detection root',
    )

    parser.add_argument(
        '--output',
        required=True,
        help='New derived normalized JSON path',
    )

    args = parser.parse_args()

    output = Path(args.output)

    if output.exists():
        raise SystemExit(
            'Refusing to overwrite prepared inventory'
        )

    payload, stats = prepared_bytes(args.root)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_bytes(payload)

    print(
        'PREPARED_IMAGE_COUNT=',
        stats['image_count'],
    )

    print(
        'PREPARED_REGION_COUNT=',
        stats['region_count'],
    )

    print(
        'PREPARED_CLASS_COUNTS=',
        stats['class_counts'],
    )

    print(
        'PREPARED_EMPTY_IMAGE_COUNT=',
        stats['empty_image_count'],
    )

    print(
        'PREPARED_INVENTORY_SHA256=',
        stats['object_sha256'],
    )

    print('PREPARED_OUTPUT=', output)
    print('MODEL_INFERENCE_EXECUTED=FALSE')


if __name__ == '__main__':
    main()
