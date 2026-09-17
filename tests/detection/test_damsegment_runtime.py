from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from detection.generalization.damsegment_runtime import (
    PORTABLE_KIND,
    RUNTIME_KIND,
    execution_plan,
    inference_batch_ranges,
    prediction_kwargs,
    validate_portable_contract,
    validate_runtime_manifest,
    validate_scoring_contract,
)
from detection.generalization.manifest import (
    derive_runtime_manifest,
    frozen_gate,
    object_hash,
)
from detection.generalization.prediction_export import (
    normalize_predictions,
    serialize_predictions,
)
from detection.generalization.schema import (
    CLASSES,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[2]

MANIFEST = (
    ROOT
    / "configs/generalization/experiments/"
      "GEN-DAMSEGMENT-ZS-001.json"
)

ONTOLOGY = (
    ROOT
    / "configs/generalization/"
      "damsegment_ontology_crosswalk.yaml"
)

PROTOCOL = (
    ROOT
    / "configs/generalization/"
      "damsegment_protocol.yaml"
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def portable():
    return load(MANIFEST)


def fake_git(head):
    def run(command, cwd=None, text=None):
        if command[:3] == ["git", "status", "--porcelain"]:
            return ""
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return head + "\n"
        raise AssertionError(command)

    return run


def derived_runtime(tmp_path, head="a" * 40):
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"synthetic-checkpoint")

    m = portable()

    with patch(
        "detection.generalization.manifest.subprocess.check_output",
        side_effect=fake_git(head),
    ), patch(
        "detection.generalization.manifest.file_hash",
        return_value=m["checkpoint_sha256"],
    ):
        runtime = derive_runtime_manifest(
            MANIFEST,
            ROOT,
            checkpoint,
        )

    return runtime


def test_portable_contract_is_frozen_authorized_and_unexecuted():
    m = portable()

    assert m["manifest_kind"] == PORTABLE_KIND
    assert m["phase"] == "frozen"
    assert m["frozen"] is True
    assert m["scientific_execution_authorized"] is True
    assert m["heldout_evaluation_count"] == 0
    assert "evaluation_git_sha" not in m

    assert validate_manifest(m) == m
    assert validate_portable_contract(m) == m

    with pytest.raises(ValueError):
        validate_manifest(m, scientific=True)


def test_portable_contract_requires_execution_authorization():
    m = portable()
    m["scientific_execution_authorized"] = False

    with pytest.raises(ValueError):
        validate_manifest(m)


def test_portable_count_must_remain_zero_before_run():
    m = portable()
    m["heldout_evaluation_count"] = 1

    with pytest.raises(ValueError):
        validate_manifest(m)


def test_wrong_dataset_or_inventory_identity_rejected():
    for key in (
        "sha256",
        "prepared_inventory_sha256",
    ):
        m = portable()
        m["dataset"][key] = "0" * 64

        with pytest.raises(ValueError):
            validate_manifest(m)

    m = portable()
    m["dataset"]["image_count"] = 1499

    with pytest.raises(ValueError):
        validate_manifest(m)


def test_changed_inference_settings_rejected():
    m = portable()
    m["resolved_inference_config"]["imgsz"] = 800

    with pytest.raises(ValueError):
        validate_manifest(m)


def test_runtime_derivation_binds_current_head_and_absolute_checkpoint(
    tmp_path,
):
    head = "a" * 40
    runtime = derived_runtime(tmp_path, head)

    assert runtime["manifest_kind"] == RUNTIME_KIND
    assert runtime["evaluation_git_sha"] == head
    assert Path(runtime["checkpoint_path"]).is_absolute()
    assert (
        runtime["portable_contract_sha256"]
        == object_hash(portable())
    )
    assert runtime["heldout_evaluation_count"] == 0

    assert (
        validate_manifest(
            runtime,
            scientific=True,
        )
        == runtime
    )
    assert validate_runtime_manifest(runtime) == runtime


def test_runtime_wrong_checkpoint_hash_rejected_before_derivation(
    tmp_path,
):
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"wrong")

    m = portable()

    with patch(
        "detection.generalization.manifest.subprocess.check_output",
        side_effect=fake_git("a" * 40),
    ), patch(
        "detection.generalization.manifest.file_hash",
        return_value="0" * 64,
    ):
        with pytest.raises(
            ValueError,
            match="Checkpoint hash",
        ):
            derive_runtime_manifest(
                MANIFEST,
                ROOT,
                checkpoint,
            )


def test_scoring_class_scope_exactly_zero_and_one(tmp_path):
    runtime = derived_runtime(tmp_path)

    ontology = load(ONTOLOGY)
    protocol = load(PROTOCOL)

    assert (
        validate_scoring_contract(
            runtime,
            ontology,
            protocol,
        )["external_dataset"]
        == "DamSegment"
    )

    bad = deepcopy(ontology)

    for mapping in bad["mappings"]:
        if mapping["gyu_id"] == 1:
            mapping["external_label"] = None
            mapping["status"] = "unmapped"
            mapping.pop("approval", None)

    with pytest.raises(ValueError):
        validate_scoring_contract(
            runtime,
            bad,
            protocol,
        )


def test_frozen_gate_accepts_derived_runtime_and_rejects_wrong_head(
    tmp_path,
):
    head = "a" * 40
    runtime = derived_runtime(tmp_path, head)
    ontology = load(ONTOLOGY)
    protocol = load(PROTOCOL)

    def gate_git(command, cwd=None, text=None):
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return head + "\n"
        if command[:3] == ["git", "status", "--porcelain"]:
            return ""
        if command[:2] == ["git", "status"]:
            return ""
        raise AssertionError(command)

    with patch(
        "detection.generalization.manifest.subprocess.check_output",
        side_effect=gate_git,
    ), patch(
        "detection.generalization.manifest.file_hash",
        return_value=runtime["checkpoint_sha256"],
    ):
        frozen_gate(
            runtime,
            ROOT,
            ontology,
            protocol,
        )

    wrong = deepcopy(runtime)
    wrong["evaluation_git_sha"] = "b" * 40
    wrong["runtime_bindings"]["evaluation_git_sha"] = (
        "b" * 40
    )

    with patch(
        "detection.generalization.manifest.subprocess.check_output",
        side_effect=gate_git,
    ):
        with pytest.raises(
            ValueError,
            match="Evaluation Git SHA",
        ):
            frozen_gate(
                wrong,
                ROOT,
                ontology,
                protocol,
            )


class Boxes:
    def __init__(self, rows):
        self.xyxy = [r[0] for r in rows]
        self.cls = [r[1] for r in rows]
        self.conf = [r[2] for r in rows]


class Result:
    def __init__(self, rows):
        self.orig_shape = (640, 640)
        self.names = CLASSES
        self.boxes = Boxes(rows)


def test_runtime_normalized_export_is_valid_and_deterministic(
    tmp_path,
):
    runtime = derived_runtime(tmp_path)

    rows = [
        ([1, 2, 30, 40], 0.0, 0.2),
        ([10, 20, 50, 60], 1.0, 0.9),
    ]

    a = normalize_predictions(
        [
            ("Images/z.jpg", Result(rows)),
            ("Images/a.jpg", Result([])),
        ],
        runtime,
    )

    b = normalize_predictions(
        [
            ("Images/a.jpg", Result([])),
            ("Images/z.jpg", Result(list(reversed(rows)))),
        ],
        runtime,
    )

    assert serialize_predictions(a, runtime) == (
        serialize_predictions(b, runtime)
    )
    assert len(a["predictions"]) == 2
    assert (
        a["model_provenance"]["evaluation_git_sha"]
        == runtime["evaluation_git_sha"]
    )


def test_prediction_kwargs_are_frozen_and_explicit(tmp_path):
    runtime = derived_runtime(tmp_path)
    kwargs = prediction_kwargs(runtime)

    assert kwargs["imgsz"] == 640
    assert kwargs["batch"] == 8
    assert kwargs["device"] == "0"
    assert kwargs["workers"] == 0
    assert kwargs["rect"] is True
    assert kwargs["quantize"] == 16
    assert kwargs["conf"] == 0.001
    assert kwargs["iou"] == 0.7
    assert kwargs["max_det"] == 300
    assert kwargs["nms"] is False
    assert kwargs["augment"] is False
    assert kwargs["agnostic_nms"] is False
    assert kwargs["single_cls"] is False
    assert kwargs["cache"] is False
    assert kwargs["compile"] is False
    assert kwargs["stream"] is False

    # These frozen controls are runner-owned structural semantics,
    # not valid Ultralytics predict keyword arguments.
    assert "pad" not in kwargs
    assert "shuffle" not in kwargs
    assert "drop_last" not in kwargs

    bad = deepcopy(runtime)
    bad["resolved_inference_config"]["conf"] = 0.25

    with pytest.raises(ValueError):
        prediction_kwargs(bad)


def test_execution_plan_enforces_structural_frozen_settings(
    tmp_path,
):
    runtime = derived_runtime(tmp_path)
    plan = execution_plan(runtime)

    assert plan["batch_size"] == 8
    assert plan["workers"] == 0
    assert plan["serial_decode"] is True
    assert plan["preserve_prepared_order"] is True
    assert plan["drop_last"] is False
    assert plan["cache"] is False
    assert plan["required_height"] == 640
    assert plan["required_width"] == 640
    assert plan["frozen_pad"] == 0.5
    assert plan["effective_pixel_padding"] == 0

    for key, value in (
        ("workers", 1),
        ("pad", 0.0),
        ("shuffle", True),
        ("drop_last", True),
        ("cache", True),
        ("end2end", False),
        ("FP16", False),
    ):
        bad = deepcopy(runtime)
        bad["resolved_inference_config"][key] = value

        with pytest.raises(ValueError):
            execution_plan(bad)


def test_batch_ranges_preserve_order_and_keep_final_partial_batch():
    ranges = inference_batch_ranges(1500, 8)

    assert len(ranges) == 188
    assert ranges[0] == (0, 8)
    assert ranges[-1] == (1496, 1500)

    flattened = [
        index
        for start, stop in ranges
        for index in range(start, stop)
    ]

    assert flattened == list(range(1500))


def test_absolute_checkpoint_locator_does_not_replace_model_identity(
    tmp_path,
):
    runtime = derived_runtime(tmp_path)

    assert Path(runtime["checkpoint_path"]).is_absolute()
    assert runtime["checkpoint_sha256"] == (
        "4c7a32c9b40c0795bbe59aca5952a063"
        "1e1524ec731ad2c7441cccb1b44f71c3"
    )
