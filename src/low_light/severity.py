"""Frozen severities and fail-closed configuration for benchmark v1."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType

import yaml


PROTOCOL_ID = "aegis-low-light-benchmark-v1"
GLOBAL_SEED = 42
SEVERITY_IDS = ("L0", "L1", "L2", "L3", "L4")
SEVERITY_NAMES = MappingProxyType(
    dict(zip(SEVERITY_IDS, ("Normal", "Mild", "Moderate", "Heavy", "Extreme")))
)
OPERATION_ORDER = (
    "brightness", "gamma", "contrast", "smooth_uneven_illumination",
    "gaussian_blur", "gaussian_sensor_noise", "clip", "uint8_round",
)
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID_SIZE = (8, 8)


@dataclass(frozen=True, slots=True)
class SeverityParameters:
    brightness: float
    gamma: float
    contrast: float
    blur_sigma: float
    noise_sigma: float
    illumination_attenuation: float


SEVERITY_PARAMETERS = MappingProxyType({
    "L0": None,
    "L1": SeverityParameters(0.85, 1.10, 0.95, 0.30, 2.0, 0.08),
    "L2": SeverityParameters(0.70, 1.20, 0.88, 0.55, 5.0, 0.15),
    "L3": SeverityParameters(0.52, 1.35, 0.80, 0.85, 8.0, 0.25),
    "L4": SeverityParameters(0.38, 1.55, 0.70, 1.20, 12.0, 0.38),
})


def get_severity_parameters(severity: str) -> SeverityParameters | None:
    """Accept only exact L0-L4 identifiers; L0 has no transform parameters."""
    if not isinstance(severity, str) or severity not in SEVERITY_IDS:
        raise ValueError("severity must be exactly one of L0, L1, L2, L3, L4")
    return SEVERITY_PARAMETERS[severity]


def canonical_config() -> dict:
    """Return a fresh description of the fixed protocol, not tunable options."""
    return {
        "protocol_id": PROTOCOL_ID,
        "global_seed": GLOBAL_SEED,
        "input": {"color_space": "BGR", "dtype": "uint8"},
        "working": {"dtype": "float32", "range": [0.0, 1.0]},
        "l0": "unchanged",
        "operation_order": list(OPERATION_ORDER),
        "brightness": "x * brightness",
        "gamma": "x ** gamma",
        "contrast": {
            "mean": "current_per_channel",
            "axes": [0, 1],
            "keepdims": True,
            "formula": "mu + contrast * (x - mu)",
            "clip": [0.0, 1.0],
        },
        "illumination": {
            "kind": "single_rotated_elliptical_attenuation",
            "sample_order": ["cx", "cy", "axis_x", "axis_y", "theta"],
            "cx_width_fraction": [0.25, 0.75],
            "cy_height_fraction": [0.25, 0.75],
            "axis_x_width_fraction": [0.35, 0.70],
            "axis_y_height_fraction": [0.35, 0.70],
            "theta_radians": "[0, pi)",
            "rotation": "xr = cos(theta)*dx + sin(theta)*dy; yr = -sin(theta)*dx + cos(theta)*dy",
            "r2": "(xr / axis_x) ** 2 + (yr / axis_y) ** 2",
            "field": "1.0 - attenuation * exp(-0.5 * r2)",
            "shared_across_channels": True,
        },
        "blur": {
            "kind": "gaussian", "backend": "opencv",
            "kernel_size": [0, 0], "border_type": "BORDER_REFLECT_101",
        },
        "noise": {
            "kind": "gaussian", "mean": 0.0,
            "sigma_units": "uint8_intensity", "normalization": "noise_sigma / 255.0",
            "rng": "image_specific", "sample_shape": "HWC",
        },
        "output": {
            "clip": [0.0, 1.0],
            "conversion": "np.rint(x * 255.0).astype(np.uint8)",
        },
        "seed": {
            "path_separators": "/",
            "template": PROTOCOL_ID + "|42|{source_split}|{source_relative_posix_path}|{severity}",
            "encoding": "utf-8", "hash": "sha256", "digest_bytes": 8,
            "byteorder": "big", "signed": False, "rng": "np.random.default_rng",
            "severities": list(SEVERITY_IDS[1:]),
        },
        "severities": {
            severity: {
                "name": SEVERITY_NAMES[severity],
                "parameters": None if params is None else asdict(params),
            }
            for severity, params in SEVERITY_PARAMETERS.items()
        },
        "clahe": {
            "color_conversion": ["BGR", "LAB", "BGR"], "channel": "L",
            "clip_limit": CLAHE_CLIP_LIMIT, "tile_grid_size": list(CLAHE_TILE_GRID_SIZE),
        },
    }


def _require_exact(actual: object, expected: object, location: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, Mapping) or actual.keys() != expected.keys():
            raise ValueError(f"{location}: missing or unsupported configuration keys")
        for key, value in expected.items():
            _require_exact(actual[key], value, f"{location}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"{location}: expected the frozen list")
        for index, value in enumerate(expected):
            _require_exact(actual[index], value, f"{location}[{index}]")
    elif type(actual) is not type(expected) or actual != expected:
        # In particular, booleans, numeric strings, NaN and infinities fail closed.
        raise ValueError(f"{location}: expected frozen value {expected!r}")


def validate_config(config: Mapping) -> None:
    """Reject any missing, extra, mistyped or changed value, at every depth."""
    _require_exact(config, canonical_config(), "config")


class _UniqueKeyLoader(yaml.SafeLoader):
    """Prevent YAML duplicate keys from silently replacing protocol values."""

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in mapping:
                raise ValueError("configuration keys must be unique strings")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def load_config(path: str | Path | None = None) -> dict:
    """Load and validate YAML; the default is the repository's frozen v1 file."""
    if path is None:
        path = Path(__file__).resolve().parents[2] / "configs/low_light/benchmark_v1.yaml"
    try:
        config = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ValueError("malformed low-light YAML configuration") from exc
    validate_config(config)
    return config
