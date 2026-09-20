#!/usr/bin/env python3
"""Create and verify the detached-seal P19 pre-START manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "ros2_ws/src/aegisinspect_p19_eval"
sys.path.insert(0, str(PKG))

from aegisinspect_p19_eval.contracts import (  # noqa: E402
    ALIGNMENT_RULE, BINDING_RULE, CHECKPOINT_SHA256, CORRESPONDENCE_RULE,
    EXPOSURE_RULE, GT_ID, MANIFEST_SCHEMA, TARGET_ANCHOR, TARGET_CLASS,
    TARGET_LINK, TARGET_MODEL, TARGET_VISUAL, canonical_json_bytes,
    sha256_file, validate_manifest, verify_detached_seal,
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--creation-timestamp", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seal", type=Path, required=True)
    args = parser.parse_args()
    texture = PKG / "models/p19_defect_target_001/materials/textures/honeycombing_v1.png"
    generator = PKG / "assets/generate_honeycombing_texture.py"
    material_model = PKG / "models/p19_defect_target_001/model.sdf"
    scene = PKG / "worlds/p19_correspondence_readiness.sdf"
    camera = PKG / "models/aegis_drone_p19_eval/model.sdf"
    trajectory = ROOT / "ros2_ws/src/aegisinspect_sim/src/deterministic_motion_system.cpp"
    p13_config = ROOT / "ros2_ws/src/aegisinspect_sim/config/bridge.yaml"
    detector_config = ROOT / "ros2_ws/src/aegisinspect_perception/scripts/detector_projection_node.py"
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "experiment_id": "P19-3D-CORRESPONDENCE-001",
        "gt_defect_id": GT_ID,
        "target_class": TARGET_CLASS,
        "gt_world_x": TARGET_ANCHOR[0], "gt_world_y": TARGET_ANCHOR[1], "gt_world_z": TARGET_ANCHOR[2],
        "gt_coordinate_convention": "center of authored front target surface",
        "target_scene_identity": TARGET_MODEL,
        "scene_model": TARGET_MODEL, "scene_link": TARGET_LINK, "scene_visual": TARGET_VISUAL,
        "visual_asset_path": str(texture.relative_to(ROOT)),
        "visual_asset_sha256": sha256_file(texture),
        "asset_generator_sha256": sha256_file(generator),
        "material_sha256": sha256_file(material_model),
        "model_sha256": sha256_file(material_model),
        "asset_provenance": {
            "kind": "project-authored deterministic procedural evaluation-only texture",
            "generator_version": "P19-HONEYCOMB-PROCEDURAL-v1",
            "seed": 1903001,
            "rights": "AegisInspect project-owned; no dataset or external image input",
        },
        "det_final_v1_checkpoint_sha256": CHECKPOINT_SHA256,
        "detector_inference_config_sha256": sha256_file(detector_config),
        "p13_trajectory_sha256": sha256_file(trajectory),
        "p13_config_sha256": sha256_file(p13_config),
        "camera_config_sha256": sha256_file(camera),
        "scene_sha256": sha256_file(scene),
        "observation_to_gt_binding_rule": BINDING_RULE,
        "correspondence_generation_rule": CORRESPONDENCE_RULE,
        "t_map_from_world_source_rule": ALIGNMENT_RULE,
        "exposure_selection_rule": EXPOSURE_RULE,
        "timeout_failure_rules": {
            "deadline_after_eligibility_s": 2.0,
            "zero_detections": "BLOCKED", "multiple_detections": "BLOCKED",
            "class_mismatch": "BLOCKED", "automatic_retry": False,
        },
        "relevant_git_shas": {
            "accepted_p18_base": "7b9ff556956c9c8995262515f53ff5382ffacf1b",
            "manifest_source_head": git("rev-parse", "HEAD"),
        },
        "creation_timestamp": args.creation_timestamp,
    }
    validate_manifest(manifest)
    payload = canonical_json_bytes(manifest) + b"\n"
    args.output.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    args.seal.write_text(digest + "\n", encoding="utf-8")
    verify_detached_seal(payload, args.seal.read_text(encoding="utf-8"))
    print(digest)


if __name__ == "__main__":
    main()
