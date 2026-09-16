import pytest

from aegisinspect_perception.detector_projection import (
    EXPECTED_CLASS_NAMES,
    bbox_to_roi,
    validate_class_map,
)


def test_frozen_class_map_accepts_expected():
    validate_class_map(EXPECTED_CLASS_NAMES)


def test_frozen_class_map_rejects_reordered_names():
    bad = dict(EXPECTED_CLASS_NAMES)
    bad[0], bad[1] = bad[1], bad[0]

    with pytest.raises(ValueError):
        validate_class_map(bad)


def test_bbox_to_roi_preserves_original_image_bounds():
    assert bbox_to_roi(
        (31.5, 0.0, 640.0, 480.0),
        640,
        480,
    ) == (31, 0, 640, 480)


def test_bbox_to_roi_uses_floor_left_top_ceil_right_bottom():
    assert bbox_to_roi(
        (100.2, 50.8, 200.1, 150.2),
        640,
        480,
    ) == (100, 50, 201, 151)


def test_bbox_to_roi_clips_to_image():
    assert bbox_to_roi(
        (-5.5, -3.2, 650.7, 490.1),
        640,
        480,
    ) == (0, 0, 640, 480)


def test_bbox_to_roi_rejects_zero_area():
    with pytest.raises(ValueError):
        bbox_to_roi(
            (100.0, 100.0, 100.0, 120.0),
            640,
            480,
        )


def test_bbox_to_roi_rejects_nonfinite():
    with pytest.raises(ValueError):
        bbox_to_roi(
            (0.0, 0.0, float("nan"), 100.0),
            640,
            480,
        )
