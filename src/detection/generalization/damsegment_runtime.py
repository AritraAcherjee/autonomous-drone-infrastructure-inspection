"""Frozen DamSegment scientific contract, runtime binding and inference bridge."""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import random
import time

PORTABLE_KIND = "portable_scientific_contract"
RUNTIME_KIND = "runtime_scientific_manifest"

FREEZE_APPROVAL = (
    "00 Control Center scientific authorization 2026-09-17"
)

EXPECTED_SCORING_CLASSES = [0, 1]


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _object_hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def validate_portable_contract(m):
    """Validate committed portable scientific decisions without runtime locators."""
    from .damsegment_preaccess import (
        DATASET,
        EXPERIMENT,
        INFERENCE,
        LEAKAGE,
        METRICS,
        PROVENANCE,
    )
    from .schema import CLASSES, digest, nonempty, require

    require(
        m.get("manifest_kind") == PORTABLE_KIND,
        "Not a portable scientific contract",
    )
    require(
        m.get("experiment_id") == EXPERIMENT,
        "Wrong DamSegment experiment",
    )
    require(
        m.get("phase") == "frozen"
        and m.get("frozen") is True,
        "Portable contract must be frozen",
    )
    require(
        m.get("scientific_execution_authorized") is True,
        "DamSegment scientific execution is not authorized",
    )
    require(
        m.get("heldout_evaluation_count") == 0,
        "Portable pre-run evaluation count must remain zero",
    )
    require(
        m.get("heldout_rerun_authorized") is False,
        "DamSegment rerun must remain unauthorized",
    )
    require(
        m.get("freeze_approval") == FREEZE_APPROVAL,
        "Unexpected scientific freeze approval",
    )

    require(
        "evaluation_git_sha" not in m,
        "Portable contract must not contain runtime Git binding",
    )

    for key, value in PROVENANCE.items():
        require(
            m.get(key) == value,
            "Frozen provenance differs: " + key,
        )

    require(
        _canonical(m.get("resolved_inference_config"))
        == _canonical(INFERENCE),
        "Frozen inference differs",
    )

    for key, value in METRICS.items():
        require(
            _canonical(m.get(key)) == _canonical(value),
            "Frozen metric differs: " + key,
        )

    require(
        m.get("class_mapping")
        == {str(k): v for k, v in CLASSES.items()},
        "Class mapping differs",
    )

    require(
        _canonical(m.get("dataset")) == _canonical(DATASET),
        "DamSegment dataset identity/provenance differs",
    )

    review = m.get("external_review", {})
    require(
        review.get("taxonomy_approved") is True
        and review.get("leakage_audit_passed") is True
        and review.get("leakage_gate_status")
        == "PASS_NO_CANDIDATES"
        and review.get("locked_gyu_test_raw_accessed") is False,
        "DamSegment external review is incomplete",
    )

    require(
        _canonical(m.get("leakage_evidence"))
        == _canonical(LEAKAGE),
        "Leakage evidence differs",
    )

    require(
        m.get("ontology_version")
        == "gyu-damsegment-v1-approved",
        "DamSegment ontology version differs",
    )
    require(
        m.get("protocol_version")
        == "generalization-v1-damsegment-preaccess",
        "DamSegment protocol version differs",
    )

    for key in (
        "ontology_sha256",
        "ontology_file_sha256",
        "protocol_sha256",
        "protocol_file_sha256",
    ):
        require(digest(m.get(key)), "Invalid " + key)

    require(
        m.get("image_size") == [640, 640],
        "DamSegment image size differs",
    )
    require(m.get("seed") == 42, "DamSegment seed differs")

    training = m.get("training_config")
    require(
        isinstance(training, dict) and training,
        "Missing DET-FINAL training provenance",
    )
    require(
        training.get("det_final_manifest_path")
        == "configs/detection/det_final_v1.yaml",
        "Unexpected training provenance source",
    )
    require(
        digest(training.get("det_final_manifest_sha256")),
        "Invalid DET-FINAL manifest hash",
    )
    require(
        training.get("training_git_sha")
        == PROVENANCE["training_git_sha"],
        "Training Git provenance differs",
    )
    require(
        training.get("source_experiment") == "DET-BASELINE",
        "Unexpected source training experiment",
    )
    require(
        training.get("training_config_reference") is not None
        and training.get("resolved_config_reference") is not None,
        "Missing canonical training config references",
    )

    evidence = m.get("validation_evidence")
    require(
        isinstance(evidence, dict) and evidence,
        "Missing DET-FINAL validation evidence",
    )
    require(
        evidence.get("det_final_manifest_path")
        == "configs/detection/det_final_v1.yaml",
        "Unexpected validation evidence source",
    )
    require(
        digest(evidence.get("det_final_manifest_sha256")),
        "Invalid validation manifest hash",
    )
    require(
        isinstance(evidence.get("evidence_index"), dict)
        and digest(
            evidence["evidence_index"].get("sha256")
        ),
        "Invalid DET-FINAL evidence index",
    )
    require(
        evidence.get("test_accessed_at_freeze") is False,
        "Validation evidence improperly claims held-out access",
    )
    require(
        nonempty(evidence.get("selection_basis")),
        "Missing validation selection basis",
    )

    env = m.get("environment", {})
    packages = env.get("packages", {})

    require(
        env.get("python") == "3.11.15",
        "Unexpected detector Python",
    )
    require(
        packages.get("ultralytics") == "8.4.145"
        and packages.get("torch") == "2.14.0+cu130"
        and packages.get("torchvision") == "0.29.0+cu130",
        "Unexpected detector package environment",
    )

    return m


def validate_runtime_manifest(m):
    """Validate runtime-only bindings and prove portable decisions are unchanged."""
    from .schema import digest, require

    require(
        m.get("manifest_kind") == RUNTIME_KIND,
        "Not a runtime scientific manifest",
    )
    require(
        digest(m.get("evaluation_git_sha"), 40),
        "Runtime evaluation Git SHA required",
    )
    require(
        Path(str(m.get("checkpoint_path", ""))).is_absolute(),
        "Runtime checkpoint path must be absolute",
    )
    require(
        digest(m.get("portable_contract_sha256")),
        "Portable contract object hash required",
    )
    require(
        digest(m.get("portable_contract_file_sha256")),
        "Portable contract file hash required",
    )

    bindings = m.get("runtime_bindings")
    require(
        isinstance(bindings, dict),
        "Runtime bindings required",
    )
    require(
        bindings.get("evaluation_git_sha")
        == m["evaluation_git_sha"],
        "Runtime Git binding differs",
    )
    require(
        bindings.get("checkpoint_path")
        == m["checkpoint_path"],
        "Runtime checkpoint locator differs",
    )
    require(
        bindings.get("portable_checkpoint_path")
        == "outputs/training/defect_detection/"
           "DET-BASELINE/weights/best.pt",
        "Portable checkpoint locator differs",
    )

    portable = deepcopy(m)
    portable["manifest_kind"] = PORTABLE_KIND
    portable["checkpoint_path"] = bindings[
        "portable_checkpoint_path"
    ]

    for key in (
        "evaluation_git_sha",
        "portable_contract_sha256",
        "portable_contract_file_sha256",
        "runtime_bindings",
    ):
        portable.pop(key, None)

    validate_portable_contract(portable)

    require(
        _object_hash(portable)
        == m["portable_contract_sha256"],
        "Runtime manifest does not bind portable contract object",
    )

    return m


def validate_scoring_contract(m, ontology, protocol):
    """Validate ontology/protocol scope without opening external images."""
    from .schema import require
    from .taxonomy import scored_classes, validate_crosswalk

    validate_runtime_manifest(m)

    ontology = validate_crosswalk(
        ontology,
        expected_dataset="DamSegment",
    )

    require(
        scored_classes("DamSegment", ontology)
        == EXPECTED_SCORING_CLASSES,
        "DamSegment scoring class scope differs",
    )

    require(
        _object_hash(protocol) == m["protocol_sha256"],
        "DamSegment protocol hash differs",
    )
    require(
        protocol.get("status") == "frozen",
        "DamSegment protocol is not frozen",
    )
    require(
        protocol.get("resolved_inference_config")
        == m["resolved_inference_config"],
        "Protocol inference configuration differs",
    )

    for key in (
        "ap_ious",
        "ap_confidence_floor",
        "operating_confidence",
        "matching_iou",
        "nms_iou",
        "nms_mode",
        "max_detections",
    ):
        require(
            protocol.get(key) == m.get(key),
            "Protocol disagrees: " + key,
        )

    return ontology


def validate_prepared_payload(
    m,
    prepared,
    prepared_file_sha256,
):
    """Validate the frozen derived GT inventory without opening raw images."""
    from .schema import require, validate_records

    dataset = m["dataset"]

    require(
        prepared_file_sha256
        == dataset["prepared_artifact_file_sha256"],
        "Prepared JSON file hash differs",
    )
    require(
        _object_hash(prepared) == dataset["sha256"],
        "Prepared inventory object hash differs",
    )

    images = prepared.get("images")
    regions = prepared.get("regions")

    validate_records(images, [], regions)

    counts = Counter(
        label
        for region in regions
        for label in region["labels"]
    )

    region_images = {r["image_id"] for r in regions}

    require(
        len(images) == 1500,
        "DamSegment image count differs",
    )
    require(
        len(regions) == 19710,
        "DamSegment region count differs",
    )
    require(
        counts == Counter({0: 19229, 1: 481}),
        "DamSegment GT class counts differ",
    )
    require(
        len(set(images) - region_images) == 3,
        "DamSegment empty-image count differs",
    )

    return images, regions


def resolve_image_paths(dataset_root, images):
    """Resolve frozen source-relative image identities without reading pixels."""
    from .schema import require

    root = Path(dataset_root).resolve()
    resolved = []

    for identity in images:
        posix = PurePosixPath(identity)

        require(
            not posix.is_absolute()
            and ".." not in posix.parts
            and len(posix.parts) == 2
            and posix.parts[0] == "Images",
            "Unsafe DamSegment image identity",
        )

        path = root.joinpath(*posix.parts)

        require(
            path.is_file(),
            "Missing DamSegment image: " + identity,
        )

        resolved.append(path)

    require(
        len(resolved) == 1500,
        "Resolved DamSegment image count differs",
    )

    return resolved


def execution_plan(m):
    """Map frozen settings to explicit runner-controlled semantics."""
    from .damsegment_preaccess import INFERENCE
    from .schema import require

    cfg = m["resolved_inference_config"]

    require(
        _canonical(cfg) == _canonical(INFERENCE),
        "Frozen inference settings differ",
    )

    require(
        cfg["device"] == "CUDA:0",
        "Frozen CUDA device differs",
    )
    require(
        cfg["workers"] == 0,
        "DamSegment runner requires workers=0",
    )
    require(
        cfg["pad"] == 0.5,
        "Frozen padding setting differs",
    )
    require(
        cfg["shuffle"] is False,
        "DamSegment runner requires shuffle=false",
    )
    require(
        cfg["drop_last"] is False,
        "DamSegment runner requires drop_last=false",
    )
    require(
        cfg["cache"] is False,
        "DamSegment runner requires cache=false",
    )
    require(
        cfg["end2end"] is True,
        "DamSegment runner requires end2end=true",
    )
    require(
        cfg["FP16"] is True,
        "DamSegment runner requires FP16=true",
    )

    return {
        "batch_size": cfg["batch"],
        "workers": 0,
        "serial_decode": True,
        "preserve_prepared_order": True,
        "drop_last": False,
        "cache": False,
        "required_height": cfg["imgsz"],
        "required_width": cfg["imgsz"],
        "frozen_pad": cfg["pad"],
        "effective_pixel_padding": 0,
        "precision_binding": (
            "FP16=true -> Ultralytics 8.4.145 quantize=16 "
            "-> AutoBackend fp16=True"
        ),
        "end2end_binding": (
            "end2end=true -> nms=False plus loaded-head "
            "end2end assertion"
        ),
    }


def inference_batch_ranges(count, batch_size):
    """Deterministic non-dropping batch ranges."""
    from .schema import require

    require(
        type(count) is int and count >= 0,
        "Invalid inference item count",
    )
    require(
        type(batch_size) is int and batch_size > 0,
        "Invalid inference batch size",
    )

    return [
        (start, min(start + batch_size, count))
        for start in range(0, count, batch_size)
    ]


def prediction_kwargs(m):
    """Translate frozen controls into valid Ultralytics 8.4.145 arguments."""
    cfg = m["resolved_inference_config"]

    # Validate every direct and structural frozen setting first.
    execution_plan(m)

    return {
        "imgsz": cfg["imgsz"],
        "batch": cfg["batch"],
        "device": "0",
        "workers": cfg["workers"],
        "rect": cfg["rect"],
        # Ultralytics 8.4.145 maps legacy half=True to quantize=16.
        # Use the current equivalent directly to preserve FP16 without
        # relying on a deprecated argument.
        "quantize": 16 if cfg["FP16"] else None,
        "conf": cfg["conf"],
        "iou": cfg["iou"],
        "max_det": cfg["max_det"],
        "nms": cfg["nms"],
        "augment": cfg["augment"],
        "agnostic_nms": cfg["agnostic_nms"],
        "single_cls": cfg["single_cls"],
        "cache": cfg["cache"],
        "compile": cfg["compile"],
        "save": False,
        "verbose": False,
        "stream": False,
    }


def run_inference(
    repo,
    manifest_path,
    prepared_path,
    dataset_root,
    outer_archive,
    detection_archive,
    ontology_path,
    protocol_path,
    output_path,
):
    """Run exactly the frozen detector/export bridge. No metric computation."""
    from .manifest import (
        canonical,
        file_hash,
        frozen_gate,
        read_json,
        read_json_with_hash,
        validate_bundle,
    )
    from .prediction_export import (
        assemble_bundle,
        normalize_predictions,
    )
    from .schema import CLASSES, require

    repo = Path(repo).resolve()
    output_path = Path(output_path).resolve()
    metadata_path = output_path.with_name(
        "execution_metadata.json"
    )

    require(
        not output_path.exists()
        and not metadata_path.exists(),
        "Inference output already exists",
    )

    manifest, manifest_file_sha = read_json_with_hash(
        manifest_path
    )

    ontology = read_json(ontology_path)
    protocol = read_json(protocol_path)

    # Runtime scientific validation and HEAD/checkpoint gate happen
    # before any DamSegment image pixel is opened.
    frozen_gate(
        manifest,
        repo,
        ontology,
        protocol,
    )

    validate_scoring_contract(
        manifest,
        ontology,
        protocol,
    )

    require(
        file_hash(ontology_path)
        == manifest["ontology_file_sha256"],
        "Ontology file bytes differ",
    )
    require(
        file_hash(protocol_path)
        == manifest["protocol_file_sha256"],
        "Protocol file bytes differ",
    )

    require(
        file_hash(outer_archive)
        == manifest["dataset"]["outer_archive_sha256"],
        "DamSegment outer archive hash differs",
    )
    require(
        file_hash(detection_archive)
        == manifest["dataset"]["detection_archive_sha256"],
        "DamSegment detection archive hash differs",
    )

    prepared, prepared_file_sha = read_json_with_hash(
        prepared_path
    )

    images, regions = validate_prepared_payload(
        manifest,
        prepared,
        prepared_file_sha,
    )

    image_paths = resolve_image_paths(
        dataset_root,
        images,
    )

    # All scientific gates have passed. Only now may model/image execution begin.
    import cv2
    import numpy as np
    import torch
    import ultralytics
    from ultralytics import YOLO

    require(
        ultralytics.__version__ == "8.4.145",
        "Ultralytics runtime differs",
    )
    require(
        torch.__version__ == "2.14.0+cu130",
        "PyTorch runtime differs",
    )
    require(
        torch.cuda.is_available(),
        "CUDA is unavailable",
    )

    seed = manifest["seed"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False

    model = YOLO(manifest["checkpoint_path"])

    require(
        model.names == CLASSES,
        "Loaded detector class mapping differs",
    )

    head = None
    if hasattr(model, "model") and hasattr(
        model.model,
        "model",
    ):
        modules = model.model.model
        if len(modules):
            head = modules[-1]

    require(
        head is not None
        and getattr(head, "end2end", False) is True,
        "Frozen YOLO26 end-to-end head required",
    )

    plan = execution_plan(manifest)
    kwargs = prediction_kwargs(manifest)

    started = time.perf_counter()

    entries = []

    # Own batching and decoding explicitly so the frozen scientific
    # semantics do not depend on Ultralytics source-loader defaults:
    #
    # workers=0   -> serial cv2 decode in this process
    # shuffle=F   -> iterate frozen prepared inventory order
    # drop_last=F -> explicit final partial batch is retained
    # cache=F     -> only the current batch is held
    # pad=0.5     -> every raw image is verified 640x640, so no
    #                letterbox pixels are required at imgsz=640
    for start, stop in inference_batch_ranges(
        len(images),
        plan["batch_size"],
    ):
        batch_ids = images[start:stop]
        batch_paths = image_paths[start:stop]
        batch_images = []

        for identity, image_path in zip(
            batch_ids,
            batch_paths,
        ):
            image = cv2.imread(
                str(image_path),
                cv2.IMREAD_COLOR,
            )

            require(
                image is not None,
                "Failed to decode DamSegment image: "
                + identity,
            )
            require(
                image.ndim == 3
                and image.shape[0]
                == plan["required_height"]
                and image.shape[1]
                == plan["required_width"]
                and image.shape[2] == 3,
                "DamSegment image shape differs: "
                + identity,
            )

            batch_images.append(image)

        require(
            len(batch_images) == stop - start,
            "DamSegment batch decode count differs",
        )

        batch_results = model.predict(
            source=batch_images,
            **kwargs,
        )

        require(
            len(batch_results) == len(batch_ids),
            "Detector batch result count differs",
        )

        for identity, result in zip(
            batch_ids,
            batch_results,
        ):
            require(
                tuple(result.orig_shape)
                == (
                    plan["required_height"],
                    plan["required_width"],
                ),
                "Detector original image shape differs",
            )

            entries.append((identity, result))

    require(
        len(entries) == len(images) == 1500,
        "Detector result count differs",
    )

    fragment = normalize_predictions(
        entries,
        manifest,
    )

    bundle = assemble_bundle(
        fragment,
        regions,
        manifest,
    )

    validate_bundle(bundle, manifest)

    elapsed = time.perf_counter() - started

    payload = canonical(bundle) + b"\n"

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open("xb") as stream:
        stream.write(payload)

    prediction_sha = hashlib.sha256(
        payload
    ).hexdigest()

    metadata = {
        "experiment_id": manifest["experiment_id"],
        "evaluation_git_sha": manifest[
            "evaluation_git_sha"
        ],
        "portable_contract_sha256": manifest[
            "portable_contract_sha256"
        ],
        "runtime_manifest_sha256": manifest_file_sha,
        "checkpoint_sha256": manifest[
            "checkpoint_sha256"
        ],
        "dataset_sha256": manifest["dataset"]["sha256"],
        "prepared_file_sha256": prepared_file_sha,
        "ontology_sha256": manifest["ontology_sha256"],
        "protocol_sha256": manifest["protocol_sha256"],
        "inference_config": manifest[
            "resolved_inference_config"
        ],
        "predict_kwargs": kwargs,
        "execution_plan": plan,
        "evaluated_images": len(images),
        "evaluated_regions": len(regions),
        "prediction_count": len(bundle["predictions"]),
        "prediction_bundle_sha256": prediction_sha,
        "duration_seconds": elapsed,
        "scientific_metrics_calculated": False,
        "heldout_evaluation_count": 0,
    }

    metadata_path.write_bytes(
        canonical(metadata) + b"\n"
    )

    return {
        "prediction_bundle": str(output_path),
        "prediction_bundle_sha256": prediction_sha,
        "execution_metadata": str(metadata_path),
        "prediction_count": len(bundle["predictions"]),
        "evaluated_images": len(images),
        "evaluated_regions": len(regions),
        "duration_seconds": elapsed,
    }
