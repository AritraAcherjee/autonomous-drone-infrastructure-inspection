"""Derive a HEAD-bound DamSegment runtime manifest after preparation commit."""

import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from detection.generalization.manifest import (
    canonical,
    derive_runtime_manifest,
    frozen_gate,
    read_json,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--ontology", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output).resolve()

    if output.exists():
        raise FileExistsError(
            "Runtime manifest already exists; regeneration refused"
        )

    runtime = derive_runtime_manifest(
        args.contract,
        ROOT,
        args.checkpoint,
    )

    ontology = read_json(args.ontology)
    protocol = read_json(args.protocol)

    frozen_gate(
        runtime,
        ROOT,
        ontology,
        protocol,
    )

    payload = canonical(runtime) + b"\n"
    digest = hashlib.sha256(payload).hexdigest()

    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("xb") as stream:
        stream.write(payload)

    print("RUNTIME_MANIFEST=", output)
    print("RUNTIME_MANIFEST_SHA256=", digest)
    print(
        "EVALUATION_GIT_SHA=",
        runtime["evaluation_git_sha"],
    )
    print(
        "PORTABLE_CONTRACT_SHA256=",
        runtime["portable_contract_sha256"],
    )


if __name__ == "__main__":
    main()
