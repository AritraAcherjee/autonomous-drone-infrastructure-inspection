"""Pinhole geometry in meters: optical +X right, +Y down, +Z forward.

Pixels, depth image and intrinsics must share the same calibrated pinhole
image geometry. Undistortion, registration and calibration checks belong to
the caller; raw distorted pixels cannot be used with rectified intrinsics.
No ROS imports, frame transformations or ray-range conversions occur here.
"""

from collections.abc import Sequence
from math import ceil, isfinite


def pixel_to_camera_xyz(
    u: float, v: float, depth_z: float, *,
    fx: float, fy: float, cx: float, cy: float,
) -> tuple[float, float, float]:
    """Back-project a calibrated pixel using optical-axis Z (meters).

    Intrinsics and pixel coordinates are in pixels. Return optical-frame
    (X, Y, Z) in meters, not Euclidean ray range. Inputs must be finite,
    depth_z/fx/fy positive; invalid values or nonfinite results raise ValueError.
    The caller must ensure matching calibrated geometry (not inferable here).
    """
    for name, value in (
        ('u', u), ('v', v), ('depth_z', depth_z),
        ('fx', fx), ('fy', fy), ('cx', cx), ('cy', cy),
    ):
        if not isfinite(value):
            raise ValueError(f'{name} must be finite')
    if depth_z <= 0 or fx <= 0 or fy <= 0:
        raise ValueError('depth_z, fx and fy must be positive')
    x = ((u - cx) / fx) * depth_z
    y = ((v - cy) / fy) * depth_z
    if not isfinite(x) or not isfinite(y):
        raise ValueError('back-projected coordinates must be finite')
    return float(x), float(y), float(depth_z)


def sample_roi_depth(
    depth_image: Sequence[Sequence[float]],
    roi: tuple[int, int, int, int], *,
    central_fraction: float = 0.5,
    min_valid_fraction: float = 0.5,
) -> float:
    """Return median positive finite optical-axis Z in meters in a central ROI.

    Image is rectangular, indexed [v][u]. ROI is integer (left, top, right,
    bottom), with exclusive right/bottom, wholly inside the image; no clipping.
    central_fraction in (0, 1] scales each side, rounded up to whole pixels.
    Centering ties favor top/left. Valid fraction uses all central ROI pixels
    as denominator; equality passes. min_valid_fraction must be in [0, 1].
    Raise ValueError for invalid geometry/options or no/insufficient valid depth.
    The median is a region estimate, not a guarantee of foreground identity.
    """
    if not isfinite(central_fraction) or not 0 < central_fraction <= 1:
        raise ValueError('central_fraction must be in (0, 1]')
    if not isfinite(min_valid_fraction) or not 0 <= min_valid_fraction <= 1:
        raise ValueError('min_valid_fraction must be in [0, 1]')
    height = len(depth_image)
    if height == 0 or len(depth_image[0]) == 0:
        raise ValueError('depth_image must be nonempty')
    width = len(depth_image[0])
    if any(len(row) != width for row in depth_image):
        raise ValueError('depth_image must be rectangular')
    if len(roi) != 4 or any(type(bound) is not int for bound in roi):
        raise ValueError('roi must contain four integer bounds')
    left, top, right, bottom = roi
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError('roi must be nonempty and inside depth_image')
    sample_width = ceil((right - left) * central_fraction)
    sample_height = ceil((bottom - top) * central_fraction)
    left += (right - left - sample_width) // 2
    top += (bottom - top - sample_height) // 2
    valid = sorted(
        float(depth_image[v][u])
        for v in range(top, top + sample_height)
        for u in range(left, left + sample_width)
        if isfinite(depth_image[v][u]) and depth_image[v][u] > 0
    )
    if not valid or len(valid) / (sample_width * sample_height) < min_valid_fraction:
        raise ValueError('central ROI has no or insufficient valid depth')
    middle = len(valid) // 2
    if len(valid) % 2:
        return valid[middle]
    # Avoid overflow when averaging two large finite positive values.
    return valid[middle - 1] + (valid[middle] - valid[middle - 1]) / 2
