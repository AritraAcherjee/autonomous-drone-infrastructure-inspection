# Phase 3: camera-frame ROS projection

TASK: [MSI][CHAT-08] Camera-frame ROS projection
BRANCH: feat/camera-frame-ros-projection
BASE MAIN SHA: 043ce54d40708c6bf278f8b07741c1e4afe9ccd6
CODE STATUS: CODE READY / WSL RUNTIME VALIDATION PENDING
RUNTIME VALIDATION: PENDING — MSI WSL
NEXT STEP: Run the WSL acceptance procedure below and retain its output.
BLOCKERS: No code/static blocker; ROS generation, colcon and live acceptance remain unverified.

## 1–5. Baseline, inspection and interface decision

Verified root C:\Dev\aegisinspect-chat08-phase3-codex, existing target branch,
clean tree, HEAD and origin/main both equal the base above. Phase 2 merge
57f2973 is an ancestor (exit 0). The branch was not recreated or switched.

src/depth and src/geometry do not exist. Both tested helpers actually live in
ros2_ws/src/aegisinspect_mapping/aegisinspect_mapping/depth_geometry.py.
The existing mapping package installs a pure Python module with ament_cmake_python.
Perception is reserved. Interfaces previously contained only YAML contracts;
there were no reusable request/response definitions. System tests use pure
pytest and separately installed opt-in ROS acceptance scripts.

Selected a pure ROS-independent, ROS-shaped adapter/core plus a thin synchronous
rclpy service in the existing mapping package. No new package or Action.
The service /aegis/mapping/project_camera uses
aegisinspect_interfaces/srv/ProjectCamera. A dedicated service is justified:
the repository has no interface for stamped pixel/ROI requests, numeric failure
status and optional-valid XYZ. Standard sensor messages remain unchanged.

The foundation service prohibition is updated to an exact allowlist containing
only ProjectCamera.srv. All other foundation assertions and all old test cases
are retained; arbitrary new services, custom messages and Actions remain rejected.

## 6–8. Exact request and response

Request fields:

- header: original observation stamp (sec, nanosec), frame_id camera_optical_frame.
- mode: PIXEL=0 or ROI=1.
- PIXEL uses int32 u and v, integer pixel indices. ROI fields are ignored.
- ROI uses int32 left, top, right, bottom. Left/top inclusive, right/bottom
  exclusive. u/v are ignored. Require nonempty ordered bounds wholly in image.
  No clipping, rescaling, neighbor search or detector semantics.

Response fields:

- uint8 status and string detail; status=SUCCESS alone indicates success.
- header: exact depth observation stamp and camera_optical_frame on success.
  On failure: requested stamp and empty frame_id, for correlation only.
- geometry_msgs/Point point: meters, optical +X right, +Y down, +Z forward.
  Z is sampled optical-axis depth. Every coordinate is NaN on failure.
- float64 sample_u/sample_v: representative image pixel, NaN on failure.
- float64 latency_ms: processing duration measured with perf_counter, excluding
  transport/serialization; never used for sensor timestamps.

The pure Result exposes xyz=None on failure. No zero-coordinate placeholders
escape through the ROS response adapter.

## 9–10. Synchronization and timestamps

Separate bounded caches use exact (sec, nanosec) keys, default cache_size=30
observations per stream. The service uses only the request's exact depth AND
CameraInfo. Arrival order may differ. Missing, not-yet-delivered, evicted or
mismatched pairs return TIMESTAMP_MISMATCH immediately. A client can retry the
same stamp after delivery; no latest fallback, tolerance or waiting inside
the service. Zero is a literal observation timestamp, never a latest sentinel.

Subscriptions use qos_profile_sensor_data on the frozen topics:
 /aegis/perception/depth/image and /aegis/sensors/camera/camera_info.
No input/output observation uses ROS now, wall clock or completion time.
The node uses the single-threaded default executor.

## 11. Status taxonomy

| Code | Name | Meaning |
| --- | --- | --- |
| 0 | SUCCESS | Valid camera-frame point |
| 1 | NO_VALID_DEPTH | Pixel or sampled central ROI has no positive finite depth |
| 2 | INSUFFICIENT_DEPTH | Some valid central ROI depth, below configured fraction |
| 3 | INVALID_CAMERA_MODEL | Invalid intrinsics or incompatible calibration geometry |
| 4 | OUT_OF_BOUNDS | Pixel/ROI extends outside image |
| 5 | TIMESTAMP_MISMATCH | Exact requested observation pair unavailable or unequal stamps |
| 6 | FRAME_MISMATCH | Any input frame differs from camera_optical_frame |
| 7 | INVALID_DEPTH_IMAGE | Wrong encoding, dimensions/layout, byte order or payload |
| 8 | INVALID_REQUEST | Unknown mode, malformed ROI, invalid request/configuration |
| 9 | NUMERICAL_ERROR | Existing geometry helper rejects nonfinite projected output |

When several inputs are invalid, the first validation failure is returned.
The cache checks observation availability first; the core checks sampling
configuration, stamps, frames, calibration, payload, request and depth in order.

## 12–17. Projection and reuse

Pixel mode reads exactly rows[v][u], rejects NaN, either infinity, zero and
negative depth, then calls the unchanged pixel_to_camera_xyz(u, v, z,
fx=..., fy=..., cx=..., cy=...).

ROI mode reuses unchanged sample_roi_depth(rows, bounds,
central_fraction=0.5, min_valid_fraction=0.5). Both fractions are validated
startup parameters. The existing sampler owns central rounding, valid filtering
and median calculation. It is called first with minimum fraction zero to
distinguish no depth from insufficient depth, then with the configured threshold.
No sampling math is copied. This small repeated ROI calculation keeps the
frozen helper API intact.

Representative pixel is the geometric center of requested pixel centers:
((left+right-1)/2, (top+bottom-1)/2). This can be half-integral and is explicitly
a region estimate, not a measured surface at that exact ray. Central-crop
rounding remains the sampler's existing top/left tie rule.

CameraInfo validation requires positive matching image dimensions, finite K,
positive fx/fy, zero skew and pinhole bottom row. D must be finite and zero;
supported distortion_model names are empty, plumb_bob and rational_polynomial.
Binning must be 0/1. ROI must be unset or the full image with zero offsets and
no do_rectify. R may be unspecified all-zero or identity; P may be unspecified
all-zero or match monocular K with zero translation. R/P tolerance is 1e-6
absolute, for calibration compatibility only, not synchronization.
Malformed R/P and unsupported distortion/cropping/rectification fail explicitly.

Depth decoding accepts only 32FC1 and honors endianness and row padding.
No unit/range conversion occurs. Frames are checked, never relabeled to hide
a disagreement. No TF lookup, transformation or map output exists.

Simple counters track each status. Every 30 node-clock seconds the node logs
success/failure totals, reason counts and last processing duration.
Configuration is captured at startup; restart to apply new parameter values.

## 18. Exact changed files

Created:
- ros2_ws/src/aegisinspect_interfaces/srv/ProjectCamera.srv
- ros2_ws/src/aegisinspect_mapping/aegisinspect_mapping/camera_projection.py
- ros2_ws/src/aegisinspect_mapping/scripts/camera_projection_node.py
- ros2_ws/src/aegisinspect_mapping/launch/camera_projection.launch.py
- ros2_ws/src/aegisinspect_mapping/test/test_camera_projection.py
- ros2_ws/src/aegisinspect_system_tests/scripts/projection_check.py
- docs/implementation_reports/camera_frame_ros_projection.md

Modified:
- ros2_ws/src/aegisinspect_interfaces/CMakeLists.txt
- ros2_ws/src/aegisinspect_interfaces/package.xml
- ros2_ws/src/aegisinspect_interfaces/config/contracts.yaml
- ros2_ws/src/aegisinspect_mapping/CMakeLists.txt
- ros2_ws/src/aegisinspect_mapping/package.xml
- ros2_ws/src/aegisinspect_system_tests/CMakeLists.txt
- ros2_ws/src/aegisinspect_system_tests/package.xml
- ros2_ws/src/aegisinspect_system_tests/test/test_foundation.py

## 19–22. Tests and static evidence

88 added cases cover analytic pixels, median/outliers, validity fractions,
bad depths, ROI and pixel bounds, K/R/P/D, cropping/binning, frames, timestamps,
zero timestamp, cache ordering/eviction, response NaNs, status constants and
the actual node callback with test-double ROS transport. These callback tests
do not claim generated ROS types, DDS, executor or simulator validation.

Windows Python 3.12.14, pytest 9.1.1; dependencies installed outside the repository.
Final code suite: **191 passed in 0.27s**, no errors, failures or skips.
Includes all 103 existing relevant Phase 1/2 cases. Earlier implementation run:
182 passed; final callback/configuration additions increased this to 191.

Exact successful Windows command, from the verified repository root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = "$env:TEMP\aegis-phase3-test-deps"
& 'C:\Users\79aa3\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -p no:cacheprovider -c ros2_ws/src/aegisinspect_mapping/pytest.ini ros2_ws/src/aegisinspect_mapping/test ros2_ws/src/aegisinspect_system_tests/test -q
```

Initial attempts were blocked by missing pytest and sandbox access to temporary
dependencies. No tests failed in a successfully collected suite. Running with
approved access resolved the environment issue. No ROS/Gazebo installation or
WSL repair was attempted.

Sensor/bridge/TF/world files and Chat 02/data files are untouched. Existing
duplicate SDFormat body-name debt is untouched.

## 23–25. Exact WSL build, test and launch procedure

Use the existing MSI Ubuntu/ROS Lyrical environment. These commands build this
Windows checkout while keeping generated artifacts on the Linux filesystem.
Do not source another project overlay. In terminal 1:

```bash
source /opt/ros/lyrical/setup.bash
cd /mnt/c/Dev/aegisinspect-chat08-phase3-codex
git branch --show-current
git rev-parse HEAD
git merge-base --is-ancestor 57f2973 HEAD
git status --short
export AEGIS_PHASE3_RUN="$HOME/aegisinspect-phase3-validation"
cd ros2_ws
colcon --log-base "$AEGIS_PHASE3_RUN/log" build \
  --build-base "$AEGIS_PHASE3_RUN/build" \
  --install-base "$AEGIS_PHASE3_RUN/install" \
  --symlink-install --event-handlers console_direct+
source "$AEGIS_PHASE3_RUN/install/setup.bash"
colcon --log-base "$AEGIS_PHASE3_RUN/log" test \
  --build-base "$AEGIS_PHASE3_RUN/build" \
  --event-handlers console_direct+ --return-code-on-test-failure
colcon test-result --test-result-base "$AEGIS_PHASE3_RUN/build" --verbose
ros2 interface show aegisinspect_interfaces/srv/ProjectCamera
ros2 launch aegisinspect_bringup foundation.launch.py headless:=true
```

Expected build: all packages succeed. Expected tests: no errors/failures/skips.
Colcon's aggregate count can include ament wrapper tests in addition to the
191 pytest cases. Preserve complete output. A build or runtime failure means
runtime acceptance has not passed, regardless of Windows results.

In terminal 2:

```bash
source /opt/ros/lyrical/setup.bash
source "$HOME/aegisinspect-phase3-validation/install/setup.bash"
ros2 launch aegisinspect_mapping camera_projection.launch.py
```

Equivalent direct node command (use instead of terminal 2 launch, not alongside):

```bash
ros2 run aegisinspect_mapping camera_projection_node.py --ros-args \
  -p use_sim_time:=true -p cache_size:=30 \
  -p central_fraction:=0.5 -p min_valid_fraction:=0.5
```

In terminal 3:

```bash
source /opt/ros/lyrical/setup.bash
source "$HOME/aegisinspect-phase3-validation/install/setup.bash"
ros2 service type /aegis/mapping/project_camera
ros2 run aegisinspect_system_tests projection_check.py
ros2 run aegisinspect_system_tests depth_check.py --timeout 30
ros2 run aegisinspect_system_tests smoke_check.py --timeout 30
```

All three probes must exit 0. The last two recheck Phase 2 optical-Z/timestamps
and the existing RGB/CameraInfo/IMU/LiDAR/clock/TF foundation with Phase 3 running.
Do not substitute a manually copied old timestamp for the live projection probe;
its purpose is to acquire matching current observations automatically.

## 26–30. Runtime cases and analytic tolerances

projection_check.py reads exact matching depth/CameraInfo headers, sends service
requests, and retries only the same timestamp for up to three seconds if its
pair is still in transit. It checks:

| Case | Request | Nominal XYZ meters |
| --- | --- | --- |
| Principal | round(cx), round(cy), normally (320,240) | (0,0,3.65) |
| Off-center | (64,round(cy)), normally (64,240) | (-1.685862786,0,3.65) |
| ROI | [300,230,341,251), representative (320,240) | (0,0,3.65) |
| Invalid pixel | (-1,240), exact available observation | OUT_OF_BOUNDS, NaN XYZ |
| Missing observation | sec=-1 in positive-time scene | TIMESTAMP_MISMATCH, NaN XYZ |

Expected X/Y use runtime CameraInfo and Z=3.65 through the existing geometry
helper. Nominal off-axis X assumes fx=640/(2*tan(pi/6))=554.2562584.
Every axis must be within 0.02 m of fixture truth. Additionally, using the
returned Z, pinhole X/Y must agree within 1e-9 m. Successful headers must equal
the requested original header exactly and frame must be camera_optical_frame.
Failure responses must contain NaNs, not plausible zero points.
The ROI sits on the unoccluded wall around the principal point.

Geometry in the Gazebo world is evaluation truth only. These checks do not
publish world coordinates or any transform.

## 31. Known limitations

- ROS interface generation, colcon installation, DDS transport and Gazebo
  execution remain pending; Windows evidence alone is not merge readiness.
- Only aligned undistorted monocular pinhole images; no registration,
  undistortion, cropping or calibration rescaling.
- Finite cache and best-effort sensor delivery can produce explicit missing-pair
  failures. There is no historical storage or waiting service.
- Restart the projection node when restarting/resetting the simulator. Timestamp
  reuse across simulation epochs cannot be disambiguated by a stamp-only API.
- ROI center plus robust depth is a regional estimate, not segmentation or
  foreground identification. No uncertainty propagation or per-sample counts.
- Processing decodes an image per request and samples an ROI twice; suitable for
  the short synchronous Phase 3 path, not a throughput benchmark claim.
- No map/base_link/odom projection, tf2, ML integration, fusion or localization.

## 32–37. Git and handoff

git diff --check passed before staging; final staged checks and status are
reported with the commit SHA in the handoff response. No build/install/log/cache
or dataset output is included. Commit subject:
feat(depth): add camera-frame ROS projection.
No automatic PR or merge.

Suggested PR title: [Chat 08] Add camera-frame pixel/ROI projection service

Suggested PR description:
Add an exact-observation ProjectCamera service around the existing depth geometry
and robust ROI sampler. Pixel and ROI requests return camera_optical_frame XYZ
with the original sensor stamp, or explicit failures with NaN wire coordinates.
Validate calibration, payload, frames and cache correspondence without changing
sensor geometry or TF. Add 88 deterministic tests and an opt-in live acceptance
probe. Windows: 191 tests pass. MSI WSL colcon and ROS/Gazebo acceptance pending;
not merge-ready until those pass.

Recommended next Chat 08 milestone: complete and record Phase 3 WSL acceptance,
then obtain review for this camera-frame-only change. Any later camera-to-body
or world-frame milestone needs its own scope and authorization. Chat 08 is not
complete and Phase 4 has not started.
