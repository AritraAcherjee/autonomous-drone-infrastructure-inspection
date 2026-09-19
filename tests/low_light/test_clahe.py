"""Synthetic-only checks of the frozen OpenCV LAB/L-channel CLAHE contract."""

import cv2
import numpy as np
import pytest

from src.low_light import apply_clahe, canonical_config, load_config
from src.low_light import clahe as clahe_module


@pytest.fixture
def image():
    yy, xx = np.indices((65, 97), dtype=np.uint16)
    return np.stack((20 + xx % 60, 30 + yy % 70, 15 + (xx + yy) % 80), axis=-1).astype(np.uint8)


def test_clahe_determinism_dimensions_dtype_range_and_source_preservation(image):
    original = image.copy()
    first = apply_clahe(image)
    second = apply_clahe(image, config=load_config())
    assert first.tobytes() == second.tobytes()
    assert first.shape == image.shape
    assert first.dtype == np.uint8
    assert 0 <= int(first.min()) <= int(first.max()) <= 255
    np.testing.assert_array_equal(image, original)
    assert not np.shares_memory(first, image)
    assert not np.array_equal(first, image)


def test_clahe_matches_exact_opencv_recipe(image):
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l_channel)
    expected = cv2.cvtColor(cv2.merge((enhanced, a_channel, b_channel)), cv2.COLOR_LAB2BGR)
    np.testing.assert_array_equal(apply_clahe(image), expected)


def test_only_lightness_is_changed_in_lab(image, monkeypatch):
    original_lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    original_cvt_color = cv2.cvtColor
    calls = []

    def record_conversion(array, code):
        calls.append(code)
        if code == cv2.COLOR_LAB2BGR:
            np.testing.assert_array_equal(array[..., 1:], original_lab[..., 1:])
            assert not np.array_equal(array[..., 0], original_lab[..., 0])
        return original_cvt_color(array, code)

    monkeypatch.setattr(clahe_module.cv2, "cvtColor", record_conversion)
    apply_clahe(image)
    assert calls == [cv2.COLOR_BGR2LAB, cv2.COLOR_LAB2BGR]


@pytest.mark.parametrize("shape", [(1, 1, 3), (1, 19, 3), (17, 1, 3), (7, 9, 3)])
def test_small_readonly_images(shape):
    image = np.full(shape, 90, dtype=np.uint8)
    image.flags.writeable = False
    result = apply_clahe(image)
    assert result.shape == image.shape and result.dtype == np.uint8
    assert np.all(image == 90)


def test_noncontiguous_source(image):
    view = image[::2, ::2]
    np.testing.assert_array_equal(apply_clahe(view), apply_clahe(view.copy()))


@pytest.mark.parametrize("bad_image", [None, [[[1, 2, 3]]], np.zeros((3, 4), dtype=np.uint8),
    np.zeros((3, 4, 1), dtype=np.uint8), np.zeros((3, 4, 4), dtype=np.uint8),
    np.zeros((0, 4, 3), dtype=np.uint8), np.zeros((3, 0, 3), dtype=np.uint8),
    np.zeros((3, 4, 3), dtype=np.float32)])
def test_invalid_source_rejected(bad_image):
    with pytest.raises(ValueError, match="image"):
        apply_clahe(bad_image)


@pytest.mark.parametrize("section,key,value", [("clahe", "clip_limit", 3.0),
    ("clahe", "tile_grid_size", [4, 4]), ("clahe", "channel", "BGR"),
    ("clahe", "resize", [640, 640]), ("noise", "kind", "poisson")])
def test_unsupported_config_rejected(image, section, key, value):
    config = canonical_config()
    config[section][key] = value
    with pytest.raises(ValueError):
        apply_clahe(image, config=config)


def test_empty_config_rejected(image):
    with pytest.raises(ValueError):
        apply_clahe(image, config={})
