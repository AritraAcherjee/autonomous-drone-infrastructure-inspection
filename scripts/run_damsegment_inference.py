"""Run frozen DET-FINAL-v1 DamSegment inference/export; never computes metrics."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from detection.generalization.damsegment_runtime import (
    run_inference,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--manifest", required=True)
    parser.add_argument("--prepared", required=True)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--outer-archive", required=True)
    parser.add_argument("--detection-archive", required=True)
    parser.add_argument("--ontology", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    result = run_inference(
        ROOT,
        args.manifest,
        args.prepared,
        args.dataset_root,
        args.outer_archive,
        args.detection_archive,
        args.ontology,
        args.protocol,
        args.output,
    )

    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
