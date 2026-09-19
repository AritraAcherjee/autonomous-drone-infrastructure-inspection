"""Deterministic, image-only photometric transforms; no image file I/O."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping

import cv2
import numpy as np

from .severity import GLOBAL_SEED, PROTOCOL_ID, get_severity_parameters, validate_config


def _validate_image(image: np.ndarray) -> None:
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        raise ValueError("image must be a uint8 BGR numpy array")
    if image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) == 0:
        raise ValueError("image must have nonempty shape (H, W, 3)")


def derive_seed(
    source_split: str, source_relative_path: str | os.PathLike[str], severity: str,
) -> int:
    """Hash image identity without opening the path or using process randomness."""
    if get_severity_parameters(severity) is None:
        raise ValueError("L0 is unchanged and has no transform seed")
    if not isinstance(source_split, str) or not source_split or "|" in source_split:
        raise ValueError("source_split must be nonempty and contain no '|'")
    try:
        path = os.fspath(source_relative_path)
    except TypeError as exc:
        raise ValueError("source_relative_path must be a nonempty text path") from exc
    if not isinstance(path, str) or not path or "|" in path:
        raise ValueError("source_relative_path must be nonempty and contain no '|'")
    path = path.replace("\\", "/")
    seed_string = f"{PROTOCOL_ID}|{GLOBAL_SEED}|{source_split}|{path}|{severity}"
    digest = hashlib.sha256(seed_string.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _apply_brightness(x: np.ndarray, multiplier: float) -> np.ndarray:
    return x * np.float32(multiplier)


def _apply_gamma(x: np.ndarray, gamma: float) -> np.ndarray:
    return x ** np.float32(gamma)


def _apply_contrast(x: np.ndarray, multiplier: float) -> np.ndarray:
    mu = x.mean(axis=(0, 1), keepdims=True)
    return np.clip(mu + np.float32(multiplier) * (x - mu), 0.0, 1.0)


def _illumination_field(
    height: int, width: int, attenuation: float, rng: np.random.Generator,
) -> np.ndarray:
    # Draw order is part of reproducibility: cx, cy, axis_x, axis_y, theta.
    cx = np.float32(rng.uniform(0.25 * width, 0.75 * width))
    cy = np.float32(rng.uniform(0.25 * height, 0.75 * height))
    axis_x = np.float32(rng.uniform(0.35 * width, 0.70 * width))
    axis_y = np.float32(rng.uniform(0.35 * height, 0.70 * height))
    theta = np.float32(rng.uniform(0.0, np.pi))
    yy, xx = np.indices((height, width), dtype=np.float32)
    dx, dy = xx - cx, yy - cy
    cos_theta, sin_theta = np.cos(theta), np.sin(theta)
    xr = cos_theta * dx + sin_theta * dy
    yr = -sin_theta * dx + cos_theta * dy
    r2 = (xr / axis_x) ** 2 + (yr / axis_y) ** 2
    shadow_strength = np.exp(-0.5 * r2)
    return 1.0 - np.float32(attenuation) * shadow_strength


def _apply_uneven_illumination(
    x: np.ndarray, attenuation: float, rng: np.random.Generator,
) -> np.ndarray:
    field = _illumination_field(x.shape[0], x.shape[1], attenuation, rng)
    return x * field[..., None]


def _apply_gaussian_noise(
    x: np.ndarray, noise_sigma: float, rng: np.random.Generator,
) -> np.ndarray:
    noise = rng.normal(0.0, noise_sigma / 255.0, size=x.shape).astype(np.float32)
    return x + noise


def apply_low_light(
    image: np.ndarray,
    severity: str,
    *,
    source_split: str,
    source_relative_path: str | os.PathLike[str],
    config: Mapping | None = None,
) -> np.ndarray:
    """Return a new BGR uint8 image under the frozen v1 protocol.

    Source identity is seed metadata only. L0 returns an independent unchanged
    copy, consuming no randomness. L1-L4 use one local RNG for illumination,
    then noise. OpenCV chooses the Gaussian kernel from sigma with reflected
    borders; every image arithmetic stage uses float32.
    """
    if config is not None:
        validate_config(config)
    params = get_severity_parameters(severity)
    _validate_image(image)
    if params is None:
        return image.copy()

    rng = np.random.default_rng(derive_seed(source_split, source_relative_path, severity))
    x = image.astype(np.float32) / 255.0
    x = _apply_brightness(x, params.brightness)
    x = _apply_gamma(x, params.gamma)
    x = _apply_contrast(x, params.contrast)
    x = _apply_uneven_illumination(x, params.illumination_attenuation, rng)
    x = cv2.GaussianBlur(
        x, (0, 0), sigmaX=params.blur_sigma, sigmaY=params.blur_sigma,
        borderType=cv2.BORDER_REFLECT_101,
    )
    x = _apply_gaussian_noise(x, params.noise_sigma, rng)
    x = np.clip(x, 0.0, 1.0)
    return np.rint(x * 255.0).astype(np.uint8)
