"""Deterministic, non-destructive output initialization."""
import json
from pathlib import Path

from .framework import FIELDS, stop_a_status

DIRECTORIES = ["manifests", "presentation", "logs"] + [
    f"{group}/{child}"
    for group, children in {
        "detector": "raw metrics predictions plots examples",
        "generalization": "raw metrics predictions plots examples",
        "failure_analysis": "cases tables panels",
        "runtime": "raw metrics plots",
        "reproducibility": "configs commands environment provenance",
    }.items() for child in children.split()
]


def initialize(root, protocol):
    root = Path(root)
    for directory in DIRECTORIES:
        (root / directory).mkdir(parents=True, exist_ok=True)
    documents = {
        "manifests/protocol.json": protocol,
        "manifests/status.json": stop_a_status(protocol),
        **{f"manifests/{kind}.json": {"schema_version": 1, "fields": fields, "records": []} for kind, fields in FIELDS.items()},
        "presentation/headline_detector.json": {"status": "PENDING", "fields": ["dataset", "split", "metric", "value", "unit", "source_artifact"], "rows": []},
        "presentation/domain_comparison.json": {"status": "BLOCKED_PENDING_CHAT03", "fields": ["metric", "in_domain_value", "external_value", "mapping_version", "limitations"], "rows": []},
        "presentation/limitations_failures.json": {"status": "PENDING", "fields": ["case_id", "failure_type", "hypothesized_cause", "supporting_evidence", "limitations"], "rows": []},
        "presentation/reproducibility.json": {"status": "PENDING", "fields": FIELDS["evidence"], "rows": []},
    }
    for relative, content in documents.items():
        path = root / relative
        try:
            with path.open("x", encoding="utf-8") as stream:
                json.dump(content, stream, indent=2, allow_nan=False)
                stream.write("\n")
        except FileExistsError:
            pass  # Preserve all existing raw evidence and edited records.
    return root
