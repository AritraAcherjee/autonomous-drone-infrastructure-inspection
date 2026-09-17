from pathlib import Path

import pytest

from detection.training.config import load_config
from detection.training.trainer import readiness_evidence_path


ROOT = Path(__file__).resolve().parents[2]


def test_baseline_smoke_remains_640():
    config = load_config(
        ROOT / "configs/detection/det_baseline_smoke.yaml",
        ROOT,
    )

    assert config["experiment"]["id"] == "SMOKE-DET-BASELINE"
    assert config["training"]["imgsz"] == 640
    assert config["training"]["batch"] == 4
    assert config["training"]["epochs"] == 1


def test_det_improved_smoke_is_exactly_800_and_small():
    config = load_config(
        ROOT / "configs/detection/det_improved_01_smoke.yaml",
        ROOT,
    )

    assert config["experiment"]["id"] == "SMOKE-DET-IMPROVED-01"
    assert config["output"]["name"] == "SMOKE-DET-IMPROVED-01"

    assert config["training"]["imgsz"] == 800
    assert config["training"]["batch"] == 4
    assert config["training"]["epochs"] == 1

    assert config["smoke"]["train_images"] == 128
    assert config["smoke"]["valid_images"] == 32

    assert config["data"]["train_split"] == "train"
    assert config["data"]["validation_split"] == "valid"
    assert config["data"]["test_policy"] == "prohibited"


def test_baseline_readiness_uses_legacy_historical_path():
    path, scope = readiness_evidence_path(
        ROOT,
        "DET-BASELINE",
    )

    assert scope == "baseline"
    assert path == (
        ROOT
        / "outputs/validation/defect_detection"
        / "training_pipeline/before/ready.json"
    )

    smoke_path, smoke_scope = readiness_evidence_path(
        ROOT,
        "SMOKE-DET-BASELINE",
    )

    assert smoke_scope == "baseline"
    assert smoke_path == path


def test_det_improved_readiness_is_isolated():
    expected = (
        ROOT
        / "outputs/validation/defect_detection"
        / "training_pipeline/det-improved-01/before/ready.json"
    )

    for experiment_id in (
        "DET-IMPROVED-01",
        "SMOKE-DET-IMPROVED-01",
    ):
        path, scope = readiness_evidence_path(
            ROOT,
            experiment_id,
        )

        assert scope == "det-improved-01"
        assert path == expected


def test_unknown_experiment_has_no_readiness_fallback():
    with pytest.raises(
        ValueError,
        match="No readiness evidence namespace",
    ):
        readiness_evidence_path(
            ROOT,
            "DET-IMPROVED-02",
        )
