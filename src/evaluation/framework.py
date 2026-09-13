"""Strict JSON record contracts and read-only evidence ingestion.

Paths resolve beneath an explicit evidence root. No checkpoint is opened and no
evaluation is executed. Acceptance is a reviewed evidence claim, not proof that
the upstream experiment was scientifically valid.
"""
import hashlib
import json
import math
from pathlib import Path
import re

FIELDS = {
    "experiment": "experiment_id name claim_id workstream owner status evidence_type dataset dataset_version split class_mapping_version checkpoint_id checkpoint_sha256 git_sha config_path command seed repeat_index hardware environment_ref started_at completed_at raw_result_path prediction_path metric_path plot_path accepted notes synthetic".split(),
    "evidence": "evidence_id experiment_id claim_id workstream evidence_type description artifact_path artifact_sha256 dataset split dataset_version checkpoint_id checkpoint_sha256 git_sha config_ref command_ref generated_at machine environment_ref acceptance_status reviewer_note synthetic".split(),
    "metric": "metric_id experiment_id dataset split scope class metric value unit status source_artifact evidence_type".split(),
    "failure": "case_id experiment_id dataset image_or_frame_id ground_truth_class predicted_class confidence iou outcome failure_type difficulty_tags image_path annotation_path prediction_path hypothesized_cause supporting_evidence analysis_confidence presentation_candidate notes".split(),
}
TYPES = {"SW", "ML", "GEO", "SIM"}
STATUSES = {"PLANNED", "BLOCKED", "PENDING_INPUT", "READY", "RUNNING", "COMPLETE", "ACCEPTED", "REJECTED"}
PREDICTIVE = {"mAP@0.5", "mAP@0.5:0.95", "precision", "recall", "F1", "per-class AP", "detection count"}
METRICS = {**dict.fromkeys(PREDICTIVE, "ML"), "inference latency": "SIM", "FPS": "SIM", "tests passed": "SW", "projection error": "GEO"}
TAGS = set("LOW_LIGHT SMALL_DEFECT OCCLUSION TEXTURE BACKGROUND_CONFUSION EDGE_OF_FRAME MULTIPLE_DEFECTS LOW_CONTRAST AMBIGUOUS_LABEL OTHER".split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def present(value):
    return value is not None and str(value).strip().upper() not in {"", "PENDING", "N/A", "NULL"}


def required(record, keys):
    for key in keys:
        require(present(record.get(key)), f"Missing provenance: {key}")


def digest(value, length):
    return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None


def shape(kind, record):
    require(set(record) == set(FIELDS[kind]), f"Incorrect {kind} fields")
    if "evidence_type" in record:
        require(record["evidence_type"] in TYPES, "Invalid evidence type")


def external_gate(protocol):
    ext = protocol["external"]
    require(ext["external_evaluation_authorized"] is True, "External evaluation BLOCKED")
    required(ext, "authorization_ref benchmark dataset_version subset class_mapping_version checkpoint_sha256 not_used_for_tuning_ref".split())
    require(digest(ext["checkpoint_sha256"], 64), "Invalid external checkpoint hash")
    require(ext["checkpoint_sha256"] == protocol["detector"]["checkpoint_sha256"], "Checkpoint mismatch")


def validate_experiment(record, protocol):
    shape("experiment", record)
    required(record, "experiment_id name claim_id workstream owner dataset dataset_version split".split())
    require(record["workstream"] in {"Chat02", "Chat03", "Chat19"}, "Unknown workstream")
    require(record["status"] in STATUSES, "Invalid experiment status")
    require(type(record["synthetic"]) is bool and type(record["accepted"]) is bool, "Boolean flags required")
    require(record["accepted"] == (record["status"] == "ACCEPTED"), "Inconsistent acceptance")
    if record["workstream"] == "Chat03" and record["status"] in {"READY", "RUNNING", "COMPLETE", "ACCEPTED"}:
        external_gate(protocol)
    if record["accepted"]:
        require(not record["synthetic"], "Synthetic evidence cannot be accepted")
        required(record, "git_sha config_path command hardware environment_ref started_at completed_at raw_result_path".split())
        require(digest(record["git_sha"], 40), "Full Git SHA required")
        if record["evidence_type"] == "ML":
            require(record["workstream"] in {"Chat02", "Chat03"}, "ML owner must be Chat02/Chat03")
            required(record, ["checkpoint_id", "checkpoint_sha256"])
            require(digest(record["checkpoint_sha256"], 64), "Checkpoint SHA-256 required")
            require(type(record["seed"]) is int, "ML seed required")
            det = protocol["detector"]
            require(protocol["state"] == "FROZEN" and det["status"] == "FROZEN" and det["pretraining_gate"] == "PASS", "Detector PENDING/unfrozen")
            required(det, "checkpoint_path checkpoint_id checkpoint_sha256 git_sha seed configuration".split())
            require(digest(det["git_sha"], 40), "Detector Git SHA required")
            require(record["checkpoint_sha256"] == det["checkpoint_sha256"] and record["checkpoint_id"] == det["checkpoint_id"], "Checkpoint mismatch")
            if record["workstream"] == "Chat02":
                require((record["dataset"], record["dataset_version"], record["split"]) == ("GYU-DET", "v3/baseline-v1", "test"), "Held-out split required")
                require(digest(protocol["dataset"]["split_sha256"], 64), "Held-out manifest hash required")
            else:
                ext = protocol["external"]
                require((record["dataset"], record["dataset_version"], record["split"], record["class_mapping_version"]) == (ext["benchmark"], ext["dataset_version"], ext["subset"], ext["class_mapping_version"]), "External identity/mapping mismatch")
    return record


def artifact(root, name):
    require(present(name), "Artifact path required")
    base = Path(root).resolve()
    path = (base / name).resolve()
    require(path.is_relative_to(base) and path.is_file(), "Missing or out-of-root artifact")
    require(path.suffix.lower() not in {".pt", ".pth", ".ckpt", ".onnx", ".safetensors"}, "Model artifacts must not be loaded")
    return path


def validate_evidence(record, experiment, protocol, root):
    shape("evidence", record)
    validate_experiment(experiment, protocol)
    require(record["acceptance_status"] in {"PENDING", "INCOMPLETE", "ACCEPTED", "REJECTED"}, "Invalid acceptance status")
    require(type(record["synthetic"]) is bool, "Synthetic flag required")
    for key in "experiment_id claim_id workstream evidence_type dataset split dataset_version checkpoint_id checkpoint_sha256 git_sha".split():
        require(record[key] == experiment[key], f"Evidence mismatch: {key}")
    if record["acceptance_status"] == "ACCEPTED":
        require(experiment["accepted"] and not record["synthetic"], "Unaccepted/synthetic source")
        required(record, "evidence_id description config_ref command_ref generated_at machine environment_ref reviewer_note".split())
        require(digest(record["artifact_sha256"], 64), "Artifact SHA-256 required")
        path = artifact(root, record["artifact_path"])
        require(hashlib.sha256(path.read_bytes()).hexdigest() == record["artifact_sha256"], "Artifact hash mismatch")
        for key in ["raw_result_path", "config_path", "environment_ref"]:
            artifact(root, experiment[key])
        for key in ["config_ref", "command_ref", "environment_ref"]:
            artifact(root, record[key])
    return record


def validate_metric(record, experiment, evidence, protocol, root):
    shape("metric", record)
    validate_evidence(evidence, experiment, protocol, root)
    require(record["metric"] in METRICS, "Unknown metric; extend explicit taxonomy first")
    require(record["evidence_type"] == METRICS[record["metric"]] == evidence["evidence_type"], "Metric/evidence taxonomy mismatch")
    for key in ["experiment_id", "dataset", "split"]:
        require(record[key] == experiment[key], f"Metric mismatch: {key}")
    require(record["status"] in {"PENDING", "INCOMPLETE", "ACCEPTED", "REJECTED"}, "Invalid metric status")
    value = record["value"]
    require(value is None or (type(value) in {int, float} and math.isfinite(value)), "Numeric value or null required")
    if record["status"] == "ACCEPTED":
        require(value is not None and evidence["acceptance_status"] == "ACCEPTED", "Missing/unaccepted metric")
        require(record["source_artifact"] == evidence["artifact_path"], "Metric source mismatch")
        required(record, ["metric_id", "scope", "unit"])
        # Accepted metrics must occur verbatim in the hash-verified upstream export.
        source = json.loads(artifact(root, record["source_artifact"]).read_text(encoding="utf-8"))
        require(record in source.get("metrics", []), "Metric absent from source export")
    return record


def validate_failure(record):
    shape("failure", record)
    required(record, "case_id experiment_id dataset image_or_frame_id failure_type".split())
    require(record["outcome"] in {"TP", "FP", "FN", "CLASS_CONFUSION", "LOW_CONFIDENCE_TP"}, "Invalid outcome")
    require(isinstance(record["difficulty_tags"], list) and set(record["difficulty_tags"]) <= TAGS, "Invalid difficulty tags")
    for key in ["confidence", "iou", "analysis_confidence"]:
        value = record[key]
        require(value is None or (type(value) in {int, float} and math.isfinite(value) and 0 <= value <= 1), f"Invalid {key}")
    require(type(record["presentation_candidate"]) is bool, "Boolean candidate required")
    if record["presentation_candidate"]:
        required(record, ["supporting_evidence", "image_path"])
    return record


def stop_a_status(protocol):
    # This preparation release deliberately has no finalization authority.
    return {"status": "NOT COMPLETE", "detector": "PENDING" if protocol["detector"]["status"] != "FROZEN" else "AWAITING_REVIEW", "external": "BLOCKED" if protocol["external"]["external_evaluation_authorized"] is not True else "AWAITING_REVIEW", "requirements": protocol["definition_of_done"], "reason": "Final acceptance requires Control Center review of the complete evidence package."}


def presentation_rows(bundles, protocol, root):
    rows = []
    for metric, experiment, evidence in bundles:
        validate_metric(metric, experiment, evidence, protocol, root)
        require(not experiment["synthetic"] and not evidence["synthetic"], "Synthetic production output prohibited")
        rows.append({**metric, "value": metric["value"] if metric["status"] == "ACCEPTED" else None})
    return {"stop_a_status": stop_a_status(protocol)["status"], "rows": rows}
