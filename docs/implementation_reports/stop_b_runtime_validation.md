# Stop-B ROS/Gazebo foundation runtime validation

**Status: PASSED — Stop-B ROS/Gazebo FOUNDATION manual runtime validation.**

Evidence source: verified manual Ubuntu/WSL runtime results supplied by the
repository owner and recorded on 2026-09-10. These results were not independently
rerun in the Codex execution environment. They supersede the original
environment-blocked build and GUI runtime status in the foundation reports.
No source code, interfaces, TF definitions or simulation settings were changed.

## Environment

| Item | Verified result |
|---|---|
| Host | Windows with WSL2 |
| Guest | Ubuntu 26.04 LTS, x86_64 |
| Display | WSLg available; `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0` |
| ROS | ROS 2 Lyrical installed; `ros2` CLI functional |
| Gazebo | `gz sim` 10.5.0, installed through the Lyrical `ros_gz` stack |
| Integration packages | `ros_gz_bridge`, `ros_gz_image`, `ros_gz_sim` available |

## Dependency installation and build

`rosdep install` completed successfully:

```text
All required rosdeps installed successfully
```

`colcon build --symlink-install`: **13 packages finished successfully, 0 failed**.
The previously recorded offline suite remains **22 static tests passed**; no new
Ubuntu `colcon test` or automated live smoke-check result was supplied.

## Gazebo launch

```bash
ros2 launch aegisinspect_bringup foundation.launch.py
```

The Gazebo GUI launched successfully through WSLg. The `inspection_bay` world
and `aegis_drone` model loaded, and the launch remained running. The observed
real-time factor during GUI operation was approximately **74–77%**.

## ROS discovery and simulation time

Discovered nodes:

```text
/aegis/robot_state_publisher
/aegis/sim/sensor_bridge
```

Observed topic names:

```text
/aegis/joint_states
/aegis/robot_description
/aegis/sensors/camera/camera_info
/aegis/sensors/camera/image_raw
/aegis/sensors/imu/data
/aegis/sensors/lidar/points
/clock
/tf
/tf_static
```

`/clock` successfully produced a live simulation timestamp. Topic discovery
alone does not establish a publisher or message delivery on every listed topic.
In particular, `/aegis/joint_states` may appear through robot_state_publisher's
subscription, and the presence of `/tf` does not prove dynamic TF publication.

## Sensor observations

| Sensor/topic | Observed wall-clock rate during GUI simulation |
|---|---|
| RGB `/aegis/sensors/camera/image_raw` | Sustained approximately 11–12 Hz |
| IMU `/aegis/sensors/imu/data` | Approximately 147–149 Hz |
| 3D LiDAR `/aegis/sensors/lidar/points` | Approximately 7.4–7.5 Hz |

These are **wall-clock observations at roughly 75% real-time factor**, not final
sensor performance targets. Configured simulation-time rates remain RGB 30 Hz,
IMU 200 Hz and LiDAR 10 Hz. The IMU and LiDAR observations roughly follow the
real-time factor. RGB is below the roughly 22–23 Hz that simple real-time-factor
scaling of 30 Hz would predict. The supplied evidence does not establish why;
rendering/transport/measurement performance needs separate characterization.
No parameters were adjusted and no full-rate performance acceptance is claimed.

CameraInfo on `/aegis/sensors/camera/camera_info`:

| Field | Observed value |
|---|---|
| `frame_id` | `camera_optical_frame` |
| Resolution | 640 x 480 |
| `fx` | 554.2562866210938 |
| `fy` | 554.2563056945801 |
| `cx` | 320.0 |
| `cy` | 240.0 |
| `distortion_model` | `plumb_bob` |
| Distortion coefficients | All zero |

The resolution, optical frame and intrinsics are consistent with the configured
640 x 480 camera and approximately 60-degree horizontal field of view.

## Static TF validation

| Resolved transform | Translation in meters | Rotation |
|---|---|---|
| `base_link -> camera_optical_frame` | [0.250, 0.000, 0.000] | RPY approximately [-90, 0, -90] degrees |
| `base_link -> imu_link` | [0, 0, 0] | Identity |
| `base_link -> lidar_link` | [0, 0, 0.150] | Identity |

The camera transform resolves through the existing intermediate `camera_link`;
it does not add or replace a TF edge. These measurements match the frozen
sensor-frame foundation. `tf2_echo` initially printed a transient frame-discovery
warning before successfully resolving each transform. That startup discovery
message is **not a validation failure**.

## Scope of the pass and remaining evidence

The manual foundation pass covers dependency installation, all 13 package builds,
GUI/world/model startup, ROS discovery, live clock and sensor observations,
CameraInfo and the reported static transforms. The original blanket statement
that all runtime validation is pending is no longer correct.

The supplied evidence does not include a successful automated `smoke_check.py`
run, headless rendering validation, standalone `gz sdf -k` validation, or every
payload/timestamp/publisher-isolation assertion implemented by the live checker.
Those checks remain unrecorded, not failed. The original blocked smoke-check
attempt remains historical evidence from the Codex environment.

**Stop B itself is not complete.** VIO, depth projection, detector integration,
autonomous flight, LiDAR SLAM and sensor fusion remain future milestones. This
manual pass does not claim any of those capabilities or complete the broader
ROS/Gazebo workstreams.

See the [verification guide](stop_b_foundation_verification.md) for reproducible
commands and the [foundation report](stop_b_foundation_report.md) for the original
implementation and static-test evidence.
