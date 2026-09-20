"""Pure fail-closed contracts for the P19 correspondence experiment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


GT_ID = "P19-GT-DEFECT-001"
TARGET_CLASS = "Honeycombing"
TARGET_LABEL = 19
TARGET_MODEL = "p19_defect_target_001"
TARGET_LINK = "target_surface"
TARGET_VISUAL = "defect_face"
TARGET_ANCHOR = (3.0, 0.0, 1.5)
WORLD_FRAME = "world"
MAP_FRAME = "map"
CHECKPOINT_SHA256 = (
    "4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3"
)
MANIFEST_SCHEMA = "aegisinspect.p19.pre_start_manifest.v1"
RECEIPT_SCHEMA = "aegisinspect.p19.exposure_receipt.v1"
BINDING_RULE = "full-frame-target-label-and-explicit-observation-token-v1"
CORRESPONDENCE_RULE = "explicit-id-chain-only-no-coordinate-input-v1"
ALIGNMENT_RULE = "first-exact-positive-startup-world-map-base-pair-v1"
EXPOSURE_RULE = (
    "first-original-rgbd-exposure-at-or-after-completion-plus-1s-within-2s-v1"
)


class ContractError(ValueError):
    """Raised whenever evaluation evidence must fail closed."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ContractError(f"{name} must be a lowercase SHA-256")
    if any(c not in "0123456789abcdef" for c in value):
        raise ContractError(f"{name} must be a lowercase SHA-256")
    return value


def require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ContractError(f"{name} must be a nonempty canonical string")
    return value


def require_finite(value: object, name: str) -> float:
    if type(value) not in {int, float} or not math.isfinite(float(value)):
        raise ContractError(f"{name} must be finite")
    return float(value)


def validate_unique_ids(values: Iterable[str], name: str) -> tuple[str, ...]:
    normalized = tuple(require_text(value, name) for value in values)
    if len(set(normalized)) != len(normalized):
        raise ContractError(f"duplicate {name}")
    return normalized


def validate_target_record(record: Mapping[str, Any]) -> None:
    expected = {
        "gt_defect_id": GT_ID,
        "target_class": TARGET_CLASS,
        "coordinate_frame": WORLD_FRAME,
        "scene_model": TARGET_MODEL,
        "scene_link": TARGET_LINK,
        "scene_visual": TARGET_VISUAL,
        "coordinate_convention": "center of authored front target surface",
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise ContractError(f"frozen target field mismatch: {key}")
    xyz = tuple(require_finite(record.get(key), key) for key in ("x_m", "y_m", "z_m"))
    if xyz != TARGET_ANCHOR:
        raise ContractError("frozen target anchor mismatch")


FORBIDDEN_DATA_REFERENCES = (
    "GYU-DET-TEST",
    "GYU_DET_TEST",
    "CODEBRIM",
    "/data/raw/",
    "\\data\\raw\\",
)


def reject_locked_data_references(value: Any) -> None:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False)
    if any(token.casefold() in text.casefold() for token in FORBIDDEN_DATA_REFERENCES):
        raise ContractError("locked or reserved dataset reference is prohibited")


REQUIRED_MANIFEST_FIELDS = frozenset({
    "schema", "experiment_id", "gt_defect_id", "target_class",
    "gt_world_x", "gt_world_y", "gt_world_z", "gt_coordinate_convention",
    "target_scene_identity", "scene_model", "scene_link", "scene_visual",
    "visual_asset_path", "visual_asset_sha256", "asset_generator_sha256",
    "material_sha256", "model_sha256", "asset_provenance",
    "det_final_v1_checkpoint_sha256", "detector_inference_config_sha256",
    "p13_trajectory_sha256", "p13_config_sha256", "camera_config_sha256",
    "scene_sha256", "observation_to_gt_binding_rule",
    "correspondence_generation_rule", "t_map_from_world_source_rule",
    "exposure_selection_rule", "timeout_failure_rules", "relevant_git_shas",
    "creation_timestamp",
})


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    missing = REQUIRED_MANIFEST_FIELDS - set(manifest)
    extra_hash = "manifest_sha256" in manifest
    if missing:
        raise ContractError(f"manifest missing fields: {sorted(missing)}")
    if extra_hash:
        raise ContractError("manifest hash must be detached")
    if manifest["schema"] != MANIFEST_SCHEMA:
        raise ContractError("manifest schema mismatch")
    validate_target_record({
        "gt_defect_id": manifest["gt_defect_id"],
        "target_class": manifest["target_class"],
        "coordinate_frame": WORLD_FRAME,
        "scene_model": manifest["scene_model"],
        "scene_link": manifest["scene_link"],
        "scene_visual": manifest["scene_visual"],
        "coordinate_convention": manifest["gt_coordinate_convention"],
        "x_m": manifest["gt_world_x"],
        "y_m": manifest["gt_world_y"],
        "z_m": manifest["gt_world_z"],
    })
    if manifest["target_scene_identity"] != TARGET_MODEL:
        raise ContractError("target scene identity mismatch")
    for name in (
        "visual_asset_sha256", "asset_generator_sha256", "material_sha256",
        "model_sha256", "detector_inference_config_sha256",
        "p13_trajectory_sha256", "p13_config_sha256", "camera_config_sha256",
        "scene_sha256",
    ):
        require_sha256(manifest[name], name)
    if manifest["det_final_v1_checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ContractError("DET-FINAL-v1 checkpoint hash mismatch")
    rules = {
        "observation_to_gt_binding_rule": BINDING_RULE,
        "correspondence_generation_rule": CORRESPONDENCE_RULE,
        "t_map_from_world_source_rule": ALIGNMENT_RULE,
        "exposure_selection_rule": EXPOSURE_RULE,
    }
    for name, expected in rules.items():
        if manifest[name] != expected:
            raise ContractError(f"frozen rule mismatch: {name}")
    reject_locked_data_references(manifest)


def verify_detached_seal(manifest_bytes: bytes, seal_text: str) -> None:
    expected = require_sha256(seal_text.strip(), "detached manifest seal")
    if sha256_bytes(manifest_bytes) != expected:
        raise ContractError("manifest changed after sealing")


@dataclass(frozen=True)
class CameraGeometry:
    parent_frame: str
    pose_xyz_rpy: tuple[float, float, float, float, float, float]
    width: int
    height: int
    horizontal_fov: float
    near_clip: float
    far_clip: float
    update_rate_hz: float


def validate_camera_parity(rgb: CameraGeometry, truth: CameraGeometry) -> None:
    if rgb != truth:
        raise ContractError("RGB-D/truth camera geometry mismatch")


@dataclass(frozen=True)
class TruthSummary:
    total_pixels: int
    target_pixels: int
    background_pixels: int
    unresolved_pixels: int
    other_target_pixels: int


def summarize_truth_labels(labels: Sequence[int], *, target_label: int = TARGET_LABEL) -> TruthSummary:
    if not labels:
        raise ContractError("truth label buffer is empty")
    target = sum(value == target_label for value in labels)
    background = sum(value == 0 for value in labels)
    unresolved = sum(value < 0 or value > 255 for value in labels)
    other = len(labels) - target - background - unresolved
    result = TruthSummary(len(labels), target, background, unresolved, other)
    if result.target_pixels != result.total_pixels:
        raise ContractError("truth exposure is not full-target")
    if result.background_pixels or result.unresolved_pixels or result.other_target_pixels:
        raise ContractError("truth exposure contains non-target pixels")
    return result


@dataclass(frozen=True)
class UpdateAttestation:
    iteration: int
    sim_time_ns: int
    paused: bool
    render_event: int
    render_event_type: str


def parse_update_attestation(text: str) -> UpdateAttestation:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError("invalid update attestation JSON") from exc
    if set(value) != {"iteration", "sim_time_ns", "paused", "render_event", "render_event_type"}:
        raise ContractError("update attestation fields mismatch")
    if type(value["iteration"]) is not int or value["iteration"] < 1:
        raise ContractError("invalid simulation iteration")
    if type(value["sim_time_ns"]) is not int or value["sim_time_ns"] <= 0:
        raise ContractError("invalid simulation timestamp")
    if value["paused"] is not False:
        raise ContractError("paused update cannot attest an exposure")
    if type(value["render_event"]) is not int or value["render_event"] < 1:
        raise ContractError("invalid render event sequence")
    if value["render_event_type"] != "gz::sim::events::PostRender":
        raise ContractError("attestation is not sourced from an explicit post-render event")
    return UpdateAttestation(**value)


@dataclass(frozen=True)
class ExposureReceipt:
    experiment_id: str
    run_id: str
    observation_token: str
    rgb_sensor_identity: str
    truth_sensor_identity: str
    simulation_iteration: int
    render_identity: str
    timestamp_ns: int
    frame_id: str
    width: int
    height: int
    encoding: str
    step: int
    rgb_message_sha256: str
    rgb_pixel_sha256: str
    depth_message_sha256: str
    camera_info_sha256: str
    truth_label_buffer_sha256: str
    scene_state_sha256: str
    gt_defect_id: str
    scene_model: str
    scene_link: str
    scene_visual: str
    binding_rule_version: str
    truth_summary: TruthSummary


def validate_receipt(receipt: ExposureReceipt, attestation: UpdateAttestation) -> None:
    for name in ("experiment_id", "run_id", "observation_token", "render_identity"):
        require_text(getattr(receipt, name), name)
    for name in (
        "rgb_message_sha256", "rgb_pixel_sha256", "depth_message_sha256",
        "camera_info_sha256", "truth_label_buffer_sha256", "scene_state_sha256",
    ):
        require_sha256(getattr(receipt, name), name)
    if receipt.timestamp_ns != attestation.sim_time_ns:
        raise ContractError("exposure does not resolve to the attested simulation update")
    if receipt.simulation_iteration != attestation.iteration:
        raise ContractError("simulation iteration mismatch")
    expected_render = f"gz-post-render-{attestation.render_event}-update-{attestation.iteration}"
    if receipt.render_identity != expected_render:
        raise ContractError("render/update identity mismatch")
    if receipt.gt_defect_id != GT_ID or receipt.binding_rule_version != BINDING_RULE:
        raise ContractError("receipt target binding mismatch")
    if (receipt.scene_model, receipt.scene_link, receipt.scene_visual) != (
        TARGET_MODEL, TARGET_LINK, TARGET_VISUAL
    ):
        raise ContractError("runtime target identity mismatch")
    if receipt.frame_id != "camera_optical_frame":
        raise ContractError("unexpected RGB frame")
    if (receipt.width, receipt.height, receipt.step) != (640, 480, 1920):
        raise ContractError("unexpected RGB geometry")
    if receipt.encoding.lower() not in {"rgb8", "bgr8"}:
        raise ContractError("unexpected RGB encoding")
    if receipt.truth_summary.target_pixels != receipt.truth_summary.total_pixels:
        raise ContractError("receipt truth is not full-target")
    if any((receipt.truth_summary.background_pixels,
            receipt.truth_summary.unresolved_pixels,
            receipt.truth_summary.other_target_pixels)):
        raise ContractError("receipt truth contains non-target pixels")


def validate_consecutive_receipts(receipts: Sequence[ExposureReceipt]) -> None:
    if len(receipts) < 20:
        raise ContractError("fewer than 20 eligible paired receipts")
    tokens = validate_unique_ids((item.observation_token for item in receipts), "observation_token")
    del tokens
    previous_stamp = 0
    previous_iteration = 0
    for item in receipts:
        if item.timestamp_ns <= previous_stamp:
            raise ContractError("duplicate or restarted timestamp")
        if item.simulation_iteration <= previous_iteration:
            raise ContractError("duplicate or restarted simulation iteration")
        previous_stamp = item.timestamp_ns
        previous_iteration = item.simulation_iteration


def explicit_correspondence(*, p15_defect_id: str, creator_observation_id: str,
                            detection_id: str, inference_detection_id: str,
                            inference_observation_token: str,
                            certificate_observation_token: str,
                            gt_defect_id: str, estimated_class: str,
                            gt_class: str, detection_count: int,
                            contributing_observation_ids: Sequence[str],
                            **unexpected: Any) -> Mapping[str, str]:
    if unexpected:
        raise ContractError("coordinate or unsupported matching inputs are prohibited")
    for value, name in (
        (p15_defect_id, "p15_defect_id"),
        (creator_observation_id, "creator_observation_id"),
        (detection_id, "detection_id"),
        (inference_observation_token, "observation_token"),
    ):
        require_text(value, name)
    if detection_count != 1:
        raise ContractError("exactly one future detector result is required")
    if tuple(contributing_observation_ids) != (creator_observation_id,):
        raise ContractError("estimate must have exactly one contributing observation")
    if creator_observation_id != detection_id or detection_id != inference_detection_id:
        raise ContractError("estimate/detection identity chain mismatch")
    if inference_observation_token != certificate_observation_token:
        raise ContractError("observation token/certificate mismatch")
    if gt_defect_id != GT_ID:
        raise ContractError("GT identity mismatch")
    if gt_class != TARGET_CLASS or estimated_class != gt_class:
        raise ContractError("exact GT/estimated class agreement required")
    return {"estimated_defect_id": p15_defect_id, "gt_defect_id": gt_defect_id}


def quaternion_rotation(q: Sequence[float]) -> tuple[tuple[float, float, float], ...]:
    if len(q) != 4:
        raise ContractError("quaternion must have four components")
    x, y, z, w = (require_finite(v, "quaternion") for v in q)
    norm = math.sqrt(x*x + y*y + z*z + w*w)
    if norm <= 1e-12:
        raise ContractError("degenerate quaternion")
    x, y, z, w = (v / norm for v in (x, y, z, w))
    return (
        (1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)),
        (2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)),
        (2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)),
    )


def pose_matrix(position: Sequence[float], quaternion: Sequence[float]) -> tuple[tuple[float, ...], ...]:
    if len(position) != 3:
        raise ContractError("position must have three components")
    p = tuple(require_finite(v, "position") for v in position)
    r = quaternion_rotation(quaternion)
    return tuple(tuple(r[i][j] for j in range(3)) + (p[i],) for i in range(3)) + ((0.0, 0.0, 0.0, 1.0),)


def rigid_inverse(matrix: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
    validate_rigid_se3(matrix)
    r = tuple(tuple(float(matrix[i][j]) for j in range(3)) for i in range(3))
    t = tuple(float(matrix[i][3]) for i in range(3))
    rt = tuple(tuple(r[j][i] for j in range(3)) for i in range(3))
    ti = tuple(-sum(rt[i][j] * t[j] for j in range(3)) for i in range(3))
    return tuple(rt[i] + (ti[i],) for i in range(3)) + ((0.0, 0.0, 0.0, 1.0),)


def matmul(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(sum(float(a[i][k]) * float(b[k][j]) for k in range(4))
                       for j in range(4)) for i in range(4))


def determinant3(r: Sequence[Sequence[float]]) -> float:
    return (r[0][0]*(r[1][1]*r[2][2]-r[1][2]*r[2][1])
            - r[0][1]*(r[1][0]*r[2][2]-r[1][2]*r[2][0])
            + r[0][2]*(r[1][0]*r[2][1]-r[1][1]*r[2][0]))


def validate_rigid_se3(matrix: Sequence[Sequence[float]]) -> None:
    if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise ContractError("transform must be 4x4")
    if any(not math.isfinite(float(v)) for row in matrix for v in row):
        raise ContractError("transform must be finite")
    if any(abs(float(matrix[3][i]) - expected) > 1e-9
           for i, expected in enumerate((0.0, 0.0, 0.0, 1.0))):
        raise ContractError("invalid homogeneous bottom row")
    r = tuple(tuple(float(matrix[i][j]) for j in range(3)) for i in range(3))
    for i in range(3):
        for j in range(3):
            dot = sum(r[k][i] * r[k][j] for k in range(3))
            if abs(dot - (1.0 if i == j else 0.0)) > 1e-8:
                raise ContractError("rotation is not orthonormal")
    if abs(determinant3(r) - 1.0) > 1e-8:
        raise ContractError("rotation determinant is not +1")


def startup_alignment(*, timestamp_ns: int, world_base_frame: str,
                      map_base_frame: str, world_from_base: Sequence[Sequence[float]],
                      map_from_base: Sequence[Sequence[float]], selection_index: int) -> tuple[tuple[float, ...], ...]:
    if type(timestamp_ns) is not int or timestamp_ns <= 0:
        raise ContractError("startup timestamp must be positive")
    if selection_index != 0:
        raise ContractError("alignment must use the first valid startup pair")
    if world_base_frame != "base_link" or map_base_frame != "base_link":
        raise ContractError("startup poses must describe the same base_link")
    validate_rigid_se3(world_from_base)
    validate_rigid_se3(map_from_base)
    result = matmul(map_from_base, rigid_inverse(world_from_base))
    validate_rigid_se3(result)
    return result


def receipt_as_dict(receipt: ExposureReceipt) -> Mapping[str, Any]:
    value = asdict(receipt)
    value["schema"] = RECEIPT_SCHEMA
    return value
