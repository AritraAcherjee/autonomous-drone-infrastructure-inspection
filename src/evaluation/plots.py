"""Validated plot specifications for future renderers; no scoring or model IO.

Specifications carry source hashes and are not images or completed results.
Plot artifacts must be re-indexed and reviewed after rendering by a consumer.
"""
import json
import math

from .framework import artifact, external_gate, require, validate_evidence

KINDS = {"confusion_matrix", "pr_curves", "training_validation_curves", "domain_comparison", "example_panel", "runtime"}


def numbers(values):
    return isinstance(values, list) and bool(values) and all(type(v) in {int, float} and math.isfinite(v) for v in values)


def plot_spec(kind, evidence, experiment, protocol, root):
    require(kind in KINDS, "Unknown plot kind")
    validate_evidence(evidence, experiment, protocol, root)
    require(evidence["acceptance_status"] == "ACCEPTED", "Accepted plot source required")
    expected = "SIM" if kind == "runtime" else "ML"
    require(evidence["evidence_type"] == expected, "Plot evidence taxonomy mismatch")
    if kind == "domain_comparison":
        external_gate(protocol)
        require(experiment["workstream"] == "Chat03", "Chat03 comparison evidence required")
    payload = json.loads(artifact(root, evidence["artifact_path"]).read_text(encoding="utf-8"))
    require(payload.get("kind") == kind and payload.get("synthetic") is False, "Incorrect/synthetic plot source")
    data = payload["data"]
    if kind == "confusion_matrix":
        labels, matrix = data["labels"], data["matrix"]
        require(bool(labels) and len(set(labels)) == len(labels) and len(matrix) == len(labels), "Invalid matrix labels/shape")
        require(all(numbers(row) and len(row) == len(labels) and all(type(v) is int and v >= 0 for v in row) for row in matrix), "Invalid matrix counts")
    elif kind == "example_panel":
        require(bool(data["cases"]), "Empty panel")
        for case in data["cases"]:
            require(case["outcome"] in {"TP", "FP", "FN"}, "Invalid panel outcome")
            artifact(root, case["image_path"])
            require(bool(case["evidence_id"]), "Case source required")
    else:
        require(bool(data["series"]), "Empty plot")
        for series in data["series"]:
            require(bool(series["label"]) and numbers(series["x"]) and numbers(series["y"]) and len(series["x"]) == len(series["y"]), "Invalid curve")
            if kind == "pr_curves":
                require(all(0 <= v <= 1 for v in series["x"] + series["y"]), "Invalid PR range")
        if kind == "domain_comparison":
            require({s["domain"] for s in data["series"]} == {"in_domain", "external"}, "Both domains required")
        if kind == "runtime":
            require(data["unit"] in {"ms", "s", "FPS"}, "Runtime unit required")
    return {"kind": kind, "data": data, "evidence_id": evidence["evidence_id"], "source_sha256": evidence["artifact_sha256"], "status": "RENDER_INPUT_ONLY", "stop_a_status": "NOT COMPLETE"}
