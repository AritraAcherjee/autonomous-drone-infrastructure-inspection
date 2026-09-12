# Chat 08 Phase 2: simulated metric depth

**CODE READY / RUNTIME VALIDATION PENDING. Not merge-ready.**

Baseline: `606f04670c53a9b1833a3a5f5bf8121d7e3e9c2a`.
Windows worktree: `C:\Dev\aegisinspect-chat08-codex`.
Branch: `feat/simulated-depth-integration`.
HEAD, main and cached origin/main matched the baseline; worktree was clean.
No remote freshness claim is made from the cached tracking ref.
Codex cannot invoke WSL; no WSL repair or alternate ROS/Gazebo installation was attempted.

## Architecture and implementation

Inspected the 13 ROS packages and manifests/build files, simulation model/world,
bridge YAML, description Xacro, description/simulation/bringup launches,
interface contract, foundation tests/smoke checker, mapping depth geometry and
tests, README and prior implementation reports. The actual geometry core is
`ros2_ws/src/aegisinspect_mapping/aegisinspect_mapping/depth_geometry.py`;
there are no separate implemented `src/depth/` or `src/geometry/` modules.

The existing rig is stationary, with a camera on `camera_link`, an Ogre2 sensors
system, and one `ros_gz_bridge` parameter bridge. The camera originally used
sensor type `camera`. It now uses `rgbd_camera`, retaining the same pose,
640x480 resolution, 60-degree horizontal FOV, 0.1/20 m clip planes, 30 Hz rate,
RGB format and optical frame. One camera element drives color, depth and
CameraInfo; no second calibration, sensor pose or clipping override is added.

| Gazebo transport | ROS topic | ROS type |
|---|---|---|
| `/aegis/sim/sensors/camera/image` | `/aegis/sensors/camera/image_raw` | `sensor_msgs/msg/Image` |
| `/aegis/sim/sensors/camera/depth_image` | `/aegis/perception/depth/image` | `sensor_msgs/msg/Image` |
| `/aegis/sim/sensors/camera/camera_info` | `/aegis/sensors/camera/camera_info` | `sensor_msgs/msg/CameraInfo` |

Only the internal Gazebo RGB topic changes to accommodate RGB-D suffixing.
All frozen ROS sensor topics and /clock remain. TF, world geometry and geometry
core are unchanged. Depth moves from reserved to active perception configuration,
with an explicit pending runtime-validation marker. VIO remains reserved.
No adapter, range conversion, point-cloud bridge or projection node is added.

## Expected semantics and evidence limits

These are source/configuration expectations, **not MSI runtime measurements**:

- [Gazebo Sensors 10 RGB-D implementation](https://github.com/gazebosim/gz-sensors/blob/gz-sensors10/src/RgbdCameraSensor.cc)
  uses one depth renderer for RGB and depth, publishes `/image` and `/depth_image`,
  emits `R_FLOAT32` depth with sensor update time and frame metadata.
- [CameraSensor projection/information implementation](https://github.com/gazebosim/gz-sensors/blob/gz-sensors10/src/CameraSensor.cc)
  derives CameraInfo from the renderer projection when no intrinsics override is supplied.
- [Ogre2 depth renderer](https://github.com/gazebosim/gz-rendering/blob/gz-rendering10/ogre2/src/Ogre2DepthCamera.cc)
  extracts the forward X coordinate as depth; default invalid bounds are infinities.
  Its [depth shader](https://github.com/gazebosim/gz-rendering/blob/gz-rendering10/ogre2/src/media/materials/programs/GLSL/depth_camera_fs.glsl)
  reconstructs view-space position. Forward camera-link X corresponds to optical Z
  under the unchanged tested optical rotation. Thus metric optical-Z is expected.
- [ros_gz image conversion](https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/src/convert/sensor_msgs.cpp)
  maps `R_FLOAT32` to `32FC1`, copies the header and payload. The existing launch
  keeps `override_timestamps_with_wall_time: False` and `use_sim_time: True`.

The upstream branch sources are supporting evidence, not a fingerprint of the
installed MSI packages. Verify their actual behavior using the procedure below.
Rendering/clipping at image edges may differ from the former RGB renderer;
RGB output, intrinsics and sensor regression checks remain runtime gates.

Non-finite/no-return depth is passed through unchanged, so the existing ROI
sampler rejects it. There is no finite replacement, filling or recovery.
The shader can use distance for clipping without making valid depth radial
range. Do not add range-to-Z conversion unless the live plane test proves it necessary.

## Static validation on Windows

Python 3.12.14; task-local pytest 9.1.1, PyYAML 6.0.3, xacro 2.1.1,
catkin_pkg 1.1.1. Test dependencies are outside the repository.

```powershell
python -m pytest -p no:cacheprovider -c ros2_ws/src/aegisinspect_mapping/pytest.ini ros2_ws/src/aegisinspect_mapping/test ros2_ws/src/aegisinspect_system_tests/test -q --tb=short
```

Actual execution used the bundled Python executable and task-local PYTHONPATH.
Result: **91 passed** (78 existing checks, 13 new parameterized cases), no
failures/errors. Pytest's cache plugin was disabled because its temporary cache
directories are inaccessible in this sandbox; no tests were disabled.
`git diff --check` passes.

New tests parse configuration and verify one RGB-D camera, frozen geometry,
direct bridge paths and unobstructed fixture rays. Synthetic probe tests cover
endian/padded images, invalid floats, malformed payloads, zero timestamp fields,
and rejection of radial range and millimetres. Existing geometry APIs/tests
remain unchanged. Foundation tests were updated only for the intended depth
activation and RGB-D output naming; all existing sensor/TF assertions remain.

The broader `python -m pytest -p no:cacheprovider tests -q --tb=line` was also run:
**59 passed, 63 failed, 37 teardown errors, 14 warnings**. Running the same suite
against a separate untouched `git archive HEAD` baseline produced identical
counts and identical failed/error test IDs. Causes include temporary-directory
access denial, absent excluded raw data, and an existing data evidence checksum
mismatch. No data files/tests or ACLs were changed. This is not an all-repository
green result; those baseline issues remain outside Phase 2.

## Exact WSL acceptance procedure

First ensure this feature commit is pushed from Windows (commands below).
Use the existing WSL clone. The initial block stops on a dirty tree, protects an
existing local feature branch from replacement, and refuses divergent history.

```bash
cd ~/autonomous-drone-infrastructure-inspection
test -z "$(git status --porcelain)" || { echo 'STOP: dirty WSL worktree'; exit 1; }
git fetch origin || exit 1
if git show-ref --verify --quiet refs/heads/feat/simulated-depth-integration; then
  git switch feat/simulated-depth-integration || exit 1
else
  git switch --track -c feat/simulated-depth-integration origin/feat/simulated-depth-integration || exit 1
fi
git merge --ff-only origin/feat/simulated-depth-integration || exit 1
git merge-base --is-ancestor 606f04670c53a9b1833a3a5f5bf8121d7e3e9c2a HEAD || exit 1
git status --short --branch
git rev-parse HEAD
source /opt/ros/lyrical/setup.bash
printf 'ROS_DISTRO=%s\n' "$ROS_DISTRO"
command -v ros2
command -v gz
ros2 --help >/dev/null && echo ROS2_OK
gz sim --version
ros2 pkg prefix ros_gz_bridge
ros2 pkg prefix ros_gz_sim
ros2 pkg prefix ros_gz_image
cd ros2_ws
# Existing README rosdep workflow; no alternate ROS/Gazebo installation.
rosdep install --from-paths src --ignore-src --rosdistro lyrical -r -y || exit 1
colcon list
colcon build --symlink-install || exit 1
source install/setup.bash
colcon test --event-handlers console_direct+ || exit 1
colcon test-result --verbose || exit 1
gz sdf -k src/aegisinspect_sim/models/aegis_drone/model.sdf || exit 1
export GZ_SIM_RESOURCE_PATH="$(ros2 pkg prefix --share aegisinspect_sim)/models${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
gz sdf -k src/aegisinspect_sim/worlds/inspection_bay.sdf || exit 1
ros2 launch aegisinspect_bringup foundation.launch.py
# Or, instead of the GUI launch:
# ros2 launch aegisinspect_bringup foundation.launch.py headless:=true
```

Require 13 successful package builds and 0 test errors/failures. Record the
exact commit tested and command summaries. Use one simulation instance and the
same ROS_DOMAIN_ID/GZ_PARTITION in all terminals if either is explicitly set.

In a second WSL terminal:

```bash
cd ~/autonomous-drone-infrastructure-inspection/ros2_ws
source /opt/ros/lyrical/setup.bash
source install/setup.bash
ros2 topic list -t
for topic in /aegis/sensors/camera/image_raw /aegis/sensors/camera/camera_info /aegis/sensors/imu/data /aegis/sensors/lidar/points /clock /aegis/perception/depth/image; do
  ros2 topic info "$topic" --verbose
done
ros2 topic type /aegis/perception/depth/image
# Must print sensor_msgs/msg/Image.
ros2 topic echo /aegis/perception/depth/image --once --no-arr --qos-reliability best_effort
ros2 topic echo /aegis/sensors/camera/image_raw --once --no-arr --qos-reliability best_effort
ros2 topic echo /aegis/sensors/camera/camera_info --once --qos-reliability best_effort
ros2 topic echo /clock --once
ros2 run aegisinspect_system_tests smoke_check.py --timeout 30
ros2 run aegisinspect_system_tests depth_check.py --timeout 30
```

Both probes must exit 0. The smoke check retains RGB/CameraInfo, IMU, LiDAR,
clock, static TF and reserved-VIO checks, and requires advancing depth messages.
The depth probe reports encoding, frame, sizes, K/P/D and invalid-value counts.
It checks RGB/depth/CameraInfo resolution and pinhole calibration, then captures
three raw Gazebo observations with `gz topic` while subscribing to ROS, requiring
all three timestamps to match **exactly**, not merely lie near /clock.
It reads data only, retains no permanent capture and does not restamp anything.
A missing capture, timeout, wrong payload, or mismatched timestamp is a failure
or blocker, never a pass. Increase `--timeout` for slow renderer startup.

### Fronto-parallel optical-Z experiment

The existing wall's front face is X=4-0.2/2=3.9 m. The camera is at X=0.25 m,
Z=1.5 m, facing +X, so expected optical depth is **3.65 m**. The probe derives
this distance and camera settings from installed SDF. No new world is needed.

At principal row v=240, it samples u=64,320,576. Configuration tests ray-cast
these three paths against all existing bay boxes: they hit the wall clear of
panels/column/floor. Require each sample within **0.02 m** of 3.65 m. At the side
pixels radial range would be about 4.02 m, so it cannot pass this tolerance.
The probe prints radial predictions for comparison; it never converts the image.
This checks metric scale and optical-Z; **no live result has been obtained yet**.

### Invalid/no-return experiment

After the normal checks, remove only the five geometry models from the running
test simulation. This alters the current simulator instance, not source files.
Require `data: true` for each service response. The unchanged rig then faces
empty space. Do not run this before the wall/normal sensor regression checks.

```bash
for entity in wall panel_a panel_b column floor; do
  gz service -s /world/inspection_bay/remove \
    --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 5000 \
    --req "name: \"$entity\" type: MODEL"
done
ros2 run aegisinspect_system_tests depth_check.py --timeout 30 --expect-no-return
```

Require no positive finite depth pixels. NaN, infinities or nonpositive invalid
values are rejectable by the existing sampler; finite clip-distance plateaus
must fail. Stop and restart foundation.launch.py afterward to restore the bay.
The no-return mode does not constitute the wall experiment or normal sensor pass.

## Changed files and handoff

Stage only these repository-relative paths if a manual commit is needed:

```text
README.md
docs/implementation_reports/simulated_depth_integration.md
ros2_ws/src/aegisinspect_interfaces/config/contracts.yaml
ros2_ws/src/aegisinspect_sim/config/bridge.yaml
ros2_ws/src/aegisinspect_sim/models/aegis_drone/model.sdf
ros2_ws/src/aegisinspect_system_tests/CMakeLists.txt
ros2_ws/src/aegisinspect_system_tests/package.xml
ros2_ws/src/aegisinspect_system_tests/scripts/smoke_check.py
ros2_ws/src/aegisinspect_system_tests/scripts/depth_check.py
ros2_ws/src/aegisinspect_system_tests/test/test_foundation.py
ros2_ws/src/aegisinspect_system_tests/test/test_simulated_depth.py
```

Suggested commit message and PR title: `feat(depth): integrate simulated metric depth`.
Git staging in Codex failed with `Unable to create .git/index.lock: Permission denied`.
No commit was created and no ACLs were changed. From Windows PowerShell, stage
the exact reviewed paths and mark the new runtime probe executable for WSL:

```powershell
Set-Location C:\Dev\aegisinspect-chat08-codex
git add -- README.md docs/implementation_reports/simulated_depth_integration.md ros2_ws/src/aegisinspect_interfaces/config/contracts.yaml ros2_ws/src/aegisinspect_sim/config/bridge.yaml ros2_ws/src/aegisinspect_sim/models/aegis_drone/model.sdf ros2_ws/src/aegisinspect_system_tests/CMakeLists.txt ros2_ws/src/aegisinspect_system_tests/package.xml ros2_ws/src/aegisinspect_system_tests/scripts/smoke_check.py ros2_ws/src/aegisinspect_system_tests/scripts/depth_check.py ros2_ws/src/aegisinspect_system_tests/test/test_foundation.py ros2_ws/src/aegisinspect_system_tests/test/test_simulated_depth.py
git update-index --chmod=+x ros2_ws/src/aegisinspect_system_tests/scripts/depth_check.py
git diff --cached --check
git diff --cached --stat
git -C C:\Dev\aegisinspect-chat08-codex commit -m "feat(depth): integrate simulated metric depth"
git -C C:\Dev\aegisinspect-chat08-codex push -u origin feat/simulated-depth-integration
```

Do not stage all untracked paths. Three inaccessible `pytest-cache-files-*`
directories were left under `ros2_ws/src/aegisinspect_mapping` by the initial
pytest cache attempt. They are test artifacts, not source changes, and Git warns
when trying to inspect them. No attempt was made to change their ACLs.

Suggested PR description:

> Enable a shared Gazebo RGB-D camera and bridge its depth image directly to
> `/aegis/perception/depth/image`, preserving the existing ROS sensor interfaces
> and calibration geometry. Add deterministic configuration/probe tests and an
> opt-in WSL validator for optical-Z, invalid returns and exact observation stamps.
>
> Validation: 91 relevant static/geometry tests pass. The data suite reproduces
> its unchanged baseline failures (59 pass, 63 fail, 37 errors). WSL colcon,
> Gazebo, sensor regression and depth acceptance remain pending. Not merge-ready.

No Phase 3, detector, localization, map transform or projection work is included.
