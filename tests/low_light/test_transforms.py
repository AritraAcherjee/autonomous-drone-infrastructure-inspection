"""Synthetic contract tests: no dataset image loading or training dependencies."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, astuple
import hashlib
import inspect
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys

import cv2
import numpy as np
import pytest

from src.low_light import (
    GLOBAL_SEED, OPERATION_ORDER, PROTOCOL_ID, SEVERITY_IDS, SEVERITY_NAMES,
    SEVERITY_PARAMETERS, apply_low_light, canonical_config, derive_seed,
    get_severity_parameters, load_config, validate_config,
)
from src.low_light import transforms


EXPECTED_PARAMETERS = {
    "L1": (0.85, 1.10, 0.95, 0.30, 2.0, 0.08),
    "L2": (0.70, 1.20, 0.88, 0.55, 5.0, 0.15),
    "L3": (0.52, 1.35, 0.80, 0.85, 8.0, 0.25),
    "L4": (0.38, 1.55, 0.70, 1.20, 12.0, 0.38),
}
IDENTITY = {"source_split": "validation", "source_relative_path": "synthetic/panel.png"}


@pytest.fixture
def image():
    yy, xx = np.indices((73, 109), dtype=np.uint16)
    return np.stack(((xx * 7 + yy * 3) % 256, (xx * 2 + yy * 11) % 256,
                     (xx * 13 + yy * 5) % 256), axis=-1).astype(np.uint8)


def test_frozen_protocol_and_yaml():
    assert PROTOCOL_ID == "aegis-low-light-benchmark-v1"
    assert GLOBAL_SEED == 42
    assert SEVERITY_IDS == ("L0", "L1", "L2", "L3", "L4")
    assert dict(SEVERITY_NAMES) == {
        "L0": "Normal", "L1": "Mild", "L2": "Moderate", "L3": "Heavy", "L4": "Extreme",
    }
    assert tuple(SEVERITY_PARAMETERS) == SEVERITY_IDS
    assert get_severity_parameters("L0") is None
    for severity, expected in EXPECTED_PARAMETERS.items():
        assert astuple(get_severity_parameters(severity)) == expected
    assert OPERATION_ORDER == (
        "brightness", "gamma", "contrast", "smooth_uneven_illumination",
        "gaussian_blur", "gaussian_sensor_noise", "clip", "uint8_round",
    )
    config = load_config()
    assert config == canonical_config()
    assert config["clahe"]["clip_limit"] == 2.0
    assert config["clahe"]["tile_grid_size"] == [8, 8]
    validate_config(config)


def test_canonical_parameters_are_immutable():
    with pytest.raises(TypeError):
        SEVERITY_PARAMETERS["L1"] = None
    with pytest.raises(TypeError):
        SEVERITY_NAMES["L1"] = "other"
    with pytest.raises(FrozenInstanceError):
        SEVERITY_PARAMETERS["L1"].brightness = 0.1
    config = canonical_config()
    config["severities"]["L1"]["parameters"]["brightness"] = 0.1
    assert canonical_config()["severities"]["L1"]["parameters"]["brightness"] == 0.85


def test_exact_seed_and_repeatability():
    seed_string = "aegis-low-light-benchmark-v1|42|validation|synthetic/panel.png|L1"
    expected = int.from_bytes(hashlib.sha256(seed_string.encode("utf-8")).digest()[:8], "big")
    assert expected == 5764507719068780628
    assert derive_seed("validation", "synthetic/panel.png", "L1") == expected
    assert derive_seed("validation", "synthetic/panel.png", "L1") == expected
    assert 0 <= expected < 2 ** 64


def test_seed_depends_on_severity_split_and_path():
    seeds = {derive_seed("validation", "synthetic/panel.png", s) for s in EXPECTED_PARAMETERS}
    assert len(seeds) == 4
    assert derive_seed("train", "synthetic/panel.png", "L1") not in seeds
    assert derive_seed("validation", "synthetic/other.png", "L1") not in seeds


@pytest.mark.parametrize("path", [r"synthetic\panel.png", PureWindowsPath("synthetic/panel.png"),
                                  Path("synthetic/panel.png"), "synthetic/panel.png"])
def test_path_separator_normalization(image, path):
    assert derive_seed("validation", path, "L2") == derive_seed("validation", "synthetic/panel.png", "L2")
    result = apply_low_light(image, "L2", source_split="validation", source_relative_path=path)
    assert result.tobytes() == apply_low_light(image, "L2", **IDENTITY).tobytes()


@pytest.mark.parametrize("severity", SEVERITY_IDS)
def test_image_contract_and_determinism(image, severity):
    original = image.copy()
    result = apply_low_light(image, severity, **IDENTITY)
    assert result.tobytes() == apply_low_light(image, severity, **IDENTITY).tobytes()
    assert result.shape == image.shape
    assert result.dtype == np.uint8
    assert 0 <= int(result.min()) <= int(result.max()) <= 255
    np.testing.assert_array_equal(image, original)
    assert not np.shares_memory(result, image)
    assert result.tobytes() == apply_low_light(image, severity, config=load_config(), **IDENTITY).tobytes()


def test_l0_is_unchanged_without_rng(image, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("L0 must not construct or consume an RNG")

    monkeypatch.setattr(np.random, "default_rng", forbidden)
    np.testing.assert_array_equal(apply_low_light(image, "L0", **IDENTITY), image)
    with pytest.raises(ValueError, match="L0"):
        derive_seed("validation", "synthetic/panel.png", "L0")


def test_gamma_greater_than_one_darkens():
    x = np.array([0.0, 0.1, 0.3, 0.7, 1.0], dtype=np.float32)
    result = transforms._apply_gamma(x, 1.55)
    np.testing.assert_allclose(result, x ** 1.55, rtol=1e-6)
    assert np.all(result[1:-1] < x[1:-1])
    assert result[0] == 0 and result[-1] == 1
    assert result.dtype == np.float32


def test_contrast_uses_current_per_channel_mean_and_clips():
    original = np.array([[[0.1, 0.4, 0.6], [0.3, 0.8, 1.0]]], dtype=np.float32)
    current = transforms._apply_gamma(transforms._apply_brightness(original, 0.70), 1.20)
    # Explicitly average each of the current channels, not the original pixels.
    means = (current[:, :1, :] + current[:, 1:, :]) / 2
    expected = means + 0.88 * (current - means)
    result = transforms._apply_contrast(current, 0.88)
    np.testing.assert_allclose(result, expected, rtol=1e-6)
    wrong_original_mean = original.mean(axis=(0, 1), keepdims=True)
    assert not np.allclose(result, wrong_original_mean + 0.88 * (current - wrong_original_mean))
    wrong_shared_mean = current.mean()
    assert not np.allclose(result, wrong_shared_mean + 0.88 * (current - wrong_shared_mean))
    high_contrast = transforms._apply_contrast(original, 10.0)
    assert high_contrast.min() == 0.0 and high_contrast.max() == 1.0
    assert result.dtype == np.float32


def test_illumination_exact_sampling_rotation_and_field():
    class FixedRng:
        def __init__(self):
            self.calls = []
            self.values = iter((8.0, 6.0, 7.0, 5.0, np.pi / 3))

        def uniform(self, low, high):
            self.calls.append((low, high))
            return next(self.values)

    rng = FixedRng()
    field = transforms._illumination_field(12, 20, 0.25, rng)
    np.testing.assert_allclose(
        rng.calls, [(5.0, 15.0), (3.0, 9.0), (7.0, 14.0), (4.2, 8.4), (0.0, np.pi)],
        rtol=1e-15, atol=0,
    )
    # Independent scalar reference at selected coordinates, including off-axis points.
    for y, x in ((0, 0), (6, 8), (3, 17), (11, 19)):
        dx, dy = x - 8.0, y - 6.0
        xr = np.cos(np.pi / 3) * dx + np.sin(np.pi / 3) * dy
        yr = -np.sin(np.pi / 3) * dx + np.cos(np.pi / 3) * dy
        expected = 1.0 - 0.25 * np.exp(-0.5 * ((xr / 7.0) ** 2 + (yr / 5.0) ** 2))
        assert field[y, x] == pytest.approx(expected, abs=1e-7)
    assert field.dtype == np.float32
    assert field.min() >= 0.75 and field.max() <= 1.0


def test_illumination_is_deterministic_and_shared_across_channels():
    x = np.ones((37, 61, 3), dtype=np.float32)
    first = transforms._apply_uneven_illumination(x, 0.38, np.random.default_rng(1234))
    second = transforms._apply_uneven_illumination(x, 0.38, np.random.default_rng(1234))
    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(first[..., 0], first[..., 1])
    np.testing.assert_array_equal(first[..., 1], first[..., 2])
    assert np.ptp(first) > 0.0
    colored = x * np.array([0.25, 0.5, 1.0], dtype=np.float32)
    output = transforms._apply_uneven_illumination(colored, 0.38, np.random.default_rng(1234))
    np.testing.assert_array_equal(output[..., 0] * 4, output[..., 2])
    np.testing.assert_array_equal(output[..., 1] * 2, output[..., 2])
    np.testing.assert_array_equal(x, np.ones_like(x))


def test_gaussian_noise_is_deterministic_and_uses_uint8_units():
    x = np.zeros((80, 100, 3), dtype=np.float32)
    expected = np.random.default_rng(7654).normal(0.0, 12.0 / 255.0, size=x.shape).astype(np.float32)
    actual = transforms._apply_gaussian_noise(x, 12.0, np.random.default_rng(7654))
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(actual, transforms._apply_gaussian_noise(x, 12.0, np.random.default_rng(7654)))
    assert actual.dtype == np.float32
    assert actual.min() < 0 and actual.max() > 0
    assert not np.array_equal(actual[..., 0], actual[..., 1])
    np.testing.assert_array_equal(x, np.zeros_like(x))


@pytest.mark.parametrize("severity", EXPECTED_PARAMETERS)
def test_entire_pipeline_matches_frozen_math(image, severity):
    brightness, gamma, contrast, sigma, noise_sigma, attenuation = EXPECTED_PARAMETERS[severity]
    seed_text = f"aegis-low-light-benchmark-v1|42|validation|synthetic/panel.png|{severity}"
    seed = int.from_bytes(hashlib.sha256(seed_text.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    x = image.astype(np.float32) / 255.0
    x = x * brightness
    x = x ** gamma
    mu = x.mean(axis=(0, 1), keepdims=True)
    x = np.clip(mu + contrast * (x - mu), 0.0, 1.0)
    h, w = image.shape[:2]
    cx, cy, ax, ay, theta = np.array([
        rng.uniform(0.25 * w, 0.75 * w), rng.uniform(0.25 * h, 0.75 * h),
        rng.uniform(0.35 * w, 0.70 * w), rng.uniform(0.35 * h, 0.70 * h), rng.uniform(0, np.pi),
    ], dtype=np.float32)
    dx = np.arange(w, dtype=np.float32)[None, :] - cx
    dy = np.arange(h, dtype=np.float32)[:, None] - cy
    xr = np.cos(theta) * dx + np.sin(theta) * dy
    yr = -np.sin(theta) * dx + np.cos(theta) * dy
    field = 1.0 - attenuation * np.exp(-0.5 * ((xr / ax) ** 2 + (yr / ay) ** 2))
    x = cv2.GaussianBlur(x * field[..., None], (0, 0), sigma, sigmaY=sigma,
                         borderType=cv2.BORDER_REFLECT_101)
    x += rng.normal(0.0, noise_sigma / 255.0, x.shape).astype(np.float32)
    expected = np.rint(np.clip(x, 0.0, 1.0) * 255.0).astype(np.uint8)
    np.testing.assert_array_equal(apply_low_light(image, severity, **IDENTITY), expected)


def test_final_clipping_and_round_to_even(image, monkeypatch):
    intensities = np.array([-10.0, 0.5, 1.5, 2.5, 254.5, 255.0, 300.0], dtype=np.float32)
    signal = (intensities / 255.0)[None, :, None].repeat(3, axis=2)
    monkeypatch.setattr(transforms, "_apply_gaussian_noise", lambda x, sigma, rng: signal)
    result = apply_low_light(image, "L1", **IDENTITY)
    np.testing.assert_array_equal(result[0, :, 0], [0, 0, 2, 2, 254, 255, 255])


def test_severities_produce_distinct_outputs(image):
    results = [apply_low_light(image, severity, **IDENTITY) for severity in EXPECTED_PARAMETERS]
    assert len({result.tobytes() for result in results}) == 4
    assert all(float(a.mean()) > float(b.mean()) for a, b in zip(results, results[1:]))


def test_no_module_global_numpy_randomness(image, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("module-global numpy randomness used")

    for name in ("seed", "normal", "uniform", "random", "rand", "randn"):
        monkeypatch.setattr(np.random, name, forbidden)
    first = apply_low_light(image, "L3", **IDENTITY)
    apply_low_light(image, "L4", **IDENTITY)
    np.testing.assert_array_equal(first, apply_low_light(image, "L3", **IDENTITY))


def test_reproducible_across_processes_and_python_hash_seeds():
    code = (
        "import hashlib, numpy as np; from src.low_light import apply_low_light, derive_seed; "
        "x=np.arange(900,dtype=np.uint16).reshape(10,30,3).astype(np.uint8); "
        "y=apply_low_light(x,'L3',source_split='validation',source_relative_path='synthetic/a.png'); "
        "print(derive_seed('validation','synthetic/a.png','L3'),hashlib.sha256(y.tobytes()).hexdigest())"
    )
    outputs = [subprocess.check_output(
        [sys.executable, "-B", "-c", code], cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTHONHASHSEED": hash_seed}, text=True, timeout=30,
    ) for hash_seed in ("1", "999")]
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("shape", [(1, 1, 3), (1, 13, 3), (17, 1, 3), (9, 11, 3)])
@pytest.mark.parametrize("severity", SEVERITY_IDS)
def test_small_and_readonly_images(shape, severity):
    x = np.full(shape, 128, dtype=np.uint8)
    x.flags.writeable = False
    result = apply_low_light(x, severity, **IDENTITY)
    assert result.shape == shape and result.dtype == np.uint8
    assert np.all(x == 128)


def test_noncontiguous_input(image):
    view = image[::2, ::2]
    assert not view.flags.c_contiguous
    np.testing.assert_array_equal(apply_low_light(view, "L4", **IDENTITY),
                                  apply_low_light(view.copy(), "L4", **IDENTITY))


@pytest.mark.parametrize("severity", ["L5", "l1", "L01", "L1 ", " L1", "Mild", "", 1, None, [], {}])
def test_malformed_severity_rejected(image, severity):
    with pytest.raises(ValueError, match="severity"):
        get_severity_parameters(severity)
    with pytest.raises(ValueError, match="severity"):
        derive_seed("validation", "synthetic/panel.png", severity)
    with pytest.raises(ValueError, match="severity"):
        apply_low_light(image, severity, **IDENTITY)


@pytest.mark.parametrize("split,path", [(None, "a.png"), ("", "a.png"), ("a|b", "c.png"),
                                        ("validation", ""), ("validation", None),
                                        ("validation", b"a.png"), ("validation", "a|b.png")])
def test_malformed_seed_identity_rejected(split, path):
    with pytest.raises(ValueError):
        derive_seed(split, path, "L1")


@pytest.mark.parametrize("bad_image", [None, [[[1, 2, 3]]], np.zeros((3, 4), dtype=np.uint8),
    np.zeros((3, 4, 4), dtype=np.uint8), np.zeros((0, 4, 3), dtype=np.uint8),
    np.zeros((3, 0, 3), dtype=np.uint8), np.zeros((3, 4, 3), dtype=np.float32)])
@pytest.mark.parametrize("severity", ["L0", "L1"])
def test_malformed_image_rejected(bad_image, severity):
    with pytest.raises(ValueError, match="image"):
        apply_low_light(bad_image, severity, **IDENTITY)


def _leaf_paths(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaf_paths(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _leaf_paths(child, path + (index,))
    else:
        yield path


@pytest.mark.parametrize("path", list(_leaf_paths(canonical_config())), ids=lambda p: ".".join(map(str, p)))
def test_every_frozen_config_value_is_enforced(path):
    config = canonical_config()
    target = config
    for key in path[:-1]:
        target = target[key]
    value = target[path[-1]]
    if isinstance(value, bool):
        replacement = not value
    elif isinstance(value, (int, float)):
        replacement = value + 1
    elif isinstance(value, str):
        replacement = value + "_unsupported"
    else:
        replacement = {}
    target[path[-1]] = replacement
    with pytest.raises(ValueError):
        validate_config(config)


@pytest.mark.parametrize("config", [None, [], {}, "v1", 42])
def test_malformed_config_rejected(config):
    with pytest.raises(ValueError):
        validate_config(config)


@pytest.mark.parametrize("value", [True, "0.85", float("nan"), float("inf"), None])
def test_malformed_numeric_values_rejected(value):
    config = canonical_config()
    config["severities"]["L1"]["parameters"]["brightness"] = value
    with pytest.raises(ValueError):
        validate_config(config)


@pytest.mark.parametrize("key", ["glare", "poisson", "poisson_noise", "camera_simulator", "camera_specific"])
@pytest.mark.parametrize("location", [(), ("noise",), ("severities", "L1", "parameters")])
def test_unapproved_settings_rejected_at_every_level(key, location):
    config = canonical_config()
    target = config
    for part in location:
        target = target[part]
    target[key] = False  # Even a disabled unsupported feature must not be ignored.
    with pytest.raises(ValueError, match="unsupported"):
        validate_config(config)


def test_missing_keys_extra_severity_and_reordered_operations_rejected():
    config = canonical_config()
    del config["severities"]["L2"]["parameters"]["gamma"]
    with pytest.raises(ValueError):
        validate_config(config)
    config = canonical_config()
    config["severities"]["L5"] = config["severities"]["L4"]
    with pytest.raises(ValueError):
        validate_config(config)
    config = canonical_config()
    config["operation_order"].reverse()
    with pytest.raises(ValueError):
        validate_config(config)


@pytest.mark.parametrize("text", ["", "[", "[]", "a: 1\na: 2\n", "a: {b: 1, b: 2}\n",
                                   "a: 1\n---\na: 2\n", "!!python/object:builtins.object {}",
                                   "? [a, b]\n: 1\n"])
def test_malformed_yaml_rejected(tmp_path, text):
    path = tmp_path / "malformed.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


@pytest.mark.parametrize("nested", [False, True])
def test_duplicate_keys_in_otherwise_valid_yaml_rejected(tmp_path, nested):
    source = Path(__file__).resolve().parents[2] / "configs/low_light/benchmark_v1.yaml"
    text = source.read_text(encoding="utf-8")
    if nested:
        text = text.replace("      brightness: 0.85", "      brightness: 0.99\n      brightness: 0.85")
    else:
        text += "\nglobal_seed: 42\n"
    path = tmp_path / "duplicate.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_config(path)


@pytest.mark.parametrize("severity", ["L0", "L4"])
def test_transform_validates_supplied_config(image, severity):
    bad = canonical_config()
    bad["noise"]["kind"] = "poisson"
    with pytest.raises(ValueError):
        apply_low_light(image, severity, config=bad, **IDENTITY)
    with pytest.raises(ValueError):
        apply_low_light(image, severity, config={}, **IDENTITY)


def test_transform_layer_has_no_geometry_labels_or_image_io():
    package = Path(transforms.__file__).parent
    forbidden_calls = {
        "resize", "warpAffine", "warpPerspective", "remap", "rotate", "flip",
        "rot90", "fliplr", "flipud", "imread", "imwrite", "VideoCapture",
    }
    for name in ("transforms.py", "clahe.py"):
        tree = ast.parse((package / name).read_text(encoding="utf-8"))
        calls = {node.func.attr for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        assert calls.isdisjoint(forbidden_calls)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names = [node.name] + [arg.arg for arg in node.args.args + node.args.kwonlyargs]
                assert not any(token in name.lower() for name in names
                               for token in ("bbox", "label", "geometr", "annotation"))
    assert set(inspect.signature(apply_low_light).parameters) == {
        "image", "severity", "source_split", "source_relative_path", "config",
    }
