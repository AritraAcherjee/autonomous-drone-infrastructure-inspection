"""Create only empty Chat 19 evidence containers; never execute experiments."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluation.prepare import initialize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/final_evaluation/stop_a")
    args = parser.parse_args()
    protocol = json.loads((ROOT / "configs/evaluation/stop_a_protocol.yaml").read_text(encoding="utf-8"))
    initialize(args.output, protocol)
    print("PREPARED_NOT_FROZEN; STOP A = NOT COMPLETE")


if __name__ == "__main__":
    main()
