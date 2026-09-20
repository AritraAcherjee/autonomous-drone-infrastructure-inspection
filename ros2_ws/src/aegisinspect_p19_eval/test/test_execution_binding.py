from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
MODULE_PATH = ROOT / "tools/p19/normal_host_manifest.py"
SPEC = importlib.util.spec_from_file_location("normal_host_manifest", MODULE_PATH)
manifest = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(manifest)


def write(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def make_bound_tree(tmp_path: Path):
    root = tmp_path / "root"
    overlay = tmp_path / "p19-passive-observability-build/install"
    write(overlay / "setup.bash")
    for name, digest in manifest.P19_LIBRARY_HASHES.items():
        path = write(overlay / "aegisinspect_p19_eval/lib" / name)
        manifest.P19_LIBRARY_HASHES[name] = manifest.sha256_file(path)
    for relative, digest in manifest.DIAGNOSTIC_SOURCE_HASHES.items():
        data = b"source"
        if relative.endswith(".schema.json"):
            data = json.dumps({"$id": manifest.DIAGNOSTIC_SCHEMA}).encode()
        path = write(root / relative, data)
        manifest.DIAGNOSTIC_SOURCE_HASHES[relative] = manifest.sha256_file(path)
    runner = write(tmp_path / "runner.sh", b"#!/bin/sh\n")
    static_zip = write(tmp_path / "static.zip", b"static")
    manifest.STATIC_EVIDENCE_SHA256 = manifest.sha256_file(static_zip)
    manifest.ACCEPTED_OVERLAY = overlay.resolve()
    return root, overlay, runner, static_zip


@pytest.fixture(autouse=True)
def restore_constants():
    libraries = copy.deepcopy(manifest.P19_LIBRARY_HASHES)
    sources = copy.deepcopy(manifest.DIAGNOSTIC_SOURCE_HASHES)
    overlay = manifest.ACCEPTED_OVERLAY
    static = manifest.STATIC_EVIDENCE_SHA256
    yield
    manifest.P19_LIBRARY_HASHES.clear(); manifest.P19_LIBRARY_HASHES.update(libraries)
    manifest.DIAGNOSTIC_SOURCE_HASHES.clear(); manifest.DIAGNOSTIC_SOURCE_HASHES.update(sources)
    manifest.ACCEPTED_OVERLAY = overlay
    manifest.STATIC_EVIDENCE_SHA256 = static


def verify(tmp_path: Path, **changes):
    root, overlay, runner, static_zip = make_bound_tree(tmp_path)
    values = dict(root=root, implementation_sha="head", actual_head="head",
                  overlay=overlay, runner_path=runner,
                  static_evidence_path=static_zip)
    values.update(changes)
    return manifest.verify_execution_bindings(**values)


def test_all_execution_bindings_positive(tmp_path):
    result = verify(tmp_path)
    assert result["implementation_sha"] == "head"
    assert result["diagnostic_schema"] == manifest.DIAGNOSTIC_SCHEMA
    assert len(result["p19_native_library_sha256"]) == 3
    assert len(result["diagnostic_runtime_source_sha256"]) == 6


def test_wrong_head_rejected(tmp_path):
    with pytest.raises(manifest.BindingError, match="implementation HEAD"):
        verify(tmp_path, actual_head="wrong")


def test_wrong_overlay_rejected(tmp_path):
    root, _, runner, static_zip = make_bound_tree(tmp_path)
    wrong = tmp_path / "wrong"; wrong.mkdir()
    with pytest.raises(manifest.BindingError, match="overlay expected"):
        manifest.verify_execution_bindings(root=root, implementation_sha="head",
            actual_head="head", overlay=wrong, runner_path=runner,
            static_evidence_path=static_zip)


def test_missing_overlay_rejected(tmp_path):
    root, overlay, runner, static_zip = make_bound_tree(tmp_path)
    (overlay / "setup.bash").unlink()
    with pytest.raises(manifest.BindingError, match="missing accepted overlay"):
        manifest.verify_execution_bindings(root=root, implementation_sha="head",
            actual_head="head", overlay=overlay, runner_path=runner,
            static_evidence_path=static_zip)


@pytest.mark.parametrize("mode", ["altered", "missing"])
def test_each_native_library_failure_is_rejected(tmp_path, mode):
    root, overlay, runner, static_zip = make_bound_tree(tmp_path)
    for name in list(manifest.P19_LIBRARY_HASHES):
        path = overlay / "aegisinspect_p19_eval/lib" / name
        original = path.read_bytes()
        path.write_bytes(b"altered") if mode == "altered" else path.unlink()
        with pytest.raises(manifest.BindingError, match=name):
            manifest.verify_execution_bindings(root=root, implementation_sha="head",
                actual_head="head", overlay=overlay, runner_path=runner,
                static_evidence_path=static_zip)
        write(path, original)


def test_wrong_schema_identity_rejected(tmp_path):
    root, overlay, runner, static_zip = make_bound_tree(tmp_path)
    relative = next(x for x in manifest.DIAGNOSTIC_SOURCE_HASHES if x.endswith(".schema.json"))
    path = root / relative
    path.write_text('{"$id":"wrong"}')
    manifest.DIAGNOSTIC_SOURCE_HASHES[relative] = manifest.sha256_file(path)
    with pytest.raises(manifest.BindingError, match="diagnostic schema expected"):
        manifest.verify_execution_bindings(root=root, implementation_sha="head",
            actual_head="head", overlay=overlay, runner_path=runner,
            static_evidence_path=static_zip)


@pytest.mark.parametrize("mode", ["altered", "missing"])
def test_each_diagnostic_source_failure_is_rejected(tmp_path, mode):
    root, overlay, runner, static_zip = make_bound_tree(tmp_path)
    for relative in list(manifest.DIAGNOSTIC_SOURCE_HASHES):
        path = root / relative
        original = path.read_bytes()
        path.write_bytes(b"altered") if mode == "altered" else path.unlink()
        with pytest.raises(manifest.BindingError, match=Path(relative).name):
            manifest.verify_execution_bindings(root=root, implementation_sha="head",
                actual_head="head", overlay=overlay, runner_path=runner,
                static_evidence_path=static_zip)
        write(path, original)


def test_wrong_static_evidence_rejected(tmp_path):
    root, overlay, runner, static_zip = make_bound_tree(tmp_path)
    static_zip.write_bytes(b"wrong")
    with pytest.raises(manifest.BindingError, match="static evidence package"):
        manifest.verify_execution_bindings(root=root, implementation_sha="head",
            actual_head="head", overlay=overlay, runner_path=runner,
            static_evidence_path=static_zip)


def prior_manifest():
    return {
        "instrumentation_provenance": {"gz_sim": {"v": 1}, "gz_sensors": {"v": 1}},
        "relevant_git_shas": {},
        **{key: f"frozen:{key}" for key in manifest.SCIENTIFIC_KEYS},
    }


def test_production_manifest_adds_exact_provenance_and_preserves_science(tmp_path):
    bindings = verify(tmp_path)
    prior = prior_manifest()
    new, comparison = manifest.build_runtime_manifest(
        prior=prior, execution_bindings=bindings,
        host_identity_sha256="a" * 64, host_capability_path=tmp_path / "host.zip",
        host_capability_sha256="b" * 64, static_evidence_path=tmp_path / "static.zip",
        creation_timestamp="2026-09-20T00:00:00Z")
    assert new["diagnostic_execution_provenance"] == bindings
    assert new["relevant_git_shas"]["p19_runtime_candidate"] == "head"
    assert comparison["scientific_field_differences"] == 0
    assert comparison["scientific_behavior_fields_changed"] is False
    assert comparison["provenance_classification"] == "ENGINEERING_PROVENANCE_ADDITION"
    assert manifest.canonical_json_bytes(new) == manifest.canonical_json_bytes(new)


def test_missing_required_provenance_block_rejected(tmp_path):
    bindings = verify(tmp_path)
    del bindings["diagnostic_runtime_source_sha256"]
    with pytest.raises(manifest.BindingError, match="missing required execution provenance"):
        manifest.build_runtime_manifest(prior=prior_manifest(), execution_bindings=bindings,
            host_identity_sha256="a" * 64, host_capability_path=tmp_path / "host.zip",
            host_capability_sha256="b" * 64, static_evidence_path=tmp_path / "static.zip",
            creation_timestamp="2026-09-20T00:00:00Z")
