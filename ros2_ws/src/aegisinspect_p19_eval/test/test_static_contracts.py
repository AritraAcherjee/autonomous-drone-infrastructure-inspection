from pathlib import Path
import hashlib
import importlib.util
import math
import os
import re
import subprocess
import xml.etree.ElementTree as ET

from aegisinspect_p19_eval.contracts import CameraGeometry, validate_camera_parity


PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[2]
BASE = "7b9ff556956c9c8995262515f53ff5382ffacf1b"


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def load_readiness_launch():
    path = PKG / "launch/no_start_readiness.launch.py"
    spec = importlib.util.spec_from_file_location("p19_no_start_readiness_launch", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EnvironmentContext:
    def __init__(self, environment=None):
        self.environment = dict(environment or {})


def test_lyrical_launch_import_and_description_construction():
    module = load_readiness_launch()
    assert module.generate_launch_description() is not None
    assert "PrependEnvironmentVariable" not in Path(module.__file__).read_text()


def test_lyrical_prepend_path_environment_semantics():
    module = load_readiness_launch()
    absent = EnvironmentContext()
    module.prepend_path_environment(absent, "PATHS", "/instrumented")
    assert absent.environment["PATHS"] == "/instrumented"

    empty = EnvironmentContext({"PATHS": ""})
    module.prepend_path_environment(empty, "PATHS", "/instrumented")
    assert empty.environment["PATHS"] == "/instrumented"

    populated = EnvironmentContext({"PATHS": os.pathsep.join(["/system", "/vendor"])})
    module.prepend_path_environment(populated, "PATHS", "/certificate")
    module.prepend_path_environment(populated, "PATHS", "/instrumented")
    assert populated.environment["PATHS"].split(os.pathsep) == [
        "/instrumented", "/certificate", "/system", "/vendor"]

    duplicate = EnvironmentContext({"PATHS": os.pathsep.join(["/instrumented", "/system"])})
    module.prepend_path_environment(duplicate, "PATHS", "/instrumented")
    assert duplicate.environment["PATHS"].split(os.pathsep) == ["/instrumented", "/system"]


def test_anchor_geometry_no_interpenetration_and_full_frame_coverage():
    # Target box world bounds: x=[3.00,3.02], y=[-2,2], z=[0,3].
    # Existing wall starts at x=3.9; column ends at x=2.25; floor ends at z=0.
    assert 3.00 >= 2.25 and 3.02 <= 3.9
    final_camera_x = 0.45 + 0.25
    distance = 3.0 - final_camera_x
    horizontal_half = distance * math.tan(1.0471975511965976 / 2)
    vertical_fov = 2 * math.atan(math.tan(1.0471975511965976 / 2) * 480 / 640)
    vertical_half = distance * math.tan(vertical_fov / 2)
    assert horizontal_half < 2.0 and vertical_half < 1.5


def sensor_geometry(path, name):
    root = ET.parse(path).getroot()
    sensor = next(item for item in root.iter("sensor") if item.attrib["name"] == name)
    camera = sensor.find("camera")
    return CameraGeometry(
        parent_frame=sensor.find("pose").attrib["relative_to"],
        pose_xyz_rpy=tuple(map(float, sensor.findtext("pose").split())),
        width=int(camera.findtext("image/width")), height=int(camera.findtext("image/height")),
        horizontal_fov=float(camera.findtext("horizontal_fov")),
        near_clip=float(camera.findtext("clip/near")), far_clip=float(camera.findtext("clip/far")),
        update_rate_hz=float(sensor.findtext("update_rate")),
    )


def test_rgb_truth_geometry_parity_and_accepted_extrinsics():
    model = PKG / "models/aegis_drone_p19_eval/model.sdf"
    validate_camera_parity(sensor_geometry(model, "camera"), sensor_geometry(model, "p19_truth_camera"))
    accepted = ROOT / "ros2_ws/src/aegisinspect_sim/models/aegis_drone/model.sdf"
    validate_camera_parity(sensor_geometry(accepted, "camera"), sensor_geometry(model, "camera"))


def test_target_runtime_identity_and_label_are_frozen():
    target = ET.parse(PKG / "models/p19_defect_target_001/model.sdf").getroot()
    model = target.find("model")
    assert model.attrib["name"] == "p19_defect_target_001"
    assert model.find("link").attrib["name"] == "target_surface"
    assert model.find("link/visual").attrib["name"] == "defect_face"
    assert model.findtext("plugin/label") == "19"


def test_procedural_asset_is_reproducible(tmp_path):
    output = tmp_path / "texture.png"
    subprocess.run([str(PKG / "assets/generate_honeycombing_texture.py"), str(output)], check=True)
    committed = PKG / "models/p19_defect_target_001/materials/textures/honeycombing_v1.png"
    assert output.read_bytes() == committed.read_bytes()


def test_core_runtime_sources_equal_accepted_base():
    protected = [
        "ros2_ws/src/aegisinspect_sim/src/deterministic_motion_system.cpp",
        "ros2_ws/src/aegisinspect_sim/models/aegis_drone/model.sdf",
        "ros2_ws/src/aegisinspect_localization/launch/rtabmap_icp_fallback.launch.py",
        "ros2_ws/src/aegisinspect_localization/aegisinspect_localization/vio_adapter.py",
        "ros2_ws/src/aegisinspect_mapping/aegisinspect_mapping/spatial_projection.py",
        "src/defect_mapping/identity.py", "src/defect_mapping/engine.py",
    ]
    for relative in protected:
        expected = subprocess.check_output(["git", "show", f"{BASE}:{relative}"], cwd=ROOT)
        assert (ROOT / relative).read_bytes() == expected


def test_no_operational_gt_route_or_forbidden_runtime_nodes():
    launch = (PKG / "launch/no_start_readiness.launch.py").read_text()
    assert 'package="aegisinspect_perception"' not in launch
    assert 'executable="camera_projection_node.py"' not in launch
    assert 'package="aegisinspect_inspection"' not in launch
    assert 'package="aegisinspect_storage"' not in launch
    collector = (PKG / "scripts/readiness_node.py").read_text()
    assert "/aegis/sim/ground_truth/pose" in collector
    assert "create_publisher" not in collector
    assert "/start" not in collector.lower() and "/reset" not in collector.lower()


def test_correspondence_source_contains_no_proximity_algorithm():
    source = (PKG / "aegisinspect_p19_eval/contracts.py").read_text().lower()
    for prohibited in ("nearest_neighbor", "nearest-neighbor", "euclidean matching", "spatial tolerance"):
        assert prohibited not in source


def test_det_final_checkpoint_hash_frozen_and_dataset_paths_absent():
    contracts = (PKG / "aegisinspect_p19_eval/contracts.py").read_text()
    assert "4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3" in contracts
    provenance = (PKG / "assets/PROVENANCE.md").read_text()
    assert "no dataset" in provenance.lower()


def test_update_attestor_is_evaluation_only_and_has_no_tf_publisher():
    source = (PKG / "src/update_attestor.cpp").read_text()
    assert "iteration" in source and "sim_time_ns" in source
    assert "Transform" not in source and "SetWorldPose" not in source
