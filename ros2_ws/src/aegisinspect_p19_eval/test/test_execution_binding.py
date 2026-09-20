from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

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
    plugin = write(tmp_path / "instrumented/libgz-sim-sensors-system.so.10.5.0",
                   b"instrumented sensors")
    manifest.EXPECTED_SENSORS_PATH = plugin.resolve()
    manifest.EXPECTED_SENSORS_CANONICAL_PATH = plugin.resolve()
    manifest.EXPECTED_SENSORS_SHA256 = manifest.sha256_file(plugin)
    world = (
        '<sdf version="1.12"><world name="w">'
        f'<plugin filename="{plugin.resolve()}" '
        f'name="{manifest.EXPECTED_SENSORS_NAME}">'
        f'<render_engine>{manifest.EXPECTED_RENDER_ENGINE}</render_engine>'
        '</plugin></world></sdf>\n'
    ).encode()
    write(root / manifest.SOURCE_WORLD_RELATIVE, world)
    write(overlay / manifest.INSTALLED_WORLD_RELATIVE, world)
    manifest.STATIC_EVIDENCE_SHA256 = manifest.sha256_file(static_zip)
    manifest.ACCEPTED_OVERLAY = overlay.resolve()
    return root, overlay, runner, static_zip


@pytest.fixture(autouse=True)
def restore_constants():
    libraries = copy.deepcopy(manifest.P19_LIBRARY_HASHES)
    sources = copy.deepcopy(manifest.DIAGNOSTIC_SOURCE_HASHES)
    overlay = manifest.ACCEPTED_OVERLAY
    static = manifest.STATIC_EVIDENCE_SHA256
    sensors_path = manifest.EXPECTED_SENSORS_PATH
    sensors_canonical = manifest.EXPECTED_SENSORS_CANONICAL_PATH
    sensors_hash = manifest.EXPECTED_SENSORS_SHA256
    yield
    manifest.P19_LIBRARY_HASHES.clear(); manifest.P19_LIBRARY_HASHES.update(libraries)
    manifest.DIAGNOSTIC_SOURCE_HASHES.clear(); manifest.DIAGNOSTIC_SOURCE_HASHES.update(sources)
    manifest.ACCEPTED_OVERLAY = overlay
    manifest.STATIC_EVIDENCE_SHA256 = static
    manifest.EXPECTED_SENSORS_PATH = sensors_path
    manifest.EXPECTED_SENSORS_CANONICAL_PATH = sensors_canonical
    manifest.EXPECTED_SENSORS_SHA256 = sensors_hash


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
    selection = result["gz_sim_sensors_system_selection"]
    assert selection["result"] == "PASS"
    assert selection["sensors_plugin_count"] == 1
    assert selection["sensors_plugin_name"] == manifest.EXPECTED_SENSORS_NAME
    assert selection["sensors_requested_path_is_absolute"] is True
    assert selection["sensors_requested_canonical_path"] == str(
        manifest.EXPECTED_SENSORS_CANONICAL_PATH
    )
    assert selection["sensors_requested_sha256"] == manifest.EXPECTED_SENSORS_SHA256
    assert selection["render_engine"] == "ogre2"
    assert selection["source_installed_world_bytes_match"] is True


def _world_paths(root, overlay):
    return root / manifest.SOURCE_WORLD_RELATIVE, overlay / manifest.INSTALLED_WORLD_RELATIVE


def _rewrite_world(path: Path, *, filename=None, name=None, render_engine=None,
                   duplicate=False):
    tree = ET.parse(path)
    world = tree.getroot().find("./world")
    plugin = world.find("plugin")
    if filename is not None:
        plugin.set("filename", filename)
    if name is not None:
        plugin.set("name", name)
    if render_engine is not None:
        plugin.find("render_engine").text = render_engine
    if duplicate:
        world.append(copy.deepcopy(plugin))
    tree.write(path, encoding="utf-8", xml_declaration=False)


@pytest.mark.parametrize("requested", [
    "gz-sim-sensors-system",
    "libgz-sim-sensors-system.so",
    "libgz-sim-sensors-system.so.10",
    "relative/libgz-sim-sensors-system.so.10.5.0",
])
def test_non_absolute_or_logical_sensor_requests_rejected(tmp_path, requested):
    root, overlay, _, _ = make_bound_tree(tmp_path)
    source, installed = _world_paths(root, overlay)
    _rewrite_world(source, filename=requested)
    installed.write_bytes(source.read_bytes())
    with pytest.raises(manifest.BindingError, match="not absolute"):
        manifest.verify_gz_sim_sensors_system_selection(root=root, overlay=overlay)


def test_wrong_absolute_or_vendor_sensor_path_rejected(tmp_path):
    root, overlay, _, _ = make_bound_tree(tmp_path)
    source, installed = _world_paths(root, overlay)
    for requested in [
        str(tmp_path / "wrong/libgz-sim-sensors-system.so.10.5.0"),
        "/opt/ros/lyrical/opt/gz_sim_vendor/lib/gz-sim-10/plugins/"
        "libgz-sim-sensors-system.so.10.5.0",
    ]:
        _rewrite_world(source, filename=requested)
        installed.write_bytes(source.read_bytes())
        with pytest.raises(manifest.BindingError, match="Sensors plugin path expected"):
            manifest.verify_gz_sim_sensors_system_selection(root=root, overlay=overlay)


def test_missing_or_wrong_hash_sensor_plugin_rejected(tmp_path):
    root, overlay, _, _ = make_bound_tree(tmp_path)
    plugin = manifest.EXPECTED_SENSORS_PATH
    plugin.unlink()
    with pytest.raises(manifest.BindingError, match="missing requested Sensors plugin"):
        manifest.verify_gz_sim_sensors_system_selection(root=root, overlay=overlay)
    plugin.write_bytes(b"wrong")
    with pytest.raises(manifest.BindingError, match="requested Sensors plugin SHA-256"):
        manifest.verify_gz_sim_sensors_system_selection(root=root, overlay=overlay)


def test_unexpected_canonical_target_rejected(tmp_path):
    root, overlay, _, _ = make_bound_tree(tmp_path)
    manifest.EXPECTED_SENSORS_CANONICAL_PATH = tmp_path / "accepted/elsewhere.so"
    with pytest.raises(manifest.BindingError, match="canonical path"):
        manifest.verify_gz_sim_sensors_system_selection(root=root, overlay=overlay)


@pytest.mark.parametrize("mode", ["zero", "duplicate", "wrong_name"])
def test_sensor_declaration_cardinality_and_name_rejected(tmp_path, mode):
    root, overlay, _, _ = make_bound_tree(tmp_path)
    source, installed = _world_paths(root, overlay)
    if mode == "zero":
        tree = ET.parse(source); world = tree.getroot().find("./world")
        world.remove(world.find("plugin")); tree.write(source)
    elif mode == "duplicate":
        _rewrite_world(source, duplicate=True)
    else:
        _rewrite_world(source, name="wrong::Sensors")
    installed.write_bytes(source.read_bytes())
    with pytest.raises(manifest.BindingError, match="exactly one"):
        manifest.verify_gz_sim_sensors_system_selection(root=root, overlay=overlay)


def test_wrong_or_missing_render_engine_rejected(tmp_path):
    root, overlay, _, _ = make_bound_tree(tmp_path)
    source, installed = _world_paths(root, overlay)
    _rewrite_world(source, render_engine="ogre")
    installed.write_bytes(source.read_bytes())
    with pytest.raises(manifest.BindingError, match="render engine"):
        manifest.verify_gz_sim_sensors_system_selection(root=root, overlay=overlay)
    tree = ET.parse(source); tree.getroot().find("./world/plugin").remove(
        tree.getroot().find("./world/plugin/render_engine"))
    tree.write(source); installed.write_bytes(source.read_bytes())
    with pytest.raises(manifest.BindingError, match="render engine"):
        manifest.verify_gz_sim_sensors_system_selection(root=root, overlay=overlay)


def test_source_installed_world_mismatch_rejected(tmp_path):
    root, overlay, _, _ = make_bound_tree(tmp_path)
    _, installed = _world_paths(root, overlay)
    installed.write_bytes(installed.read_bytes() + b" ")
    with pytest.raises(manifest.BindingError, match="world bytes differ"):
        manifest.verify_gz_sim_sensors_system_selection(root=root, overlay=overlay)


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
    assert new["scene_sha256"] == prior["scene_sha256"]
    selection = new["diagnostic_execution_provenance"][
        "gz_sim_sensors_system_selection"
    ]
    assert selection["result"] == "PASS"
    assert selection["source_world_sha256"] == selection["installed_world_sha256"]
    assert manifest.canonical_json_bytes(new) == manifest.canonical_json_bytes(new)


def test_missing_required_provenance_block_rejected(tmp_path):
    bindings = verify(tmp_path)
    del bindings["diagnostic_runtime_source_sha256"]
    with pytest.raises(manifest.BindingError, match="missing required execution provenance"):
        manifest.build_runtime_manifest(prior=prior_manifest(), execution_bindings=bindings,
            host_identity_sha256="a" * 64, host_capability_path=tmp_path / "host.zip",
            host_capability_sha256="b" * 64, static_evidence_path=tmp_path / "static.zip",
            creation_timestamp="2026-09-20T00:00:00Z")


def test_missing_or_altered_sensor_selection_provenance_rejected(tmp_path):
    bindings = verify(tmp_path)
    del bindings["gz_sim_sensors_system_selection"]
    with pytest.raises(manifest.BindingError, match="missing required execution provenance"):
        manifest.build_runtime_manifest(prior=prior_manifest(), execution_bindings=bindings,
            host_identity_sha256="a" * 64, host_capability_path=tmp_path / "host.zip",
            host_capability_sha256="b" * 64, static_evidence_path=tmp_path / "static.zip",
            creation_timestamp="2026-09-20T00:00:00Z")

    bindings = verify(tmp_path)
    bindings["gz_sim_sensors_system_selection"]["result"] = "FAIL"
    with pytest.raises(manifest.BindingError, match="selection provenance result"):
        manifest.build_runtime_manifest(prior=prior_manifest(), execution_bindings=bindings,
            host_identity_sha256="a" * 64, host_capability_path=tmp_path / "host.zip",
            host_capability_sha256="b" * 64, static_evidence_path=tmp_path / "static.zip",
            creation_timestamp="2026-09-20T00:00:00Z")
