"""Generate frozen validation variants only; no training or detector inference."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from src.low_light.manifest import BENCHMARK_ROOT, VALID_MANIFEST
from src.low_light.validation_variants import generate_validation_variants


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate L0-L4 from approved GYU valid metadata only. Never train, resplit, or run a detector.",
        epilog="The frozen output root must be empty. A --limit run is a development sample, not scientific evaluation evidence.")
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY, help="repository containing approved validation metadata")
    parser.add_argument("--output-root", type=Path, default=Path(BENCHMARK_ROOT),
                        help=f"must resolve to <repo-root>/{BENCHMARK_ROOT}")
    parser.add_argument("--config", type=Path, default=Path("configs/low_light/benchmark_v1.yaml"),
                        help="Task B frozen config, relative to repo root or absolute")
    parser.add_argument("--source-manifest", type=Path, default=Path(VALID_MANIFEST),
                        help="must be the canonical approved valid.csv; alternate manifests are rejected")
    parser.add_argument("--source-split", choices=("valid",), default="valid", help="existing split identity; only valid is permitted")
    parser.add_argument("--limit", type=int, help="positive deterministic lexical prefix size; marks all records as development_sample")
    parser.add_argument("--no-copy-labels", action="store_true", help="retain label identity/hash without copying labels")
    args = parser.parse_args(argv)
    try:
        summary = generate_validation_variants(
            args.repo_root, source_split=args.source_split, output_root=args.output_root,
            source_manifest=args.source_manifest, config_path=args.config,
            limit=args.limit, copy_labels=not args.no_copy_labels)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Generation refused: {exc}\n")
    print(f"{summary['generation_scope']}: {summary['source_image_count']} validation sources, "
          f"{summary['total_variant_count']} variants. No scientific evaluation performed.")
    print(args.repo_root.resolve() / BENCHMARK_ROOT / "manifests/benchmark_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
