import json
from pathlib import Path

import pytest

from detection.generalization.manifest import canonical, object_hash
from detection.generalization.damsegment_preaccess import INFERENCE
from detection.generalization.schema import validate_manifest
from detection.generalization.taxonomy import (
    crosswalk_dataset,
    map_region_labels,
    scored_classes,
    shared_classes,
    validate_crosswalk,
)


ROOT = Path(__file__).resolve().parents[2]

DAM_ONTOLOGY = (
    ROOT
    / "configs/generalization/damsegment_ontology_crosswalk.yaml"
)

CODEBRIM_ONTOLOGY = (
    ROOT
    / "configs/generalization/ontology_crosswalk.yaml"
)

MANIFEST = (
    ROOT
    / "configs/generalization/experiments/GEN-DAMSEGMENT-ZS-001.json"
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_damsegment_portable_scientific_contract():
    manifest = load(MANIFEST)

    assert validate_manifest(manifest) == manifest
    assert manifest["dataset"]["identity"] == "DamSegment"
    assert manifest["dataset"]["version"] == "v1"
    assert manifest["dataset"]["split"] == "Damage Detection"
    assert manifest["dataset"]["sha256"] == (
        "a75a29496ba8bb76f49db5a36b64a992"
        "0911b5e4c420f634a4390deb418e14df"
    )
    assert manifest["manifest_kind"] == "portable_scientific_contract"
    assert manifest["phase"] == "frozen"
    assert manifest["frozen"] is True
    assert manifest["scientific_execution_authorized"] is True
    assert manifest["heldout_evaluation_count"] == 0
    assert "evaluation_git_sha" not in manifest
    assert manifest["external_review"]["leakage_audit_passed"] is True
    assert (
        manifest["external_review"]["leakage_gate_status"]
        == "PASS_NO_CANDIDATES"
    )


def test_damsegment_crosswalk_is_exact():
    ontology = validate_crosswalk(
        load(DAM_ONTOLOGY),
        expected_dataset="DamSegment",
    )

    assert crosswalk_dataset(ontology) == "DamSegment"
    assert shared_classes(ontology) == [0, 1]
    assert ontology["source_class_ids"] == {
        "0": "Crack",
        "1": "Spalling",
    }
    assert (
        ontology["external_aggregate_label"]
        == "shared-class DamSegment mAP"
    )


def test_damsegment_region_mapping():
    ontology = load(DAM_ONTOLOGY)

    mapped, excluded = map_region_labels(
        ["Crack", "Spalling"],
        ontology,
    )

    assert mapped == [0, 1]
    assert excluded == []


def test_unapproved_damsegment_mapping_fails_closed():
    ontology = load(DAM_ONTOLOGY)
    ontology["mappings"][2] = {
        "gyu_id": 2,
        "external_label": "Crack",
        "status": "approved",
        "approval": "invalid synthetic approval",
    }

    with pytest.raises(ValueError):
        validate_crosswalk(ontology)


def test_unknown_external_label_fails_closed():
    ontology = load(DAM_ONTOLOGY)

    with pytest.raises(ValueError):
        map_region_labels(["Efflorescence"], ontology)


def test_scored_classes_are_dataset_driven():
    dam = load(DAM_ONTOLOGY)
    codebrim = load(CODEBRIM_ONTOLOGY)

    assert scored_classes("DamSegment", dam) == [0, 1]
    assert scored_classes("CODEBRIM", codebrim) == [0, 1, 4]
    assert scored_classes("GYU-DET", codebrim) == [0, 1, 2, 3, 4, 5]


def test_crosswalk_dataset_mismatch_rejected():
    with pytest.raises(ValueError):
        validate_crosswalk(
            load(DAM_ONTOLOGY),
            expected_dataset="CODEBRIM",
        )


def test_unknown_scoring_dataset_fails_closed():
    with pytest.raises(ValueError):
        scored_classes(
            "UNKNOWN-DATASET",
            load(DAM_ONTOLOGY),
        )


def test_explicit_unknown_ontology_dataset_fails_closed():
    ontology = load(DAM_ONTOLOGY)
    ontology["external_dataset"] = "UNKNOWN-DATASET"

    with pytest.raises(ValueError):
        validate_crosswalk(ontology)


def test_codebrim_legacy_crosswalk_preserved():
    ontology = load(CODEBRIM_ONTOLOGY)

    assert crosswalk_dataset(ontology) == "CODEBRIM"
    assert shared_classes(ontology) == [0, 1, 4]
    assert (
        ontology["external_aggregate_label"]
        == "shared-class CODEBRIM mAP"
    )


def test_damsegment_preaccess_cannot_be_scientific_manifest():
    manifest = load(MANIFEST)

    with pytest.raises(ValueError):
        validate_manifest(
            manifest,
            scientific=True,
        )


def test_prepared_inventory_binding_and_counts():
    manifest = load(MANIFEST)
    dataset = manifest["dataset"]

    assert dataset["sha256"] == (
        "a75a29496ba8bb76f49db5a36b64a992"
        "0911b5e4c420f634a4390deb418e14df"
    )

    assert dataset["prepared_inventory_sha256"] == (
        dataset["sha256"]
    )

    assert dataset[
        "prepared_artifact_file_sha256"
    ] == (
        "dabc0bb394127d7dc5d90b8441bdb64f"
        "91e7b6606c07994e300b4a6aeb124f70"
    )

    assert (
        dataset["image_count"]
        == dataset["prepared_image_count"]
        == 1500
    )

    assert (
        dataset["annotation_instances"]
        == dataset["prepared_region_count"]
        == 19710
    )

    assert dataset[
        "prepared_regions_per_aegis_class"
    ] == {
        "0": 19229,
        "1": 481,
    }

    assert sum(
        dataset[
            "prepared_regions_per_aegis_class"
        ].values()
    ) == 19710

    assert dataset[
        "yolo_annotation_files"
    ] == 1500

    assert dataset[
        "pascal_voc_style_json_files"
    ] == 1500


def test_manifest_records_exact_crosswalk_and_exclusions():
    dataset = load(MANIFEST)["dataset"]

    assert dataset["approved_crosswalk"] == {
        "0": {
            "source_label": "Crack",
            "aegis_id": 0,
            "aegis_label": "Crack",
        },
        "1": {
            "source_label": "Spalling",
            "aegis_id": 1,
            "aegis_label": "Breakage",
        },
    }

    assert dataset[
        "excluded_aegis_classes"
    ] == {
        "2": "Honeycombing",
        "3": "Hole",
        "4": "Exposed Reinforcement",
        "5": "Seepage",
    }


def test_external_benchmark_cannot_be_tuning_or_test_replacement():
    policy = load(MANIFEST)[
        "dataset"
    ]["external_use_policy"]

    assert policy == {
        "used_for_training": False,
        "used_for_tuning": False,
        "used_for_model_selection": False,
        "replacement_for_gyu_locked_test": False,
    }


def test_manifest_canonical_hash_is_order_independent():
    manifest = load(MANIFEST)

    reversed_manifest = dict(
        reversed(list(manifest.items()))
    )

    assert canonical(manifest) == canonical(
        reversed_manifest
    )

    assert object_hash(manifest) == object_hash(
        reversed_manifest
    )


def test_frozen_model_and_inference_contract():
    manifest = load(MANIFEST)

    assert manifest["model_id"] == "DET-FINAL-v1"

    assert manifest["checkpoint_sha256"] == (
        "4c7a32c9b40c0795bbe59aca5952a063"
        "1e1524ec731ad2c7441cccb1b44f71c3"
    )

    assert (
        manifest["resolved_inference_config"]
        == INFERENCE
    )


def test_prepared_inventory_drift_rejected():
    manifest = load(MANIFEST)

    manifest["dataset"][
        "prepared_region_count"
    ] -= 1

    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_unknown_legacy_ontology_version_fails_closed():
    ontology = load(CODEBRIM_ONTOLOGY)
    ontology["version"] = "unknown-legacy-v999"

    with pytest.raises(ValueError):
        validate_crosswalk(ontology)


def test_locked_test_raw_access_is_not_required_or_claimed():
    manifest = load(MANIFEST)

    assert manifest["external_review"][
        "locked_gyu_test_raw_accessed"
    ] is False

    assert manifest["leakage_evidence"][
        "locked_gyu_test_raw_accessed"
    ] is False

    assert manifest[
        "heldout_rerun_authorized"
    ] is False
