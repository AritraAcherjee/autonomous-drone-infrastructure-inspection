"""Pure detector-to-projection contracts.

This module intentionally has no Ultralytics or ROS runtime dependency so its
geometry and class-map contract can be regression-tested independently.
"""

from dataclasses import dataclass
import math


MODEL_VERSION = "DET-FINAL-v1"

EXPECTED_CLASS_NAMES = {
    0: "Crack",
    1: "Breakage",
    2: "Honeycombing",
    3: "Hole",
    4: "Exposed Reinforcement",
    5: "Seepage",
}


@dataclass(frozen=True)
class Detection:
    detection_id: str
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]
    image_width: int
    image_height: int
    frame_id: str
    stamp_sec: int
    stamp_nanosec: int
    model_version: str = MODEL_VERSION


def validate_class_map(names) -> None:
    """Require the exact frozen DET-FINAL-v1 six-class mapping."""
    if isinstance(names, dict):
        observed = {int(k): str(v) for k, v in names.items()}
    else:
        observed = {i: str(v) for i, v in enumerate(names)}

    if observed != EXPECTED_CLASS_NAMES:
        raise ValueError(
            f"DET-FINAL-v1 class-map mismatch: "
            f"expected={EXPECTED_CLASS_NAMES}, observed={observed}"
        )


def bbox_to_roi(
    bbox_xyxy: tuple[float, float, float, float],
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    """Convert original-image xyxy floats to ProjectCamera ROI bounds.

    ProjectCamera uses inclusive left/top and exclusive right/bottom.
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive")

    x1, y1, x2, y2 = bbox_xyxy

    if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
        raise ValueError("Bounding box contains non-finite values")

    if x2 <= x1 or y2 <= y1:
        raise ValueError("Bounding box must have positive area")

    left = max(0, min(image_width - 1, math.floor(x1)))
    top = max(0, min(image_height - 1, math.floor(y1)))
    right = max(0, min(image_width, math.ceil(x2)))
    bottom = max(0, min(image_height, math.ceil(y2)))

    if right <= left or bottom <= top:
        raise ValueError("Bounding box has no valid in-image ROI")

    return left, top, right, bottom
