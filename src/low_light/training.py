"""Frozen LL-DETECTOR-01 configuration and in-memory, image/epoch-local augmentation.

Mosaic receives one photometric draw for the completed sample, keyed by its
primary source record (Ultralytics preserves that record's im_file). Repeated
inputs with that identity and zero-based epoch have byte-identical outputs.
Upstream geometry and hue/saturation remain the parent detector's transforms.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from types import MappingProxyType

import cv2
import numpy as np
import yaml

from . import transforms
from .severity import (
    GLOBAL_SEED, SeverityParameters, _require_exact, _UniqueKeyLoader,
    canonical_config as benchmark_config,
)

EXPERIMENT_ID = "LL-DETECTOR-01"
PARENT_ID = "DET-FINAL-v1"
CHECKPOINT_PATH = "outputs/training/defect_detection/DET-BASELINE/weights/best.pt"
CHECKPOINT_SHA256 = "4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3"
PROJECT = "outputs/training/low_light"
PROBABILITIES = MappingProxyType(dict(Normal=0.50, Mild=0.20, Moderate=0.15, Heavy=0.10, Extreme=0.05))
CONDITIONAL_PROBABILITIES = MappingProxyType(dict(Mild=0.40, Moderate=0.30, Heavy=0.20, Extreme=0.10))
PARAMETER_RANGES = MappingProxyType({
    name: MappingProxyType(dict(zip(
        ("brightness", "gamma", "contrast", "noise_sigma", "blur_sigma", "illumination_attenuation"), ranges,
    ))) for name, ranges in {
        "Mild": ((0.78, 0.92), (1.05, 1.15), (0.92, 1.00), (1.0, 3.0), (0.0, 0.4), (0.04, 0.10)),
        "Moderate": ((0.60, 0.78), (1.10, 1.30), (0.85, 0.95), (3.0, 6.0), (0.2, 0.7), (0.10, 0.18)),
        "Heavy": ((0.42, 0.60), (1.20, 1.50), (0.75, 0.90), (6.0, 10.0), (0.5, 1.1), (0.18, 0.30)),
        "Extreme": ((0.28, 0.45), (1.35, 1.75), (0.65, 0.82), (10.0, 14.0), (0.8, 1.5), (0.28, 0.42)),
    }.items()
})


def canonical_config() -> dict:
    """Return a fresh exact recipe, including every explicit parent hyperparameter."""
    math_config = benchmark_config()
    return {
        "schema_version": 1,
        "experiment": {"id": EXPERIMENT_ID, "description": "Frozen in-memory low-light training from DET-FINAL-v1."},
        "parent": {"id": PARENT_ID, "checkpoint_sha256": CHECKPOINT_SHA256},
        "model": {"family": "YOLO26", "size": "s", "checkpoint": CHECKPOINT_PATH,
                  "pretrained": True, "task": "detect", "acquisition": "local_only"},
        "data": {"yaml": "configs/data/gyu_det_v3_baseline_v1.yaml", "identity": "GYU-DET V3 baseline-v1",
                 "train_split": "train", "validation_split": "valid", "test_policy": "prohibited"},
        "training": {
            "imgsz": 640, "batch": 4, "epochs": 100, "optimizer": "SGD", "lr0": 0.01, "lrf": 0.01,
            "momentum": 0.937, "weight_decay": 0.0005, "warmup_epochs": 3.0, "warmup_momentum": 0.8,
            "warmup_bias_lr": 0.1, "nbs": 64, "cos_lr": False, "seed": 42, "deterministic": True,
            "device": "0", "workers": 0, "patience": 30, "amp": "bf16", "cache": False, "save": True,
            "save_period": 10, "resume": False, "single_cls": False, "cls_remap": True, "rect": False,
            "compile": False, "channels_last": False, "freeze": None, "time": None, "fraction": 1.0,
            "profile": False, "box": 7.5, "cls": 0.5, "cls_pw": 0.0, "dfl": 1.5,
        },
        "augmentation": {
            "hsv_h": 0.015, "hsv_s": 0.7, "hsv_v": 0.0, "degrees": 0.0, "translate": 0.1,
            "scale": 0.5, "shear": 0.0, "perspective": 0.0, "flipud": 0.0, "fliplr": 0.5,
            "bgr": 0.0, "mosaic": 1.0, "close_mosaic": 10, "mixup": 0.0, "cutmix": 0.0,
            "copy_paste": 0.0, "copy_paste_mode": "flip", "multi_scale": 0.0,
            "auto_augment": None, "erasing": 0.0, "albumentations": "disabled",
        },
        "output": {"project": PROJECT, "name": EXPERIMENT_ID, "exist_ok": False, "best_and_last": True},
        "validation": {"val": True, "split": "val", "plots": True, "save_json": False,
                       "conf": 0.001, "iou": 0.7, "max_det": 300, "nms": False, "augment": False},
        "reproducibility": {"git": True, "environment": True, "requested_config": True, "resolved_config": True},
        "low_light": {
            "enabled": True, "in_memory_only": True, "source_split": "train", "global_seed": GLOBAL_SEED,
            "placement": "after_geometry_and_hue_saturation_before_format",
            "source_identity": "primary_record.image_relative_path",
            "epoch": "zero_based_trainer_epoch", "normal_probability": 0.50, "low_light_probability": 0.50,
            "overall_probabilities": dict(PROBABILITIES),
            "conditional_probabilities": dict(CONDITIONAL_PROBABILITIES),
            "ranges": {name: {key: list(bounds) for key, bounds in ranges.items()}
                       for name, ranges in PARAMETER_RANGES.items()},
            "sampling": "uniform",
            "rng": {
                "template": "LL-DETECTOR-01|42|train|{source_relative_posix_path}|epoch={epoch}",
                "path_separators": "/", "case": "preserved", "encoding": "utf-8", "hash": "sha256",
                "digest_bytes": 8, "byteorder": "big", "signed": False, "generator": "np.random.default_rng",
                "draw_order": ["normal_or_low_light", "severity", "brightness", "gamma", "contrast",
                               "illumination_attenuation", "cx", "cy", "axis_x", "axis_y", "theta",
                               "blur_sigma", "noise_sigma", "gaussian_noise_realization"],
                "normal_interval": "[0, 0.5)",
                "conditional_intervals": {"Mild": "[0, 0.4)", "Moderate": "[0.4, 0.7)",
                                          "Heavy": "[0.7, 0.9)", "Extreme": "[0.9, 1)"},
            },
            "mathematics": {key: math_config[key] for key in (
                "input", "working", "operation_order", "brightness", "gamma", "contrast", "illumination",
                "blur", "output",
            )},
            "noise": {"kind": "gaussian", "mean": 0.0, "sigma_units": "uint8_intensity", "sample_shape": "HWC"},
        },
    }


def validate_config(config: Mapping) -> None:
    """Fail closed on any altered, missing, extra or mistyped recipe value."""
    _require_exact(config, canonical_config(), "config")


def load_config(path: str | Path | None = None) -> dict:
    if path is None:
        path = Path(__file__).resolve().parents[2] / "configs/low_light/ll_detector_01.yaml"
    try:
        config = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ValueError("malformed low-light training YAML configuration") from exc
    validate_config(config)
    return config


def canonical_source_path(source_split: str, source_relative_path: str | os.PathLike[str]) -> str:
    """Validate metadata without resolving, opening or discovering any source file."""
    if source_split != "train":
        raise ValueError("Low-light training sources must use the train split")
    try:
        path = os.fspath(source_relative_path).replace("\\", "/")
    except (TypeError, AttributeError) as exc:
        raise ValueError("Source identity must be a relative text path") from exc
    if (not path or any(c in path for c in ("|", ":", "\x00", "\n", "\r"))
            or any(p in ("", ".", "..") for p in path.split("/"))
            or any(p.lower() in ("test", "valid", "validation") for p in path.split("/"))):
        raise ValueError("Source identity must be a canonical relative train path")
    return path


def validate_epoch(epoch: int) -> None:
    if type(epoch) is not int or epoch < 0:
        raise ValueError("Training epoch must be an explicit nonnegative integer")


def derive_seed(source_split: str, source_relative_path: str | os.PathLike[str], epoch: int) -> int:
    path = canonical_source_path(source_split, source_relative_path)
    validate_epoch(epoch)
    seed_string = f"{EXPERIMENT_ID}|{GLOBAL_SEED}|train|{path}|epoch={epoch}"
    digest = hashlib.sha256(seed_string.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def select_severity(rng: np.random.Generator) -> str:
    """Half-open intervals; Normal consumes just the first draw."""
    if rng.random() < 0.50:
        return "Normal"
    value = rng.random()
    for upper, name in ((0.40, "Mild"), (0.70, "Moderate"), (0.90, "Heavy")):
        if value < upper:
            return name
    return "Extreme"


@dataclass(frozen=True, slots=True)
class TrainingDecision:
    seed: int
    severity: str
    parameters: SeverityParameters | None


def augment_training_image(
    image: np.ndarray, *, source_split: str, source_relative_path: str | os.PathLike[str], epoch: int,
    config: Mapping | None = None,
) -> tuple[np.ndarray, TrainingDecision]:
    """Reuse Task B float32 primitives with one local RNG in the frozen draw order.

    Noise sigma is drawn immediately before the noise realization. The ellipse
    draws are owned by Task B's shared primitive, after attenuation and before
    blur sigma. No arrays, annotations, source files or global RNGs are mutated.
    """
    if config is not None:
        validate_config(config)
    transforms._validate_image(image)
    seed = derive_seed(source_split, source_relative_path, epoch)
    rng = np.random.default_rng(seed)
    severity = select_severity(rng)
    if severity == "Normal":
        return image.copy(), TrainingDecision(seed, severity, None)
    ranges = PARAMETER_RANGES[severity]
    brightness = rng.uniform(*ranges["brightness"])
    gamma = rng.uniform(*ranges["gamma"])
    contrast = rng.uniform(*ranges["contrast"])
    attenuation = rng.uniform(*ranges["illumination_attenuation"])
    x = image.astype(np.float32) / 255.0
    x = transforms._apply_brightness(x, brightness)
    x = transforms._apply_gamma(x, gamma)
    x = transforms._apply_contrast(x, contrast)
    x = transforms._apply_uneven_illumination(x, attenuation, rng)
    blur_sigma = rng.uniform(*ranges["blur_sigma"])
    if blur_sigma > 0.0:  # Mild includes zero, for which (0, 0) is not a valid OpenCV kernel.
        x = cv2.GaussianBlur(x, (0, 0), sigmaX=blur_sigma, sigmaY=blur_sigma, borderType=cv2.BORDER_REFLECT_101)
    noise_sigma = rng.uniform(*ranges["noise_sigma"])
    x = transforms._apply_gaussian_noise(x, noise_sigma, rng)
    parameters = SeverityParameters(brightness, gamma, contrast, blur_sigma, noise_sigma, attenuation)
    return np.rint(np.clip(x, 0.0, 1.0) * 255.0).astype(np.uint8), TrainingDecision(seed, severity, parameters)


class LowLightTrainingHook:
    """Image-only labels adapter; identity comes from approved records, never a basename."""

    def __init__(self, records: list[dict], config: Mapping):
        validate_config(config)
        identities = {}
        seen = set()
        for record in records:
            path = canonical_source_path(record.get("split"), record.get("image_relative_path"))
            key = os.fspath(record["image"]).replace("\\", "/")
            if key in identities or path in seen:
                raise ValueError("Duplicate training source identity")
            identities[key] = path
            seen.add(path)
        if not identities:
            raise ValueError("Training source records must be nonempty")
        self.source_identities = MappingProxyType(identities)
        self.epoch = None

    def set_epoch(self, epoch: int) -> None:
        validate_epoch(epoch)
        self.epoch = epoch

    def __call__(self, labels: dict) -> dict:
        if self.epoch is None:
            raise ValueError("Set the explicit training epoch before low-light augmentation")
        key = os.fspath(labels["im_file"]).replace("\\", "/")
        if key not in self.source_identities:
            raise ValueError("Sample is not an approved training source")
        image, _ = augment_training_image(labels["img"], source_split="train",
            source_relative_path=self.source_identities[key], epoch=self.epoch)
        return dict(labels, img=image)


def propagate_training_epoch(trainer) -> None:
    """Ultralytics on_train_epoch_start callback, before workers=0 consumes batches."""
    if trainer.args.workers != 0:
        raise ValueError("Low-light epoch propagation requires workers=0")
    trainer.train_loader.dataset.set_training_epoch(trainer.epoch)
