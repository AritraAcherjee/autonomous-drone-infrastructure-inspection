# Autonomous Multimodal Drone Infrastructure Inspection System

AegisInspect aims to support infrastructure inspection using vision and robotics.
This repository contains the **Stop-B ROS 2 / Gazebo foundation skeleton**
and a tested, ROS-independent camera depth geometry core.
It does not complete Stop B or the ROS/Gazebo workstreams.

## Scope

Reference platform: **Ubuntu 26.04, ROS 2 Lyrical Luth, Gazebo Jetty LTS, ros_gz**.
The simulation is a stationary drone-shaped sensor rig, not a flying vehicle.
It configures RGB, aligned simulated depth, CameraInfo, IMU, a 3D LiDAR cloud, simulation time, and static
sensor transforms. There are no actuators, control loops, trajectories, detector
outputs, custom ML messages, VIO, SLAM, fusion, mapping, safety, or navigation algorithms.

The bay contains a floor, wall, column and two colored geometric panels. The panels
have no defect taxonomy or annotations. All geometry is local; no Fuel assets are
downloaded. The rig starts at Gazebo world pose **(0, 0, 1.5 m), RPY (0, 0, 0)**,
looking toward the wall at X=4 m. It remains fixed in place.

Chat 08 Phase 2 adds a shared RGB-D sensor and direct depth bridge. Its WSL
runtime acceptance is **pending**; see the
[implementation and exact validation procedure](docs/implementation_reports/simulated_depth_integration.md).

## Repository layout

Each package below contains `package.xml` and `CMakeLists.txt`.

```text
ros2_ws/src/
├── aegisinspect_interfaces/       config/contracts.yaml
├── aegisinspect_description/      urdf/drone.urdf.xacro, launch/description.launch.py
├── aegisinspect_sensors/          reserved; metadata only
├── aegisinspect_perception/       reserved; metadata only
├── aegisinspect_localization/     reserved; metadata only
├── aegisinspect_mapping/          pure Python depth geometry and synthetic tests
├── aegisinspect_safety/           reserved; metadata only
├── aegisinspect_navigation/       reserved; metadata only
├── aegisinspect_inspection/       reserved; metadata only
├── aegisinspect_diagnostics/      reserved; metadata only
├── aegisinspect_bringup/          launch/foundation.launch.py
├── aegisinspect_sim/
│   ├── config/bridge.yaml
│   ├── launch/sim.launch.py
│   ├── models/aegis_drone/model.config
│   ├── models/aegis_drone/model.sdf
│   └── worlds/inspection_bay.sdf
└── aegisinspect_system_tests/
    ├── test/test_foundation.py
    └── scripts/smoke_check.py
```

`contracts.yaml` records approved interfaces, including interfaces reserved for
later work. It does not launch publishers. URDF and SDF sensor extrinsics are
checked for consistency. Dimensions and rates are initial simulation settings,
not a claim of calibrated hardware parameters. The repository had no license
file; manifests use `Proprietary` to avoid selecting an open-source license on
the owner's behalf. The maintainer can replace this when licensing is decided.

## Install and build on Ubuntu 26.04

First configure the official ROS apt repository using the
[Lyrical Ubuntu installation instructions](https://docs.ros.org/en/lyrical/Installation/Ubuntu-Install-Debs.html).
Use the ROS vendor package pairing for Jetty described in the
[Gazebo ROS installation guide](https://gazebosim.org/docs/jetty/ros_installation/).
Do not substitute Gazebo Classic or another ROS distribution.

```bash
sudo apt update
sudo apt install ros-lyrical-ros-base ros-lyrical-ros-gz \
  ros-lyrical-xacro ros-lyrical-robot-state-publisher ros-lyrical-tf2-ros \
  python3-colcon-common-extensions python3-rosdep python3-pytest \
  python3-yaml python3-catkin-pkg

# Run init only if rosdep has never been initialized on this machine.
sudo rosdep init
rosdep update
source /opt/ros/lyrical/setup.bash

# Run from the existing autonomous-drone-infrastructure-inspection repository root.
cd ros2_ws
rosdep install --from-paths src --ignore-src --rosdistro lyrical -r -y
colcon list
colcon build --symlink-install
source install/setup.bash
colcon test --event-handlers console_direct+
colcon test-result --verbose
```

`colcon list` should find 13 packages. `colcon test` runs offline contract tests;
it does not start Gazebo. Keep `build/`, `install/`, and `log/` out of Git.

## Launch

In a terminal at the built `ros2_ws` directory:

```bash
source /opt/ros/lyrical/setup.bash
source install/setup.bash
ros2 launch aegisinspect_bringup foundation.launch.py
```

The world starts running immediately. To run without the GUI:

```bash
ros2 launch aegisinspect_bringup foundation.launch.py headless:=true
```

Headless mode uses Ogre2/EGL rendering; RGB and GPU LiDAR still require working
rendering drivers. Start one instance in an otherwise unused ROS domain. If
needed, set the same `ROS_DOMAIN_ID` in all verification terminals. This launch
adds its installed models directory to `GZ_SIM_RESOURCE_PATH`, preserving any
existing paths. Closing Gazebo shuts down the included simulation launch.

To inspect only the static robot description, without Gazebo:

```bash
ros2 launch aegisinspect_description description.launch.py use_sim_time:=false
```

Do not run that alongside foundation bringup: bringup already starts the robot
state publisher. All fixed joints are published without a joint-state node.

## Expected topics and frames

| ROS topic | ROS type | Header frame | Configured simulation rate |
|---|---|---|---|
| `/aegis/sensors/camera/image_raw` | `sensor_msgs/msg/Image` | `camera_optical_frame` | 30 Hz, 640x480 RGB8 |
| `/aegis/sensors/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | `camera_optical_frame` | 30 Hz |
| `/aegis/perception/depth/image` | `sensor_msgs/msg/Image` | `camera_optical_frame` | 30 Hz, 640x480, expected 32FC1 metres; runtime pending |
| `/aegis/sensors/imu/data` | `sensor_msgs/msg/Imu` | `imu_link` | 200 Hz |
| `/aegis/sensors/lidar/points` | `sensor_msgs/msg/PointCloud2` | `lidar_link` | 10 Hz, 360x16 rays |
| `/clock` | `rosgraph_msgs/msg/Clock` | n/a | advancing simulation time |
| `/tf_static` | `tf2_msgs/msg/TFMessage` | parent/child frames below | transient local |
| `/aegis/robot_description` | `std_msgs/msg/String` | n/a | robot description |

ROS infrastructure topics such as `/rosout` and `/parameter_events` may also
appear. `/tf` may be advertised by robot_state_publisher, but must carry no
dynamic transforms in this foundation. Rates observed per wall-clock second
depend on rendering speed and real-time factor; configured rates use simulation time.

```text
map                         reserved; not published
└── odom                    reserved; map->odom not published
    └── base_link           odom->base_link not published
        ├── camera_link
        │   └── camera_optical_frame
        ├── imu_link
        └── lidar_link
```

The live TF tree starts at `base_link`. Camera origin is (0.25, 0, 0) m, IMU
origin (0, 0, 0) m, and LiDAR origin (0, 0, 0.15) m relative to `base_link`.
Body axes are X forward, Y left, Z up. The optical rotation is
RPY (-pi/2, 0, -pi/2): optical X right, Y down, Z forward. Gazebo renders along
`camera_link` +X and labels image/CameraInfo headers `camera_optical_frame`.

The RGB-D sensor shares one pose, resolution, field of view and clipping setup.
Depth is directly bridged to `/aegis/perception/depth/image`; optical-Z, metric
values and invalid returns still require the documented WSL acceptance checks.
No projected points are published.

Reserved interfaces have **no publishers**:

* `/aegis/localization/vio/odom`: `nav_msgs/msg/Odometry`, header `odom`, child
  `base_link`. VIO will be a measurement source and must not own dynamic TF.

All bridge mappings are Gazebo-to-ROS. Sensor streams use `SENSOR_DATA` QoS;
the one-way clock bridge uses `CLOCK`. Acquisition timestamps are preserved;
wall-time overrides are disabled. `/world/inspection_bay/clock` is explicitly
mapped to ROS `/clock` to avoid relying on Gazebo's global clock alias.

`/aegis/sim/ground_truth/...` is reserved exclusively for future evaluation.
No ground-truth stream is needed for this stationary fixture, so none is
published or bridged. Known geometry is recorded in the world SDF. Gazebo
world coordinates are never injected into `map`, `odom`, `/tf` or localization.
There is no operational `world -> map` transform.

## Verify a running simulation

In another terminal, source ROS and this workspace as above, then run:

```bash
ros2 topic list -t
ros2 topic info /aegis/sensors/camera/image_raw --verbose
ros2 topic echo /clock --once
ros2 topic echo /aegis/sensors/camera/camera_info --once --qos-reliability best_effort
ros2 topic echo /aegis/sensors/imu/data --once --qos-reliability best_effort
ros2 topic echo /aegis/sensors/lidar/points --once --field header --qos-reliability best_effort
ros2 run tf2_ros tf2_echo base_link camera_optical_frame
# Ctrl-C after confirming translation and rotation, then:
ros2 run aegisinspect_system_tests smoke_check.py --timeout 30
```

The smoke check is read-only. It waits for real messages and verifies advancing
timestamps/clock, sensor frame IDs, paired image/CameraInfo timestamps, RGB
payload shape, finite IMU specific force, 3D XYZ LiDAR returns, one publisher per
sensor/clock (including depth), the four exact static transforms and absence of dynamic TF/VIO
data. Exit codes: **0 pass, 1 failure, 2 blocked/missing ROS Python runtime**.
Use a longer timeout for slow graphics startup. It must not be run with other
robot publishers in the same domain. A stationary rig should give near-zero
angular velocity and approximately +9.81 m/s² IMU Z specific force.

Run `ros2 run aegisinspect_system_tests depth_check.py --timeout 30` as well for
depth payload/calibration checks, exact Gazebo/ROS timestamp comparison and the
fronto-parallel optical-Z experiment. Follow the linked Phase 2 procedure for
the empty-scene invalid-return check.

Optional image viewing:

```bash
sudo apt install ros-lyrical-rqt-image-view
ros2 run rqt_image_view rqt_image_view
```

Select `/aegis/sensors/camera/image_raw` and best-effort QoS if offered. The image
should show the wall and colored panels. In RViz, use fixed frame `base_link`;
`map` is intentionally unavailable.

To inspect Gazebo transport or validate its SDF on the target installation:

```bash
gz sim --versions
gz topic -l
gz sdf -k src/aegisinspect_sim/models/aegis_drone/model.sdf
export GZ_SIM_RESOURCE_PATH="$(ros2 pkg prefix --share aegisinspect_sim)/models${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
gz sdf -k src/aegisinspect_sim/worlds/inspection_bay.sdf
```

## Offline checks and compatibility limits

From the repository root, with Python, pytest, PyYAML, catkin_pkg and xacro installed:

```bash
python3 -m pytest ros2_ws/src/aegisinspect_system_tests/test -v
git diff --check
```

Offline tests expand the actual Xacro, parse package manifests/XML/Python, and
check frame geometry, SDF/URDF parity, sensor/bridge contracts, self-contained
world assets, package installation paths and reserved scope. They do not validate
SDF through libsdformat, import ROS launch modules, build with ament, or simulate
sensors. Those steps require the target ROS/Gazebo installation.

The implementation uses SDF 1.12 and its native sensor `<frame_id>` field,
supported by Jetty's dependencies. See the
[SDF sensor schema](https://github.com/gazebosim/sdformat/blob/sdf16/sdf/1.12/sensor.sdf)
and [Gazebo sensor implementation](https://github.com/gazebosim/gz-sensors/blob/gz-sensors10/src/Sensor.cc).
Bridge direction, QoS and timestamp settings follow the
[ros_gz bridge interface](https://github.com/gazebosim/ros_gz/tree/ros2/ros_gz_bridge).
Older Gazebo versions may reject the SDF version or frame field. Keep the frozen
Lyrical/Jetty pairing and flag incompatibilities rather than renaming frames.

The initial Codex environment lacked ROS/Gazebo/WSL, and the offline suite passed
22 tests. Subsequent **owner-verified manual WSL2/Ubuntu runtime validation passed
for the Stop-B ROS/Gazebo foundation**: rosdep installation, all 13 package builds,
WSLg GUI/world/model startup, live clock/sensor observations, CameraInfo and the
reported static transforms. See the [runtime validation evidence](docs/implementation_reports/stop_b_runtime_validation.md)
for exact measurements and scope.

Observed GUI wall-clock rates were RGB 11–12 Hz, IMU 147–149 Hz and LiDAR
7.4–7.5 Hz at approximately 74–77% real-time factor. These are observations,
not final performance targets. RGB is below simple real-time-factor scaling
of its configured 30 Hz; the cause has not been established. The automated
live smoke checker, standalone SDF validation and headless validation still
have no successful run recorded. Stop B and later algorithm/integration
milestones are not complete.

See the [depth geometry implementation note](docs/implementation_reports/depth_projection_core.md) for the pure back-projection API, calibration preconditions, ROI sampling and offline test commands.
