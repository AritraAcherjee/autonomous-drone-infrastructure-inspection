"""Generate a read-only visual review package from the GYU pairing audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from data.validators.gyu_orphan_review import generate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "audit", "classes", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = generate(args.root, args.audit, args.classes, args.output)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Review generation failed: {exc}\n")
    print({key: result[key] for key in ("valid_annotations", "invalid_annotations", "review_sheets", "candidate_rows", "rendering_failures")})
    print(f"Review package: {args.output.resolve()}")
    return 1 if result["invalid_annotations"] or result["rendering_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
