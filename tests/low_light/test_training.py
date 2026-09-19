"""Task D contracts using only synthetic pixels/records; never fit or infer a model."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError
from decimal import Decimal
import hashlib
import inspect
from pathlib import Path, PureWindowsPath
import sys
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from src.low_light import training as t


EXPECTED_RANGES = {
    "Mild": [(0.78, 0.92), (1.05, 1.15), (0.92, 1.00), (1.0, 3.0), (0.0, 0.4), (0.04, 0.10)],
    "Moderate": [(0.60, 0.78), (1.10, 1.30), (0.85, 0.95), (3.0, 6.0), (0.2, 0.7), (0.10, 0.18)],
    "Heavy": [(0.42, 0.60), (1.20, 1.50), (0.75, 0.90), (6.0, 10.0), (0.5, 1.1), (0.18, 0.30)],
    "Extreme": [(0.28, 0.45), (1.35, 1.75), (0.65, 0.82), (10.0, 14.0), (0.8, 1.5), (0.28, 0.42)],
}
RANGE_KEYS = ("brightness", "gamma", "contrast", "noise_sigma", "blur_sigma", "illumination_attenuation")
IDENTITY = dict(source_split="train", source_relative_path="synthetic/Panel.png", epoch=7)


@pytest.fixture
def pixels():
    yy, xx = np.indices((19, 27), dtype=np.uint16)
    return np.stack(((xx * 7 + yy * 3) % 256, (xx * 2 + yy * 11) % 256,
                     (xx * 13 + yy * 5) % 256), axis=-1).astype(np.uint8)


def test_frozen_identity_and_config():
    config = t.load_config()
    assert config == t.canonical_config()
    assert config["experiment"]["id"] == "LL-DETECTOR-01"
    assert config["parent"] == {
        "id": "DET-FINAL-v1",
        "checkpoint_sha256": "4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3",
    }
    assert config["model"]["family"] + config["model"]["size"] == "YOLO26s"
    assert config["model"]["checkpoint"] == "outputs/training/defect_detection/DET-BASELINE/weights/best.pt"
    assert config["model"]["acquisition"] == "local_only"
    assert config["data"] == dict(yaml="configs/data/gyu_det_v3_baseline_v1.yaml",
        identity="GYU-DET V3 baseline-v1", train_split="train", validation_split="valid", test_policy="prohibited")
    for key, value in dict(seed=42, workers=0, deterministic=True, amp="bf16").items():
        assert config["training"][key] == value
    assert config["augmentation"]["hsv_v"] == 0.0
    assert config["output"]["project"] + "/" + config["output"]["name"] + "/" == (
        "outputs/training/low_light/LL-DETECTOR-01/"
    )


def test_all_parent_hyperparameters_unchanged_except_hsv_v():
    parent = yaml.safe_load((ROOT / "configs/detection/det_baseline.yaml").read_text())
    config = t.load_config()
    assert config["training"] == parent["training"]
    parent["augmentation"]["hsv_v"] = 0.0
    assert config["augmentation"] == parent["augmentation"]
    assert config["validation"] == parent["validation"]
    assert config["data"] == parent["data"]
    assert config["reproducibility"] == parent["reproducibility"]


def test_exact_probabilities_and_ranges():
    ll = t.load_config()["low_light"]
    assert ll["overall_probabilities"] == dict(Normal=.50, Mild=.20, Moderate=.15, Heavy=.10, Extreme=.05)
    assert sum(Decimal(str(v)) for v in ll["overall_probabilities"].values()) == Decimal("1.0")
    assert ll["normal_probability"] == ll["low_light_probability"] == .5
    assert ll["conditional_probabilities"] == dict(Mild=.4, Moderate=.3, Heavy=.2, Extreme=.1)
    assert sum(Decimal(str(v)) for v in ll["conditional_probabilities"].values()) == Decimal("1.0")
    for name, bounds in EXPECTED_RANGES.items():
        assert ll["ranges"][name] == dict(zip(RANGE_KEYS, map(list, bounds)))
        assert dict(t.PARAMETER_RANGES[name]) == dict(zip(RANGE_KEYS, bounds))
        assert ll["overall_probabilities"][name] == .5 * ll["conditional_probabilities"][name]


def leaves(value, prefix=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaves(child, (*prefix, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaves(child, (*prefix, index))
    else:
        yield prefix, value


@pytest.mark.parametrize("path,value", list(leaves(t.canonical_config())), ids=lambda v: str(v))
def test_every_frozen_config_leaf_rejects_changes(path, value):
    config = t.canonical_config()
    target = config
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = (not value if isinstance(value, bool) else value + 1 if isinstance(value, (int, float))
                        else "altered")
    with pytest.raises(ValueError):
        t.validate_config(config)


@pytest.mark.parametrize("section", list(t.canonical_config()))
def test_missing_and_extra_keys_fail_closed(section):
    config = t.canonical_config()
    del config[section]
    with pytest.raises(ValueError):
        t.validate_config(config)
    config = t.canonical_config()
    if isinstance(config[section], dict):
        config[section]["unsupported"] = True
    else:
        config["unsupported"] = True
    with pytest.raises(ValueError):
        t.validate_config(config)


@pytest.mark.parametrize("value", [None, [], "config", {}, 42])
def test_malformed_config_mapping(value):
    with pytest.raises(ValueError):
        t.validate_config(value)


@pytest.mark.parametrize("text", ["[", "null", "[]", "42", "schema_version: 1\nschema_version: 1\n",
                                  "{[invalid]: value}"])
def test_malformed_yaml_rejected(tmp_path, text):
    path = tmp_path / "invalid.yaml"
    path.write_text(text)
    with pytest.raises(ValueError):
        t.load_config(path)


@pytest.mark.parametrize("key,value", [("workers", False), ("seed", 42.0), ("deterministic", 1),
                                      ("lr0", float("nan")), ("momentum", float("inf"))])
def test_mistyped_numeric_values_fail_closed(key, value):
    config = t.canonical_config()
    config["training"][key] = value
    with pytest.raises(ValueError):
        t.validate_config(config)


@pytest.mark.parametrize("effect", ["glare", "poisson", "camera_simulator"])
def test_unsupported_effect_rejected(effect):
    config = t.canonical_config()
    config["low_light"][effect] = True
    with pytest.raises(ValueError):
        t.validate_config(config)
    assert effect not in str(t.canonical_config()).lower()


def test_constants_and_decisions_immutable(pixels):
    with pytest.raises(TypeError):
        t.PARAMETER_RANGES["Mild"]["brightness"] = (0., 1.)
    with pytest.raises(TypeError):
        t.PROBABILITIES["Normal"] = 1.
    _, decision = t.augment_training_image(pixels, **IDENTITY)
    with pytest.raises(FrozenInstanceError):
        decision.seed = 0


def test_exact_seed_same_image_epoch():
    expected = int.from_bytes(hashlib.sha256(b"LL-DETECTOR-01|42|train|synthetic/Panel.png|epoch=7").digest()[:8], "big")
    assert t.derive_seed("train", "synthetic/Panel.png", 7) == expected
    assert t.derive_seed("train", "synthetic/Panel.png", 7) == expected
    assert t.derive_seed("train", "synthetic/Panel.png", 8) != expected
    assert t.derive_seed("train", "synthetic/panel.png", 7) != expected


@pytest.mark.parametrize("path", [r"synthetic\Panel.png", PureWindowsPath("synthetic/Panel.png"),
                                  Path("synthetic/Panel.png"), "synthetic/Panel.png"])
def test_windows_posix_identity_same_seed_pixels_and_parameters(pixels, path):
    actual, decision = t.augment_training_image(pixels, **dict(IDENTITY, source_relative_path=path))
    expected, expected_decision = t.augment_training_image(pixels, **IDENTITY)
    assert actual.tobytes() == expected.tobytes()
    assert decision == expected_decision


@pytest.mark.parametrize("split", ["valid", "val", "validation", "test", "Train", "", None])
def test_nontrain_split_rejected(pixels, split):
    with pytest.raises(ValueError, match="train"):
        t.augment_training_image(pixels, **dict(IDENTITY, source_split=split))


@pytest.mark.parametrize("path", ["", None, b"bytes.png", "../a.png", "./a.png", "a//b.png", "/a.png",
                                  "C:\\a.png", "a|b.png", "test/test/images/a.jpg", "valid/images/a.jpg"])
def test_noncanonical_or_locked_identity_rejected(path):
    with pytest.raises(ValueError):
        t.derive_seed("train", path, 0)


@pytest.mark.parametrize("epoch", [-1, None, True, 1.0, "1"])
def test_invalid_epoch_rejected(epoch):
    with pytest.raises(ValueError, match="epoch"):
        t.derive_seed("train", "synthetic/a.png", epoch)


class FixedDraws:
    def __init__(self, *values):
        self.values = iter(values)
        self.calls = 0

    def random(self):
        self.calls += 1
        return next(self.values)


@pytest.mark.parametrize("draws,expected", [
    ((0.,), "Normal"), ((np.nextafter(.5, 0.),), "Normal"),
    ((.5, 0.), "Mild"), ((.5, np.nextafter(.4, 0.)), "Mild"),
    ((.5, .4), "Moderate"), ((.5, np.nextafter(.7, 0.)), "Moderate"),
    ((.5, .7), "Heavy"), ((.5, np.nextafter(.9, 0.)), "Heavy"),
    ((.5, .9), "Extreme"), ((np.nextafter(1., 0.), np.nextafter(1., 0.)), "Extreme"),
])
def test_exact_probability_boundaries(draws, expected):
    rng = FixedDraws(*draws)
    assert t.select_severity(rng) == expected
    assert rng.calls == len(draws)


def test_repeatability_range_bounds_normal_and_image_contract(pixels):
    before = pixels.copy()
    seen = set()
    for epoch in range(160):
        identity = dict(IDENTITY, epoch=epoch)
        actual, decision = t.augment_training_image(pixels, **identity)
        repeat, repeated_decision = t.augment_training_image(pixels, **identity)
        assert decision == repeated_decision
        assert actual.tobytes() == repeat.tobytes()
        assert actual.dtype == np.uint8 and actual.shape == pixels.shape
        assert not np.shares_memory(actual, pixels)
        seen.add(decision.severity)
        if decision.severity == "Normal":
            assert actual.tobytes() == before.tobytes()
            assert decision.parameters is None
        else:
            assert actual.tobytes() != before.tobytes()
            for key, value in asdict(decision.parameters).items():
                lo, hi = dict(zip(RANGE_KEYS, EXPECTED_RANGES[decision.severity]))[key]
                assert lo <= value <= hi
    assert seen == set(t.PROBABILITIES)
    np.testing.assert_array_equal(pixels, before)


def test_independent_reference_rng_order_and_task_b_primitives(pixels):
    """Independently replay each root RNG, including all ellipse draws and the noise array."""
    seen = set()
    for epoch in range(80):
        seed = t.derive_seed("train", "synthetic/Panel.png", epoch)
        rng = np.random.default_rng(seed)
        normal = rng.random() < .5
        if normal:
            continue
        draw = rng.random()
        severity = "Mild" if draw < .4 else "Moderate" if draw < .7 else "Heavy" if draw < .9 else "Extreme"
        ranges = dict(zip(RANGE_KEYS, EXPECTED_RANGES[severity]))
        brightness, gamma, contrast = [rng.uniform(*ranges[k]) for k in ("brightness", "gamma", "contrast")]
        attenuation = rng.uniform(*ranges["illumination_attenuation"])
        x = t.transforms._apply_brightness(pixels.astype(np.float32) / 255., brightness)
        x = t.transforms._apply_gamma(x, gamma)
        x = t.transforms._apply_contrast(x, contrast)
        x = t.transforms._apply_uneven_illumination(x, attenuation, rng)
        blur = rng.uniform(*ranges["blur_sigma"])
        x = cv2.GaussianBlur(x, (0, 0), sigmaX=blur, sigmaY=blur, borderType=cv2.BORDER_REFLECT_101)
        noise = rng.uniform(*ranges["noise_sigma"])
        x = t.transforms._apply_gaussian_noise(x, noise, rng)
        expected = np.rint(np.clip(x, 0, 1) * 255.).astype(np.uint8)
        actual, decision = t.augment_training_image(pixels, **dict(IDENTITY, epoch=epoch))
        assert decision.severity == severity
        assert asdict(decision.parameters) == dict(brightness=brightness, gamma=gamma, contrast=contrast,
            illumination_attenuation=attenuation, blur_sigma=blur, noise_sigma=noise)
        assert actual.tobytes() == expected.tobytes()
        seen.add(severity)
    assert seen == set(EXPECTED_RANGES)


def test_zero_blur_boundary_is_identity_blur(pixels, monkeypatch):
    class LowerBounds(FixedDraws):
        def uniform(self, low, high):
            return low

        def normal(self, mean, sigma, size):
            return np.zeros(size)

    monkeypatch.setattr(t.np.random, "default_rng", lambda _: LowerBounds(.5, 0.))
    with patch.object(t.cv2, "GaussianBlur", side_effect=AssertionError("zero sigma blur")):
        output, decision = t.augment_training_image(pixels, **IDENTITY)
    assert decision.parameters.blur_sigma == 0.0
    assert output.shape == pixels.shape


def test_no_disk_artifacts_or_global_randomness(pixels, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("builtins.open", side_effect=AssertionError("image I/O")), \
            patch.object(Path, "open", side_effect=AssertionError("path I/O")), \
            patch.object(cv2, "imwrite", side_effect=AssertionError("image write")):
        for epoch in range(12):
            t.augment_training_image(pixels, **dict(IDENTITY, epoch=epoch))
    assert list(tmp_path.iterdir()) == []
    for module in (t, t.transforms):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            assert name not in {"hash", "random.random", "random.uniform", "np.random.RandomState"}
            if name.startswith("np.random."):
                assert name == "np.random.default_rng"
            assert name not in {"cv2.imwrite", "cv2.imread", "np.save", "np.load", "rng.poisson"}


def synthetic_record(path="synthetic/Panel.png", split="train"):
    return dict(image=Path("unopened") / "Panel.png", image_relative_path=path, split=split)


def test_hook_preserves_labels_geometry_and_input_and_requires_epoch(pixels):
    row = synthetic_record()
    hook = t.LowLightTrainingHook([row], t.canonical_config())
    boxes = np.array([[.5, .5, .2, .3]], dtype=np.float32)
    labels = dict(img=pixels, im_file=str(row["image"]), cls=np.array([[3]]), instances=boxes,
                  ori_shape=pixels.shape[:2], resized_shape=pixels.shape[:2])
    with pytest.raises(ValueError, match="epoch"):
        hook(labels)
    hook.set_epoch(7)
    before = pixels.copy()
    actual = hook(labels)
    assert actual is not labels and actual.keys() == labels.keys()
    for key in labels.keys() - {"img"}:
        assert actual[key] is labels[key]
    np.testing.assert_array_equal(labels["img"], before)
    assert actual["img"].tobytes() == t.augment_training_image(pixels, **IDENTITY)[0].tobytes()
    with pytest.raises(ValueError, match="approved"):
        hook(dict(labels, im_file="locked/test.png"))


@pytest.mark.parametrize("rows", [[], [synthetic_record(split="valid")], [synthetic_record(split="test")],
                                  [synthetic_record(), synthetic_record()],
                                  [dict(image="a.png", split="train")]])
def test_hook_rejects_unapproved_or_ambiguous_records(rows):
    with pytest.raises(ValueError):
        t.LowLightTrainingHook(rows, t.canonical_config())


@pytest.fixture
def integration(tmp_path):
    """Import the installed CPU dataset API, contain its PIL patch, and write synthetic fixtures only."""
    from PIL import Image
    original_open = Image.open
    from detection.training.provenance import configure_runtime
    configure_runtime(ROOT)
    from detection.training.dataset import ReadOnlyDetectionDataset
    from detection.training.trainer import trainer_class, training_arguments
    from ultralytics.cfg import get_cfg
    import torch
    rows = []
    for index in range(4):
        image, label = tmp_path / f"panel{index}.png", tmp_path / f"panel{index}.txt"
        Image.new("RGB", (48 + index * 8, 64), (70 + index * 25, 120, 170)).save(image)
        label.write_text("0 0.5 0.5 0.25 0.25\n")
        rows.append(dict(image=image, label=label, split="train", annotation_count="1", class_ids="[0]",
                         image_relative_path=f"synthetic/train/panel{index}.png", label_relative_path=f"panel{index}.txt"))
    config = t.load_config()
    args = training_arguments(config, ROOT, ROOT / t.CHECKPOINT_PATH, tmp_path / "unused.yaml")
    cls = trainer_class()
    trainer = cls.__new__(cls)
    trainer.args = get_cfg(overrides=args)
    trainer.data = dict(train="train-list", val="valid-list", nc=6, channels=3, names=dict(enumerate(map(str, range(6)))))
    trainer.records = {"train": rows, "valid": [dict(row, split="valid") for row in rows]}
    trainer.low_light_config = config
    trainer.model = SimpleNamespace(stride=torch.tensor([32]))
    try:
        yield SimpleNamespace(trainer=trainer, cls=cls, args=args, rows=rows, dataset_class=ReadOnlyDetectionDataset)
    finally:
        Image.open = original_open


def test_real_dataset_source_identity_epoch_placement_and_validation(integration, monkeypatch):
    from ultralytics.data.augment import Format, RandomHSV, Mosaic, RandomPerspective, RandomFlip
    state = integration
    train = state.trainer.build_dataset("train-list", mode="train", batch=4)
    valid = state.trainer.build_dataset("valid-list", mode="val", batch=4)
    assert valid.low_light_hook is None
    assert isinstance(train.transforms.transforms[-1], Format)
    assert train.transforms.transforms[-2] is train.low_light_hook
    assert any(isinstance(op, RandomHSV) for op in train.transforms.transforms[:-2])
    assert all(not isinstance(op, t.LowLightTrainingHook) for op in valid.transforms.transforms)
    assert train.low_light_hook.source_identities[str(state.rows[0]["image"]).replace("\\", "/")] == (
        "synthetic/train/panel0.png"
    )
    state.trainer.train_loader = SimpleNamespace(dataset=train)
    state.trainer.epoch = 3
    t.propagate_training_epoch(state.trainer)
    assert train.low_light_hook.epoch == 3
    trace = []
    def observe(cls):
        original = cls.__call__
        def wrapped(self, labels):
            trace.append(cls.__name__)
            return original(self, labels)
        monkeypatch.setattr(cls, "__call__", wrapped)
    for cls in (Mosaic, RandomPerspective, RandomHSV, RandomFlip, t.LowLightTrainingHook, Format):
        observe(cls)
    before = {row[k]: row[k].read_bytes() for row in state.rows for k in ("image", "label")}
    item = train[0]  # Installed mosaic, geometry, HSV, low light and Format; no model.
    assert item["img"].shape == (3, 640, 640)
    assert trace.index("Mosaic") < trace.index("RandomHSV") < trace.index("LowLightTrainingHook") < trace.index("Format")
    assert trace.index("RandomPerspective") < trace.index("LowLightTrainingHook")
    assert max(i for i, event in enumerate(trace) if event == "RandomFlip") < trace.index("LowLightTrainingHook")
    assert trace.count("LowLightTrainingHook") == 1
    trace.clear()
    valid[0]
    assert "LowLightTrainingHook" not in trace
    assert all(path.read_bytes() == data for path, data in before.items())
    assert set(state.rows[0]["image"].parent.iterdir()) == set(before)
    labels = train.get_image_and_label(0)
    first = train.low_light_hook(labels)
    train.get_image_and_label(1)  # Neither loading/caching nor access order is scientific epoch identity.
    t.propagate_training_epoch(state.trainer)
    assert train.low_light_hook(labels)["img"].tobytes() == first["img"].tobytes()
    state.trainer.epoch = 4
    t.propagate_training_epoch(state.trainer)
    assert train.low_light_hook.epoch == 4
    train.close_mosaic(deepcopy(state.trainer.args))
    assert train.transforms.transforms[-2] is train.low_light_hook
    assert train.low_light_hook.epoch == 4
    assert train.transforms.transforms[0].transforms[0].p == 0.0
    state.trainer.epoch = 3
    t.propagate_training_epoch(state.trainer)
    assert train.low_light_hook(labels)["img"].tobytes() == first["img"].tobytes()


@pytest.mark.parametrize("split,augment", [("valid", False), ("valid", True), ("test", True), ("train", False)])
def test_dataset_rejects_low_light_outside_augmented_training(integration, split, augment):
    with pytest.raises(ValueError):
        integration.dataset_class(records=[dict(integration.rows[0], split=split)],
            low_light_config=t.canonical_config(), augment=augment, hyp=integration.trainer.args)


def test_dataset_rejects_brightness_jitter_and_locked_trainer_source(integration):
    args = deepcopy(integration.trainer.args)
    args.hsv_v = .4
    with pytest.raises(ValueError, match="hsv_v"):
        integration.dataset_class(records=integration.rows, low_light_config=t.canonical_config(), augment=True, hyp=args)
    with pytest.raises(ValueError, match="approved"):
        integration.trainer.build_dataset("locked-test-list", mode="test")
    integration.trainer.args.workers = 1
    with pytest.raises(ValueError, match="workers"):
        t.propagate_training_epoch(integration.trainer)


def test_trainer_registers_and_dispatches_real_epoch_callback_without_training(integration, monkeypatch, tmp_path):
    from ultralytics.models.yolo.detect import DetectionTrainer
    from ultralytics.utils import callbacks
    state = integration
    def fake_init(self, **kwargs):
        self.args = state.trainer.args
        self.save_dir = tmp_path
        self.device = SimpleNamespace(type="cuda")  # Metadata only; no device allocation or model construction.
        self.callbacks = callbacks.get_default_callbacks()
    monkeypatch.setattr(DetectionTrainer, "__init__", fake_init)
    monkeypatch.setattr(DetectionTrainer, "train", lambda _: pytest.fail("Training forbidden"))
    trainer = state.cls(records=state.trainer.records, development_data=state.trainer.data,
        expected_output=tmp_path, evidence={}, overrides=state.args, low_light_config=t.canonical_config())
    assert t.propagate_training_epoch in trainer.callbacks["on_train_epoch_start"]
    dataset = SimpleNamespace(set_training_epoch=lambda epoch: received.append(epoch))
    trainer.train_loader = SimpleNamespace(dataset=dataset)
    received = []
    for epoch in (0, 1, 9, 9, 90):
        trainer.epoch = epoch
        trainer.run_callbacks("on_train_epoch_start")
    assert received == [0, 1, 9, 9, 90]


@pytest.mark.parametrize("key,value", [("workers", 1), ("hsv_v", .4), ("lr0", .2), ("deterministic", False)])
def test_trainer_rejects_runtime_override_before_initializing(integration, monkeypatch, tmp_path, key, value):
    from ultralytics.models.yolo.detect import DetectionTrainer
    monkeypatch.setattr(DetectionTrainer, "__init__", lambda *a, **kw: pytest.fail("Must reject before setup"))
    args = dict(integration.args, **{key: value})
    with pytest.raises(ValueError, match="runtime argument"):
        integration.cls(records=integration.trainer.records, development_data=integration.trainer.data,
            expected_output=tmp_path, evidence={}, overrides=args, low_light_config=t.canonical_config())


def test_detection_config_route_output_and_arguments(tmp_path):
    from detection.training.config import load_config, run_directory, validate_config
    from detection.training.trainer import training_arguments
    config = load_config(ROOT / "configs/low_light/ll_detector_01.yaml", ROOT)
    assert config == t.load_config()
    assert run_directory(config, ROOT) == (ROOT / "outputs/training/low_light/LL-DETECTOR-01").resolve()
    args = training_arguments(config, ROOT, ROOT / t.CHECKPOINT_PATH, tmp_path / "synthetic.yaml")
    assert args["model"] == str(ROOT / t.CHECKPOINT_PATH)
    assert args["hsv_v"] == 0.0 and args["split"] == "val"
    for key, value in config["training"].items():
        assert args[key] == value
    with pytest.raises(ValueError, match="checkpoint"):
        training_arguments(config, ROOT, Path("DET-IMPROVED.pt"), Path("unused.yaml"))
    config["experiment"]["id"] = "DET-IMPROVED"
    with pytest.raises(ValueError):
        validate_config(config, ROOT)


def test_parent_checkpoint_missing_mismatch_and_no_acquisition(tmp_path, monkeypatch):
    from detection.training import trainer
    config = t.canonical_config()
    monkeypatch.setattr(trainer.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Network forbidden"))
    with pytest.raises(ValueError, match="local-only"):
        trainer.checkpoint(config, tmp_path, acquire=True)
    with pytest.raises(FileNotFoundError, match="DET-FINAL-v1"):
        trainer.checkpoint(config, tmp_path, acquire=False)
    path = tmp_path / t.CHECKPOINT_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic checkpoint sentinel, not a model")
    with pytest.raises(ValueError, match="SHA-256"):
        trainer.checkpoint(config, tmp_path, acquire=False)
    monkeypatch.setattr(trainer, "sha256", lambda p: t.CHECKPOINT_SHA256)
    verified, receipt = trainer.checkpoint(config, tmp_path, acquire=False)
    assert verified == path.resolve() and receipt["model_id"] == "DET-FINAL-v1"
    assert receipt["sha256"] == t.CHECKPOINT_SHA256


def test_duplicate_yaml_rejected_through_detector_loader(tmp_path):
    from detection.training.config import load_config
    path = tmp_path / "ll_detector_01.yaml"
    path.write_text(yaml.safe_dump(t.canonical_config()) + "schema_version: 1\n")
    with pytest.raises(ValueError, match="unique"):
        load_config(path, ROOT)
