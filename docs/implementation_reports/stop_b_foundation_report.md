# AegisInspect Stop-B foundation implementation report

Implemented in a clone of the canonical repository:
https://github.com/AritraAcherjee/autonomous-drone-infrastructure-inspection.git

Baseline commit: `1cd132587f5a91ca3b5ed215adf6f2a6d702f63e`. The clean original tree (README.md, .gitignore, .git/)
was shown before files were modified. No separate repository was created.
This report preserves the initial implementation evidence. Subsequent owner-verified
manual runtime results are recorded in the [runtime validation report](stop_b_runtime_validation.md).

## Scope and implementation

Created all 13 requested ament_cmake packages. Reserved subsystem packages contain
only manifests/build files. Added Xacro static sensor geometry, a stationary
Gazebo sensor rig, inspection bay with neutral geometric targets, RGB/CameraInfo,
IMU, 360x16 3D LiDAR, one-way ros_gz bridge and /clock support, description/sim/
bringup launch files, frozen-contract metadata, offline tests and a live checker.

No detector, fake detection, depth algorithm, VIO, SLAM, fusion, mapping,
navigation, safety logic or autonomous behavior was implemented. Depth/VIO
interfaces remain reserved. Ground truth is reserved under
`/aegis/sim/ground_truth/...` for evaluation only; this stationary fixture needs
no ground-truth stream and publishes none. Its known start pose is in world SDF:
(0, 0, 1.5 m), roll/pitch/yaw all zero. No dynamic TF or world-to-map transform.

## Files created and modified

Modified: `.gitignore`, `README.md`.
Created: `.gitattributes`, 37 ROS workspace files, and the two implementation documents listed below.
All 13 packages include `package.xml` and `CMakeLists.txt`.
`.gitattributes` retains LF line endings on Windows/Ubuntu.
No project license was selected; manifests preserve the no-license status with
`Proprietary`, as explained in README.

## Final repository tree

Excludes .git internals and ignored Python/test caches.

```text
autonomous-drone-infrastructure-inspection/
├── .gitattributes
├── .gitignore
├── README.md
├── docs/
│   └── implementation_reports/
│       ├── stop_b_foundation_report.md
│       └── stop_b_foundation_verification.md
└── ros2_ws/
    └── src/
        ├── aegisinspect_bringup/
        │   ├── CMakeLists.txt
        │   ├── launch/
        │   │   └── foundation.launch.py
        │   └── package.xml
        ├── aegisinspect_description/
        │   ├── CMakeLists.txt
        │   ├── launch/
        │   │   └── description.launch.py
        │   ├── package.xml
        │   └── urdf/
        │       └── drone.urdf.xacro
        ├── aegisinspect_diagnostics/
        │   ├── CMakeLists.txt
        │   └── package.xml
        ├── aegisinspect_inspection/
        │   ├── CMakeLists.txt
        │   └── package.xml
        ├── aegisinspect_interfaces/
        │   ├── CMakeLists.txt
        │   ├── config/
        │   │   └── contracts.yaml
        │   └── package.xml
        ├── aegisinspect_localization/
        │   ├── CMakeLists.txt
        │   └── package.xml
        ├── aegisinspect_mapping/
        │   ├── CMakeLists.txt
        │   └── package.xml
        ├── aegisinspect_navigation/
        │   ├── CMakeLists.txt
        │   └── package.xml
        ├── aegisinspect_perception/
        │   ├── CMakeLists.txt
        │   └── package.xml
        ├── aegisinspect_safety/
        │   ├── CMakeLists.txt
        │   └── package.xml
        ├── aegisinspect_sensors/
        │   ├── CMakeLists.txt
        │   └── package.xml
        ├── aegisinspect_sim/
        │   ├── CMakeLists.txt
        │   ├── config/
        │   │   └── bridge.yaml
        │   ├── launch/
        │   │   └── sim.launch.py
        │   ├── models/
        │   │   └── aegis_drone/
        │   │       ├── model.config
        │   │       └── model.sdf
        │   ├── package.xml
        │   └── worlds/
        │       └── inspection_bay.sdf
        └── aegisinspect_system_tests/
            ├── CMakeLists.txt
            ├── package.xml
            ├── scripts/
            │   └── smoke_check.py
            └── test/
                └── test_foundation.py
```

## Actual verification results

* Offline pytest command: `python -m pytest ros2_ws/src/aegisinspect_system_tests/test -v --tb=short`.
  Actual initial run: **22 passed in 0.22s**, exit 0, Windows Python 3.12.14,
  pytest 9.1.1, PyYAML 6.0.3, xacro 2.1.1 and catkin_pkg 1.1.1.
  These dependencies were installed outside the repository in the task's scratch directory.
* Checks include 13 manifest validations using catkin_pkg, package inventory,
  installation paths, XML/Python parsing, real Xacro expansion, optical rotation,
  URDF/SDF extrinsics, sensor/bridge alignment, reserved contracts and launch wiring.
* `git diff --check`: exit 0, no errors.
* LF/final-newline/trailing-whitespace check across new and rewritten files: passed.
  Pre-existing unrelated whitespace in .gitignore was left intact.
* Live smoke command attempted with `--timeout 1`: Python process exit **2**:

```text
BLOCKED: ROS 2 Python runtime unavailable: No module named 'rclpy'
```

The PowerShell tool wrapper maps a failing native command to shell exit 1; the
Python process exit code was separately captured as 2 (blocked), as designed.

**Initial Codex build status: BLOCKED** because ROS 2, colcon, Gazebo and WSL
were unavailable there. This historical limitation has been superseded for the
manual foundation checks by the owner's Ubuntu 26.04/WSL2 results:
**rosdep succeeded, 13 packages built with 0 failures, and the Stop-B ROS/Gazebo
FOUNDATION manual runtime validation passed.** GUI startup, world/model loading,
live clock/sensor observations, CameraInfo and the reported static transforms
were verified. See [runtime validation](stop_b_runtime_validation.md).

No successful automated live smoke-check, headless-rendering or standalone
libsdformat validation result was supplied. Those checks remain unrecorded.
The earlier exit-2 smoke-check result above describes the initial Codex host,
not a failure of the subsequently validated Ubuntu runtime.

## Expected ROS interfaces

| Topic | Type | Header frame |
|---|---|---|
| /aegis/sensors/camera/image_raw | sensor_msgs/msg/Image | camera_optical_frame |
| /aegis/sensors/camera/camera_info | sensor_msgs/msg/CameraInfo | camera_optical_frame |
| /aegis/sensors/imu/data | sensor_msgs/msg/Imu | imu_link |
| /aegis/sensors/lidar/points | sensor_msgs/msg/PointCloud2 | lidar_link |
| /clock | rosgraph_msgs/msg/Clock | n/a |
| /tf_static | tf2_msgs/msg/TFMessage | four fixed edges below |
| /aegis/robot_description | std_msgs/msg/String | n/a |

`/tf` may be advertised but must contain no dynamic transforms. ROS infrastructure
may also advertise `/rosout` and `/parameter_events`.

```text
map -> odom                         reserved; not published
odom -> base_link                   reserved; not published
base_link -> camera_link            fixed, (0.25, 0, 0) m
camera_link -> camera_optical_frame  fixed, RPY (-pi/2, 0, -pi/2)
base_link -> imu_link               fixed, identity
base_link -> lidar_link             fixed, (0, 0, 0.15) m
```

`/aegis/perception/depth/image` remains reserved: sensor_msgs/msg/Image,
32FC1, meters, optical-axis Z. `/aegis/localization/vio/odom` remains reserved:
nav_msgs/msg/Odometry, header odom, child base_link, no TF ownership.

## Compatibility and manual verification

Target remains Ubuntu 26.04 / ROS 2 Lyrical Luth / Gazebo Jetty LTS / ros_gz.
Uses SDF 1.12 native sensor frame_id and Jetty system plugins. Older Gazebo
versions may reject them. Headless sensor rendering still requires Ogre2/EGL
support. The owner has now verified the documented GUI foundation on Ubuntu
26.04/WSL2 with ROS 2 Lyrical and gz sim 10.5.0; this does not establish
headless compatibility or final sensor performance.

See [verification guide](stop_b_foundation_verification.md) for prerequisites, exact apt/
rosdep commands, GUI/headless launch, topic/TF inspection and troubleshooting.
After installing prerequisites, from the canonical repository root on Ubuntu:

```bash
source /opt/ros/lyrical/setup.bash
cd ros2_ws
rosdep install --from-paths src --ignore-src --rosdistro lyrical -r -y
colcon build --symlink-install
source install/setup.bash
colcon test --event-handlers console_direct+
colcon test-result --verbose
ros2 launch aegisinspect_bringup foundation.launch.py
```

In a second terminal, source the same ROS/workspace setup and run:

```bash
ros2 run aegisinspect_system_tests smoke_check.py --timeout 30
```

## Review scope

The change consists of the ROS workspace, README, Git ignore/line-ending rules,
and these two implementation documents. Temporary export patches, local runtime
dependencies, caches, build products and machine-specific output artifacts are
not part of the project change.

Branch: `feat/stop-b-ros-gazebo-foundation`.
Commit message: `feat(ros): add Stop-B Lyrical Jetty sensor foundation`.

This delivers the requested source/configuration/test skeleton. It does not
declare Stop B, the full ROS workstream, or the Gazebo workstream complete.
