from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from detection.training.config import load_config, validate_config


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "configs/detection/det_baseline.yaml"
IMPROVED = ROOT / "configs/detection/det_improved_01.yaml"


def raw(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def normalized_for_controlled_comparison(config):
    value = deepcopy(config)

    value["experiment"]["id"] = "<experiment>"
    value["experiment"]["description"] = "<description>"
    value["output"]["name"] = "<experiment>"
    value["training"]["imgsz"] = "<controlled-imgsz>"

    return value


def test_det_improved_is_single_controlled_resolution_change():
    baseline = raw(BASELINE)
    improved = raw(IMPROVED)

    assert baseline["experiment"]["id"] == "DET-BASELINE"
    assert improved["experiment"]["id"] == "DET-IMPROVED-01"

    assert baseline["training"]["imgsz"] == 640
    assert improved["training"]["imgsz"] == 800

    assert baseline["output"]["name"] == "DET-BASELINE"
    assert improved["output"]["name"] == "DET-IMPROVED-01"

    assert (
        normalized_for_controlled_comparison(baseline)
        == normalized_for_controlled_comparison(improved)
    )


def test_baseline_and_det_improved_configs_are_both_approved():
    baseline = load_config(BASELINE, ROOT)
    improved = load_config(IMPROVED, ROOT)

    assert baseline["training"]["imgsz"] == 640
    assert improved["training"]["imgsz"] == 800


def test_baseline_cannot_silently_change_to_800():
    config = load_config(BASELINE, ROOT)
    config["training"]["imgsz"] = 800

    with pytest.raises(
        ValueError,
        match=r"DET-BASELINE requires imgsz=640",
    ):
        validate_config(config, ROOT)


def test_det_improved_cannot_fall_back_to_640():
    config = load_config(IMPROVED, ROOT)
    config["training"]["imgsz"] = 640

    with pytest.raises(
        ValueError,
        match=r"DET-IMPROVED-01 requires imgsz=800",
    ):
        validate_config(config, ROOT)


def test_unknown_800_experiment_is_rejected():
    config = load_config(IMPROVED, ROOT)

    config["experiment"]["id"] = "DET-IMPROVED-02"
    config["output"]["name"] = "DET-IMPROVED-02"

    with pytest.raises(
        ValueError,
        match=r"Unapproved detector experiment identity",
    ):
        validate_config(config, ROOT)


def test_det_improved_preserves_development_only_data_contract():
    baseline = raw(BASELINE)
    improved = raw(IMPROVED)

    assert improved["data"] == baseline["data"]
    assert improved["model"] == baseline["model"]
    assert improved["data"] == {
        "yaml": "configs/data/gyu_det_v3_baseline_v1.yaml",
        "identity": "GYU-DET V3 baseline-v1",
        "train_split": "train",
        "validation_split": "valid",
        "test_policy": "prohibited",
    }


def test_det_improved_preserves_optimizer_seed_and_schedule():
    baseline = raw(BASELINE)
    improved = raw(IMPROVED)

    for key in (
        "batch",
        "epochs",
        "optimizer",
        "lr0",
        "lrf",
        "momentum",
        "weight_decay",
        "warmup_epochs",
        "warmup_momentum",
        "warmup_bias_lr",
        "nbs",
        "cos_lr",
        "seed",
        "deterministic",
        "workers",
        "patience",
        "amp",
        "resume",
    ):
        assert improved["training"][key] == baseline["training"][key]


def test_det_improved_preserves_augmentation_and_validation_contract():
    baseline = raw(BASELINE)
    improved = raw(IMPROVED)

    assert improved["augmentation"] == baseline["augmentation"]
    assert improved["validation"] == baseline["validation"]
