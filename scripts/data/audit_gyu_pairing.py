"""CLI for the read-only GYU-DET V3 pairing audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from data.validators.gyu_pairing import audit, write_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    protected = (Path(__file__).resolve().parents[2] / "data" / "raw").resolve()
    if output == root or root in output.parents or output == protected or protected in output.parents:
        parser.error("Output must be outside the input dataset and repository data/raw.")
    try:
        result = audit(root)
        write_outputs(result, output)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Audit failed: {exc}\n")
    for row in result["pairing_summary"]:
        print(row)
    print(f"Reports: {output}")
    if not any(r["image_filename"] == "5774.JPG" and r["label_filename"] == "5774.txt"
               for r in result["regression_5774"]):
        print("FAIL: required 5774.JPG / 5774.txt unique exact pair was not found.", file=sys.stderr)
        return 1
    print("PASS: 5774.JPG / 5774.txt is a normal exact matched pair.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
