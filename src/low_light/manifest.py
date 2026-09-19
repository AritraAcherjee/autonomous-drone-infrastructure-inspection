"""Deterministic scientific manifests for validation-only benchmark v1.

Image identity is a repository-relative POSIX path. Label identity is the
SHA-256 of the original bytes: annotations are never parsed or rewritten.
L0 has null parameters/seed because it is a byte copy, not a transform.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from types import MappingProxyType

import cv2
import numpy as np

from .severity import GLOBAL_SEED, PROTOCOL_ID, SEVERITY_IDS, SEVERITY_NAMES, canonical_config
from .transforms import derive_seed


SOURCE_SPLIT = "valid"
BENCHMARK_ROOT = PurePosixPath("outputs/experiments/low_light/benchmark_v1")
VALID_MANIFEST = PurePosixPath("data/manifests/gyu_det_v3_baseline_v1/valid.csv")
SOURCE_VERSION = VALID_MANIFEST.parent / "VERSION.json"
VALID_SOURCE_ROOT = PurePosixPath("data/raw/gyu_det/v3/extracted/valid/valid")
MANIFEST_NAMES = ("validation_manifest.csv", "validation_manifest.json", "benchmark_summary.json")
TIMESTAMP_POLICY = "omitted: no wall-clock time participates in scientific identity"
ARTIFACT_ENCODING = MappingProxyType({
    "version": "aegis-low-light-artifact-encoding-v1",
    "normal": "source_bytes",
    "transformed_format": "PNG",
    "png_compression": 3,
    "filename_identity": "sha256_source_relative_posix_path_prefix; collisions rejected before writes",
    "filename_digest_characters": 24,
})
SANITY = MappingProxyType({
    "version": "aegis-low-light-benchmark-sanity-v1",
    "luminance": "OpenCV COLOR_BGR2GRAY on decoded uint8 BGR, ignoring EXIF orientation",
    "near_black_operator": "<=",
    "near_black_threshold": 10,
    "percentage_units": "0..100",
    "aggregation": "unweighted arithmetic mean of per-image statistics, by severity",
})
CSV_FIELDS = (
    "protocol_version", "global_seed", "source_relative_path", "source_split",
    "severity", "derived_seed", "resolved_transform_parameters", "output_relative_path",
    "source_sha256", "generated_image_sha256", "source_label_relative_path",
    "output_label_relative_path", "source_label_sha256", "generated_label_sha256",
    "source_width", "source_height", "generated_width", "generated_height",
    "label_identity", "generation_status", "generation_scope",
    "mean_luminance", "median_luminance", "near_black_percentage",
)
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def require_valid_split(split: object) -> None:
    if type(split) is not str or split != SOURCE_SPLIT:
        raise ValueError("source split must be exactly 'valid'; train/test/resplitting are prohibited")


def relative_posix(path: str | os.PathLike[str]) -> str:
    """Normalize separators; reject absolute, ambiguous, or traversing paths."""
    try:
        value = os.fspath(path)
    except TypeError as exc:
        raise ValueError("expected a repository-relative text path") from exc
    if not isinstance(value, str):
        raise ValueError("expected a repository-relative text path")
    value = value.replace("\\", "/")
    if (any(c in value for c in ':|\x00') or any(ord(c) < 32 for c in value)
            or any(p in ("", ".", "..") or p.endswith((" ", ".")) for p in value.split("/"))):
        raise ValueError("path must be unambiguous and repository-relative, without traversal")
    return PurePosixPath(value).as_posix()


def validate_source_paths(image: str, label: str) -> tuple[str, str]:
    image, label = relative_posix(image), relative_posix(label)
    image_path = PurePosixPath(image)
    if (image_path.parent != VALID_SOURCE_ROOT / "images"
            or image_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")
            or PurePosixPath(label) != VALID_SOURCE_ROOT / "labels" / (image_path.stem + ".txt")):
        raise ValueError("source paths must preserve the canonical raw valid image/label association")
    return image, label


def variant_paths(source_relative_path: str, severity: str) -> tuple[str, str]:
    """Use a path-identity digest prefix as filename, with preflight collision checks.

    Each severity has sibling images/labels directories for evaluator compatibility.
    Transformed artifacts use lossless PNG; L0 retains the source file extension.
    Short filenames keep nested development fixtures within Windows path limits.
    """
    source = relative_posix(source_relative_path)
    if severity not in SEVERITY_IDS:
        raise ValueError("unknown severity")
    identity = hashlib.sha256(source.encode("utf-8")).hexdigest()[:ARTIFACT_ENCODING["filename_digest_characters"]]
    suffix = PurePosixPath(source).suffix if severity == "L0" else ".png"
    directory = BENCHMARK_ROOT / "validation" / SEVERITY_NAMES[severity].lower()
    return ((directory / "images" / (identity + suffix)).as_posix(),
            (directory / "labels" / (identity + ".txt")).as_posix())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha256(value: object) -> None:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError("expected a lowercase SHA-256 digest")


def deterministic_json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def strict_json_loads(data: bytes | str) -> object:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError(f"non-finite JSON value: {value}")

    try:
        return json.loads(data, object_pairs_hook=unique, parse_constant=nonfinite)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("malformed JSON") from exc


def luminance_statistics(image: np.ndarray) -> dict[str, float]:
    """Grayscale statistics of the artifact's decoded pixels, with gray <= 10 black."""
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
            or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) == 0):
        raise ValueError("statistics require nonempty uint8 BGR pixels")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return {
        "mean_luminance": float(np.mean(gray, dtype=np.float64)),
        "median_luminance": float(np.median(gray)),
        "near_black_percentage": float(100.0 * np.count_nonzero(gray <= SANITY["near_black_threshold"])
                                       / gray.size),
    }


def validate_record(record: Mapping) -> dict:
    """Validate all scientific fields, returning an independent normalized record."""
    if not isinstance(record, Mapping) or set(record) != set(CSV_FIELDS):
        raise ValueError("manifest record has missing or unsupported fields")
    result = dict(record)
    require_valid_split(result["source_split"])
    if (result["protocol_version"] != PROTOCOL_ID or type(result["global_seed"]) is not int
            or result["global_seed"] != GLOBAL_SEED):
        raise ValueError("manifest protocol/seed differs from frozen contract")
    result["source_relative_path"], result["source_label_relative_path"] = validate_source_paths(
        result["source_relative_path"], result["source_label_relative_path"])
    severity = result["severity"]
    if not isinstance(severity, str) or severity not in SEVERITY_IDS:
        raise ValueError("manifest severity is invalid")
    params = canonical_config()["severities"][severity]["parameters"]
    if deterministic_json_bytes(result["resolved_transform_parameters"]) != deterministic_json_bytes(params):
        raise ValueError("manifest transform parameters differ from Task B")
    seed = None if severity == "L0" else derive_seed(SOURCE_SPLIT, result["source_relative_path"], severity)
    if type(result["derived_seed"]) is not type(seed) or result["derived_seed"] != seed:
        raise ValueError("manifest derived seed differs from Task B")
    output, label_output = variant_paths(result["source_relative_path"], severity)
    result["output_relative_path"] = relative_posix(result["output_relative_path"])
    if result["output_relative_path"] != output:
        raise ValueError("manifest output is outside the frozen variant namespace")
    for field in ("source_sha256", "generated_image_sha256", "source_label_sha256"):
        require_sha256(result[field])
    if result["output_label_relative_path"] is None:
        if result["generated_label_sha256"] is not None:
            raise ValueError("uncopied label must have null output hash")
    else:
        result["output_label_relative_path"] = relative_posix(result["output_label_relative_path"])
        require_sha256(result["generated_label_sha256"])
        if (result["output_label_relative_path"] != label_output
                or result["source_label_sha256"] != result["generated_label_sha256"]):
            raise ValueError("label path/hash does not preserve source label bytes")
    if result["label_identity"] != "sha256:" + result["source_label_sha256"]:
        raise ValueError("label identity must describe the original annotation bytes")
    for field in ("source_width", "source_height", "generated_width", "generated_height"):
        if type(result[field]) is not int or result[field] <= 0:
            raise ValueError("manifest dimensions must be positive integers")
    if (result["source_width"] != result["generated_width"]
            or result["source_height"] != result["generated_height"]):
        raise ValueError("variant dimensions must equal source dimensions")
    if severity == "L0" and result["source_sha256"] != result["generated_image_sha256"]:
        raise ValueError("L0 must be a byte-identical source copy")
    if (result["generation_status"] != "generated"
            or result["generation_scope"] not in ("development_sample", "full_validation")):
        raise ValueError("manifest generation status/scope is invalid")
    for field, maximum in (("mean_luminance", 255), ("median_luminance", 255),
                           ("near_black_percentage", 100)):
        value = result[field]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
            raise ValueError("manifest luminance statistic is invalid")
    return result


def ordered_records(records) -> list[dict]:
    normalized = [validate_record(record) for record in records]
    if not normalized:
        raise ValueError("manifest cannot be empty")
    identities = [(r["source_relative_path"], r["severity"]) for r in normalized]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate manifest variant identity")
    normalized.sort(key=lambda r: (r["source_relative_path"], SEVERITY_IDS.index(r["severity"])))
    return normalized


def complete_records(records) -> list[dict]:
    ordered = ordered_records(records)
    scopes = {r["generation_scope"] for r in ordered}
    if len(scopes) != 1 or len({r["output_label_relative_path"] is None for r in ordered}) != 1:
        raise ValueError("manifest mixes generation scopes or label-copy policies")
    groups = {}
    for record in ordered:
        groups.setdefault(record["source_relative_path"], []).append(record)
    for group in groups.values():
        if [r["severity"] for r in group] != list(SEVERITY_IDS):
            raise ValueError("every source must have exactly L0-L4")
        for field in ("source_sha256", "source_label_relative_path", "source_label_sha256",
                      "source_width", "source_height", "label_identity"):
            if len({r[field] for r in group}) != 1:
                raise ValueError("source identity differs across variants")
    return ordered


def manifest_json_bytes(records) -> bytes:
    return deterministic_json_bytes({
        "schema_version": "aegis-low-light-manifest-v1",
        "protocol_version": PROTOCOL_ID, "global_seed": GLOBAL_SEED, "source_split": SOURCE_SPLIT,
        "transform_config": canonical_config(), "benchmark_sanity": dict(SANITY),
        "artifact_encoding": dict(ARTIFACT_ENCODING),
        "records": complete_records(records),
    })


def read_manifest_json(data: bytes | str) -> list[dict]:
    payload = strict_json_loads(data)
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValueError("malformed manifest object")
    records = complete_records(payload["records"])
    if deterministic_json_bytes(payload) != manifest_json_bytes(records):
        raise ValueError("manifest schema/config/order/path contract differs")
    return records


def manifest_csv_bytes(records) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for record in complete_records(records):
        row = dict(record)
        row["resolved_transform_parameters"] = json.dumps(
            row["resolved_transform_parameters"], sort_keys=True, separators=(",", ":"), allow_nan=False)
        writer.writerow(row)
    return stream.getvalue().encode("utf-8")


def benchmark_summary(records, *, available_source_count: int, development_limit: int | None,
                      source_manifest_sha256: str, manifest_hashes: Mapping) -> dict:
    ordered = complete_records(records)
    count = len(ordered) // len(SEVERITY_IDS)
    if type(available_source_count) is not int or available_source_count < count:
        raise ValueError("invalid available source count")
    if development_limit is not None and (type(development_limit) is not int or development_limit <= 0):
        raise ValueError("development limit must be a positive integer")
    expected_count = available_source_count if development_limit is None else min(development_limit, available_source_count)
    scope = "full_validation" if development_limit is None else "development_sample"
    if count != expected_count or ordered[0]["generation_scope"] != scope:
        raise ValueError("sample count/scope does not match deterministic selection")
    require_sha256(source_manifest_sha256)
    if set(manifest_hashes) != set(MANIFEST_NAMES[:2]):
        raise ValueError("summary must hash both manifests")
    for digest in manifest_hashes.values():
        require_sha256(digest)
    counts = Counter(r["severity"] for r in ordered)
    aggregate = {}
    for severity in SEVERITY_IDS:
        group = [r for r in ordered if r["severity"] == severity]
        aggregate[severity] = {
            field: math.fsum(r[field] for r in group) / len(group)
            for field in ("mean_luminance", "median_luminance", "near_black_percentage")
        }
    return {
        "protocol_version": PROTOCOL_ID, "global_seed": GLOBAL_SEED, "source_split": SOURCE_SPLIT,
        "source_image_count": count, "variant_count_by_severity": dict(counts),
        "total_variant_count": len(ordered), "manifest_hashes": dict(manifest_hashes),
        "source_manifest_relative_path": VALID_MANIFEST.as_posix(),
        "source_manifest_sha256": source_manifest_sha256,
        "transform_config_sha256": sha256_bytes(deterministic_json_bytes(canonical_config())),
        "generation_timestamp_policy": TIMESTAMP_POLICY,
        "generation_scope": scope, "scientific_evaluation_evidence": False,
        "selection": {"policy": "sorted_source_relative_path_prefix", "development_limit": development_limit,
                      "available_source_count": available_source_count},
        "benchmark_sanity": dict(SANITY), "artifact_encoding": dict(ARTIFACT_ENCODING),
        "aggregate_luminance_by_severity": aggregate,
        "expected_luminance_order": list(SEVERITY_IDS),
        "luminance_progression_status": "not_assessed",
    }
