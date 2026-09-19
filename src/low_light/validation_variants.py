"""Generate validation-only variants without changing source data or split identity.

The trust anchor is the repository's approved baseline-v1 VERSION.json and
valid.csv, never a caller-supplied list of samples or split assignments. Only
validation metadata is opened. No split text lists or other split CSVs are read.
All source records are gated before a deterministic development prefix is taken.

Outputs must start in an empty frozen benchmark namespace. Files are created
exclusively, so reruns cannot overwrite evidence or mutate a hard-linked source.
On failure, incomplete artifacts may remain, but no successful summary is issued.
"""

from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .manifest import (
    ARTIFACT_ENCODING, BENCHMARK_ROOT, MANIFEST_NAMES, SOURCE_SPLIT, SOURCE_VERSION, VALID_MANIFEST,
    benchmark_summary, complete_records, deterministic_json_bytes, luminance_statistics,
    manifest_csv_bytes, manifest_json_bytes, relative_posix, require_sha256,
    require_valid_split, sha256_bytes, sha256_file, strict_json_loads, validate_source_paths,
    variant_paths,
)
from .severity import GLOBAL_SEED, PROTOCOL_ID, SEVERITY_IDS, load_config
from .transforms import apply_low_light, derive_seed


SOURCE_FIELDS = (
    "processed_split", "raw_split", "image_relative_path", "label_relative_path", "image_sha256",
    "annotation_count", "class_ids", "duplicate_group_id", "leakage_group_id", "inclusion_reason",
    "exclusion_reason",
)


@dataclass(frozen=True)
class ValidationSource:
    source_relative_path: str
    source_label_relative_path: str
    source_sha256: str
    source_split: str = SOURCE_SPLIT


def _repo_path(repo: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo / path


def _canonical_path(repo: Path, relative: str) -> Path:
    """Reject symlink/junction redirects before reading source or metadata bytes."""
    path = repo / relative_posix(relative)
    if path.resolve() != path:
        raise ValueError(f"canonical input path is redirected: {relative}")
    return path


def _config_path(repo: Path, value: str | Path | None) -> Path:
    path = _repo_path(repo, "configs/low_light/benchmark_v1.yaml" if value is None else value)
    resolved = path.resolve()
    if (resolved.is_relative_to((repo / "data").resolve()) or resolved != path
            or path.suffix.lower() not in (".yaml", ".yml")):
        raise ValueError("config must be a nonredirected YAML file outside dataset storage")
    return path


def checked_output_root(repo_root: str | Path, output_root: str | Path | None = None) -> Path:
    repo = Path(repo_root).resolve()
    expected = repo / BENCHMARK_ROOT
    proposed = expected if output_root is None else _repo_path(repo, output_root)
    resolved = proposed.resolve()
    raw = (repo / "data/raw").resolve()
    if resolved.is_relative_to(raw):
        raise ValueError("output resolves inside protected raw data")
    if resolved != expected or proposed != expected:
        raise ValueError(f"output root must be the frozen namespace: {BENCHMARK_ROOT}")
    return expected


def _output_path(repo: Path, relative: str) -> Path:
    root = checked_output_root(repo)
    path = repo / relative_posix(relative)
    resolved = path.resolve()
    if resolved.is_relative_to((repo / "data/raw").resolve()):
        raise ValueError("output resolves inside protected raw data")
    if not path.is_relative_to(root) or resolved != path:
        raise ValueError("output escapes or redirects the frozen benchmark namespace")
    return path


def _write_new(repo: Path, relative: str, data: bytes) -> None:
    path = _output_path(repo, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path = _output_path(repo, relative)
    # Exclusive creation also protects against existing hard links, which resolve()
    # cannot distinguish from regular files. Never truncate an existing inode.
    with path.open("xb") as stream:
        stream.write(data)


def load_validation_sources(repo_root: str | Path, *, source_split: str = SOURCE_SPLIT,
                            source_manifest: str | Path | None = None) -> tuple[list[ValidationSource], str]:
    """Read only approved validation metadata; reject the entire input on any bad row."""
    require_valid_split(source_split)
    repo = Path(repo_root).resolve()
    expected = repo / VALID_MANIFEST
    proposed = expected if source_manifest is None else _repo_path(repo, source_manifest)
    # Check the lexical identity first: an explicit test/train path is never opened,
    # even if its contents or a symlink claim to be validation.
    if proposed != expected:
        raise ValueError(f"only the canonical validation manifest is allowed: {VALID_MANIFEST}")
    manifest_path = _canonical_path(repo, VALID_MANIFEST.as_posix())
    version_path = _canonical_path(repo, SOURCE_VERSION.as_posix())
    version = strict_json_loads(version_path.read_bytes())
    if (not isinstance(version, dict) or version.get("dataset") != "GYU-DET"
            or version.get("source_version") != "v3"
            or version.get("processed_specification_version") != "baseline-v1"
            or not isinstance(version.get("manifest_sha256"), dict)):
        raise ValueError("malformed approved source version metadata")
    expected_hash = version["manifest_sha256"].get(SOURCE_SPLIT)
    require_sha256(expected_hash)
    manifest_bytes = manifest_path.read_bytes()
    manifest_hash = sha256_bytes(manifest_bytes)
    if manifest_hash != expected_hash:
        raise ValueError("validation manifest hash differs from approved VERSION.json")
    try:
        reader = csv.DictReader(io.StringIO(manifest_bytes.decode("utf-8"), newline=""), strict=True)
        if (reader.fieldnames is None or len(reader.fieldnames) != len(SOURCE_FIELDS)
                or set(reader.fieldnames) != set(SOURCE_FIELDS)):
            raise ValueError("malformed canonical validation CSV header")
        records = []
        for row in reader:
            if set(row) != set(SOURCE_FIELDS) or any(value is None for value in row.values()):
                raise ValueError("malformed canonical validation CSV row")
            require_valid_split(row["raw_split"])
            require_valid_split(row["processed_split"])
            image, label = validate_source_paths(row["image_relative_path"], row["label_relative_path"])
            require_sha256(row["image_sha256"])
            if row["exclusion_reason"] or not row["inclusion_reason"]:
                raise ValueError("excluded/unapproved source record")
            records.append(ValidationSource(image, label, row["image_sha256"]))
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("malformed canonical validation CSV") from exc
    if not records or len({r.source_relative_path for r in records}) != len(records):
        raise ValueError("validation manifest is empty or has duplicate sources")
    if len({r.source_relative_path.casefold() for r in records}) != len(records):
        raise ValueError("validation paths collide on case-insensitive filesystems")
    for record in records:
        _canonical_path(repo, record.source_relative_path)
        _canonical_path(repo, record.source_label_relative_path)
    return sorted(records, key=lambda r: r.source_relative_path), manifest_hash


def select_development_sources(sources: list[ValidationSource], limit: int | None) -> list[ValidationSource]:
    """Take a stable lexical prefix, never a random subset or a new split."""
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("development limit must be a positive integer")
    for source in sources:
        require_valid_split(source.source_split)
        validate_source_paths(source.source_relative_path, source.source_label_relative_path)
    ordered = sorted(sources, key=lambda r: r.source_relative_path)
    return ordered if limit is None else ordered[:limit]


def _decode_image(data: bytes) -> np.ndarray:
    # Ignore EXIF orientation: the photometric benchmark must not rotate pixels.
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    if image is None or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("source/generated artifact cannot be decoded as uint8 BGR")
    return image


def _assert_sources_unchanged(repo: Path, snapshots: dict[str, str]) -> None:
    for relative, before in sorted(snapshots.items()):
        if sha256_file(_canonical_path(repo, relative)) != before:
            raise ValueError(f"raw immutability violation: source hash changed: {relative}")


def verify_generated_files(repo_root: str | Path, records) -> None:
    """Detect missing/tampered artifacts, labels, dimensions, and sanity statistics.

    This verifier reads only generated files; it never opens a raw source image.
    """
    repo = Path(repo_root).resolve()
    for record in complete_records(records):
        image_path = _output_path(repo, record["output_relative_path"])
        image_bytes = image_path.read_bytes()
        if sha256_bytes(image_bytes) != record["generated_image_sha256"]:
            raise ValueError("generated image SHA-256 mismatch")
        image = _decode_image(image_bytes)
        if image.shape[:2] != (record["generated_height"], record["generated_width"]):
            raise ValueError("generated image dimensions differ from manifest")
        if any(record[field] != value for field, value in luminance_statistics(image).items()):
            raise ValueError("generated image luminance statistics differ from manifest")
        if record["output_label_relative_path"] is not None:
            label = _output_path(repo, record["output_label_relative_path"])
            if sha256_file(label) != record["generated_label_sha256"]:
                raise ValueError("generated label SHA-256 mismatch")


def generate_validation_variants(
    repo_root: str | Path, *, source_split: str = SOURCE_SPLIT,
    output_root: str | Path | None = None, source_manifest: str | Path | None = None,
    config_path: str | Path | None = None, limit: int | None = None, copy_labels: bool = True,
) -> dict:
    """Materialize the existing valid split; return its deterministic summary.

    A supplied limit always marks results as a development sample, including a
    limit larger than the population. No generated result is detector evaluation.
    Runtime encoder/numeric library versions should be held fixed for replay.
    """
    require_valid_split(source_split)
    if type(copy_labels) is not bool:
        raise ValueError("copy_labels must be a boolean")
    repo = Path(repo_root).resolve()
    root = checked_output_root(repo, output_root)
    config = load_config(_config_path(repo, config_path))
    sources, source_manifest_hash = load_validation_sources(
        repo, source_split=source_split, source_manifest=source_manifest)
    selected = select_development_sources(sources, limit)
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("benchmark output must be empty; existing evidence is never overwritten")
    planned = []
    for source in selected:
        for severity in SEVERITY_IDS:
            image, label = variant_paths(source.source_relative_path, severity)
            planned.extend((image, label) if copy_labels else (image,))
    planned.extend((BENCHMARK_ROOT / "manifests" / name).as_posix() for name in MANIFEST_NAMES)
    if len(set(planned)) != len(planned):
        raise ValueError("generated output path collision")
    for relative in planned:
        if os.path.lexists(_output_path(repo, relative)):
            raise ValueError("output already exists")
    records = []
    snapshots = {}
    scope = "full_validation" if limit is None else "development_sample"
    try:
        for source in selected:
            source_path = _canonical_path(repo, source.source_relative_path)
            label_path = _canonical_path(repo, source.source_label_relative_path)
            source_bytes = source_path.read_bytes()
            source_hash = sha256_bytes(source_bytes)
            snapshots[source.source_relative_path] = source_hash
            if source_hash != source.source_sha256:
                raise ValueError("source image hash differs from approved validation manifest")
            label_bytes = label_path.read_bytes()
            label_hash = sha256_bytes(label_bytes)
            snapshots[source.source_label_relative_path] = label_hash
            original = _decode_image(source_bytes)
            height, width = original.shape[:2]
            for severity in SEVERITY_IDS:
                image_relative, label_relative = variant_paths(source.source_relative_path, severity)
                if severity == "L0":
                    artifact = source_bytes  # Never decode/re-encode the normal output.
                else:
                    variant = apply_low_light(
                        original, severity, source_split=SOURCE_SPLIT,
                        source_relative_path=source.source_relative_path, config=config)
                    if variant.dtype != np.uint8 or variant.shape != original.shape:
                        raise ValueError("Task B output changed image shape/dtype")
                    ok, encoded = cv2.imencode(
                        ".png", variant, [cv2.IMWRITE_PNG_COMPRESSION, ARTIFACT_ENCODING["png_compression"]])
                    if not ok:
                        raise ValueError("PNG encoding failed")
                    artifact = encoded.tobytes()
                _write_new(repo, image_relative, artifact)
                if copy_labels:
                    _write_new(repo, label_relative, label_bytes)
                decoded = _decode_image(artifact)
                records.append({
                    "protocol_version": PROTOCOL_ID, "global_seed": GLOBAL_SEED,
                    "source_relative_path": source.source_relative_path, "source_split": SOURCE_SPLIT,
                    "severity": severity,
                    "derived_seed": None if severity == "L0" else derive_seed(SOURCE_SPLIT, source.source_relative_path, severity),
                    "resolved_transform_parameters": config["severities"][severity]["parameters"],
                    "output_relative_path": image_relative, "source_sha256": source_hash,
                    "generated_image_sha256": sha256_bytes(artifact),
                    "source_label_relative_path": source.source_label_relative_path,
                    "output_label_relative_path": label_relative if copy_labels else None,
                    "source_label_sha256": label_hash,
                    "generated_label_sha256": label_hash if copy_labels else None,
                    "source_width": width, "source_height": height,
                    "generated_width": int(decoded.shape[1]), "generated_height": int(decoded.shape[0]),
                    "label_identity": "sha256:" + label_hash, "generation_status": "generated",
                    "generation_scope": scope, **luminance_statistics(decoded),
                })
        _assert_sources_unchanged(repo, snapshots)
        verify_generated_files(repo, records)
        csv_bytes = manifest_csv_bytes(records)
        json_bytes = manifest_json_bytes(records)
        summary = benchmark_summary(
            records, available_source_count=len(sources), development_limit=limit,
            source_manifest_sha256=source_manifest_hash,
            manifest_hashes={MANIFEST_NAMES[0]: sha256_bytes(csv_bytes), MANIFEST_NAMES[1]: sha256_bytes(json_bytes)})
        for name, data in zip(MANIFEST_NAMES[:2], (csv_bytes, json_bytes)):
            _write_new(repo, (BENCHMARK_ROOT / "manifests" / name).as_posix(), data)
    finally:
        # Check again on failures as well as success, including mutations to an
        # earlier source while a subsequent image was being processed.
        _assert_sources_unchanged(repo, snapshots)
    # The summary is the completion marker, published only after verification.
    _write_new(repo, (BENCHMARK_ROOT / "manifests" / MANIFEST_NAMES[2]).as_posix(),
               deterministic_json_bytes(summary))
    return summary
