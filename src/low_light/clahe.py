"""Frozen OpenCV CLAHE on the LAB lightness channel only."""

from collections.abc import Mapping

import cv2
import numpy as np

from .severity import CLAHE_CLIP_LIMIT, CLAHE_TILE_GRID_SIZE, validate_config
from .transforms import _validate_image


def apply_clahe(image: np.ndarray, *, config: Mapping | None = None) -> np.ndarray:
    """Return a new BGR uint8 image, preserving source pixels and dimensions."""
    if config is not None:
        validate_config(config)
    _validate_image(image)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID_SIZE)
    lab[..., 0] = clahe.apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
