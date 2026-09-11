"""Synthetic geometry checks; no ROS, ML or simulator required."""

import pytest

from aegisinspect_mapping.depth_geometry import pixel_to_camera_xyz, sample_roi_depth


@pytest.mark.parametrize(('u', 'v', 'z', 'expected'), [
    (320, 240, 2, (0, 0, 2)),
    (420, 240, 2, (0.4, 0, 2)),
    (220, 240, 2, (-0.4, 0, 2)),
    (320, 360, 2, (0, 0.4, 2)),
    (470, 180, 4, (1.2, -0.4, 4)),
])
def test_back_projection(u, v, z, expected):
    assert pixel_to_camera_xyz(u, v, z, fx=500, fy=600, cx=320, cy=240) == pytest.approx(expected)


@pytest.mark.parametrize('depth', [float('nan'), float('inf'), -float('inf'), 0, -1])
def test_invalid_depth(depth):
    with pytest.raises(ValueError):
        pixel_to_camera_xyz(0, 0, depth, fx=1, fy=1, cx=0, cy=0)


@pytest.mark.parametrize('name', ['fx', 'fy'])
@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf')])
def test_invalid_focal_length(name, value):
    intrinsics = dict(fx=500, fy=600, cx=320, cy=240)
    intrinsics[name] = value
    with pytest.raises(ValueError):
        pixel_to_camera_xyz(320, 240, 1, **intrinsics)


@pytest.mark.parametrize('name', ['u', 'v', 'cx', 'cy'])
@pytest.mark.parametrize('value', [float('nan'), float('inf')])
def test_nonfinite_pixel_or_principal_point(name, value):
    args = dict(u=320, v=240, depth_z=1, fx=500, fy=600, cx=320, cy=240)
    args[name] = value
    with pytest.raises(ValueError):
        pixel_to_camera_xyz(**args)


def test_projection_overflow_rejected():
    with pytest.raises(ValueError):
        pixel_to_camera_xyz(1e308, 0, 1e308, fx=1, fy=1, cx=0, cy=0)


@pytest.mark.parametrize(('samples', 'expected'), [
    ([1, 4, 2], 2),
    ([1, 4, 2, 3], 2.5),
    ([float('nan'), 2, float('inf'), 4], 3),
    ([2, 2.1, 2, 100], 2.05),
    ([0, -1, 2, 4], 3),
    ([1e308, 1e308], 1e308),
])
def test_roi_median_and_filtering(samples, expected):
    assert sample_roi_depth([samples], (0, 0, len(samples), 1), central_fraction=1) == pytest.approx(expected)


def test_central_roi_excludes_border():
    image = [[100] * 4, [100, 2, 3, 100], [100, 4, 5, 100], [100] * 4]
    assert sample_roi_depth(image, (0, 0, 4, 4)) == 3.5


def test_offset_roi_and_rounding():
    image = [[99, 1, 2, 3, 99], [99, 4, 5, 6, 99], [99, 7, 8, 9, 99]]
    # ceil(3 * .5) = 2; odd leftover pixel stays at right/bottom.
    assert sample_roi_depth(image, (1, 0, 4, 3)) == 3


def test_single_pixel_roi():
    assert sample_roi_depth([[2]], (0, 0, 1, 1)) == 2


def test_insufficient_valid_fraction():
    with pytest.raises(ValueError):
        sample_roi_depth([[1, 0, 0]], (0, 0, 3, 1), central_fraction=1)


def test_completely_invalid_roi_even_at_zero_threshold():
    with pytest.raises(ValueError):
        sample_roi_depth([[float('nan'), float('inf'), 0, -1]], (0, 0, 4, 1),
                         central_fraction=1, min_valid_fraction=0)


@pytest.mark.parametrize('roi', [(-1, 0, 1, 1), (0, 0, 3, 1), (1, 0, 1, 1),
                                 (0, 1, 1, 0), (0.5, 0, 1, 1), (0, 0, 1)])
def test_invalid_roi(roi):
    with pytest.raises(ValueError):
        sample_roi_depth([[1, 2]], roi)


@pytest.mark.parametrize('image', [[], [[]], [[1], [1, 2]]])
def test_invalid_image_shape(image):
    with pytest.raises(ValueError):
        sample_roi_depth(image, (0, 0, 1, 1))


@pytest.mark.parametrize(('name', 'value'), [
    ('central_fraction', 0), ('central_fraction', -1), ('central_fraction', 1.1),
    ('central_fraction', float('nan')), ('central_fraction', float('inf')),
    ('min_valid_fraction', -0.1), ('min_valid_fraction', 1.1),
    ('min_valid_fraction', float('nan')), ('min_valid_fraction', float('inf')),
])
def test_invalid_sampling_options(name, value):
    with pytest.raises(ValueError):
        sample_roi_depth([[1]], (0, 0, 1, 1), **{name: value})
