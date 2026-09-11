# Stop-B depth geometry core

Only the reusable geometry core is implemented. This does not complete Chat 08,
Depth + 3D Projection, or Stop B. No ROS depth node or depth publisher is added.

## Data flow and calibration

`calibrated pixel + metric optical-axis depth + matching CameraInfo intrinsics`
`-> camera_optical_frame XYZ (meters)`

The reserved depth contract remains `/aegis/perception/depth/image`,
`sensor_msgs/msg/Image`, `32FC1`, meters, optical-axis **Z**, not Euclidean ray
range. Optical axes are +X right, +Y down, +Z forward.

The pure Python module `aegisinspect_mapping.depth_geometry` provides:

```python
pixel_to_camera_xyz(u: float, v: float, depth_z: float, *,
                    fx: float, fy: float, cx: float, cy: float
                    ) -> tuple[float, float, float]
```

It computes `X = (u - cx) * Z / fx`, `Y = (v - cy) * Z / fy`, `Z = depth_z`.
All scalar inputs must be finite; Z and focal lengths must be positive.
Invalid numeric values and nonfinite outputs raise `ValueError`.

The caller must provide a common calibrated pinhole image geometry for pixels,
depth and intrinsics. Raw distorted coordinates must first be undistorted;
rectified CameraInfo must not be silently applied to raw coordinates. Cropping,
resizing and depth registration must be accounted for before calling. Scalar
arguments cannot establish calibration provenance. The later ROS adapter must
validate image/CameraInfo correspondence and timestamps and select intrinsics
for that geometry; this core does not parse CameraInfo or distortion models.

Transforming camera optical XYZ into map coordinates with tf2 belongs to the
later ROS/fusion layer, using appropriate acquisition timestamps. This function
performs no frame conversion, fusion, covariance estimation or map insertion.

## Robust region depth

```python
sample_roi_depth(depth_image: Sequence[Sequence[float]],
                 roi: tuple[int, int, int, int], *,
                 central_fraction: float = 0.5,
                 min_valid_fraction: float = 0.5) -> float
```

Use rectangular rows indexed `[v][u]` containing optical-axis Z in meters.
The integer ROI `(left, top, right, bottom)` has exclusive upper bounds and must
be nonempty and wholly inside the image; out-of-image bounds are rejected.
Each central side is `ceil(side * central_fraction)` pixels, centered with
rounding ties toward top/left. Remove nonfinite and nonpositive samples, then
return the median. For even counts the two middle values are averaged.
The valid fraction denominator includes every pixel in the central ROI;
equality with the configured minimum passes. No valid samples always fails,
even when the minimum is zero. Failures raise `ValueError`.

A central median resists isolated outliers but cannot guarantee foreground
identity or recover object shape. Associating this estimate with a detection
pixel is a caller decision; this helper only returns region depth.

## Packaging and tests

The existing mapping package stays `ament_cmake`; `ament_cmake_python` installs
its Python module and `ament_cmake_pytest` registers synthetic tests. No new ROS
package or runtime dependency is introduced. The foundation empty-package check
now excludes mapping; other reserved packages and topic contracts stay frozen.

From the repository root, with Python and pytest installed:

```bash
python -m pytest -c ros2_ws/src/aegisinspect_mapping/pytest.ini ros2_ws/src/aegisinspect_mapping/test -q
# Also requires PyYAML, catkin_pkg and xacro (offline Python dependencies):
python -m pytest -c ros2_ws/src/aegisinspect_mapping/pytest.ini ros2_ws/src/aegisinspect_mapping/test ros2_ws/src/aegisinspect_system_tests/test -q
```

Tests cover principal point, horizontal offsets of both signs, vertical offset,
known numeric back-projection, invalid depth/intrinsics/pixels, overflow, median,
invalid-sample filtering, outliers, valid-fraction failure, all-invalid regions,
central selection, rounding, single pixels, ROI bounds and option validation.
No forward projection helper is introduced. No ML or Gazebo runtime is needed.
ROS/ament build and ROS runtime validation remain for the target environment.

Validation in Codex on Windows with Python 3.12.14 and pytest 9.1.1:
combined synthetic and foundation command above: **78 passed in 0.71s**
(56 geometry cases and 22 foundation cases). No ROS runtime validation was run.
