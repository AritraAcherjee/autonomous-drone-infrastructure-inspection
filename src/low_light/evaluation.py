"""Validation-only low-light contract and an adapter around the approved validator.

AP uses Ultralytics' confidence sweep. Operating counts are independently
rematched at 0.25 / IoU 0.50, then micro-aggregated. No max-F1 operating point,
test split, wall-clock identity, implicit checkpoint acquisition or raw writes.
Heavy dependencies are imported only by explicit Desktop execution functions.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import copy
import importlib.metadata
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

from . import clahe
from .manifest import (
    BENCHMARK_ROOT, MANIFEST_NAMES, VALID_MANIFEST, benchmark_summary,
    deterministic_json_bytes, manifest_csv_bytes, read_manifest_json,
    require_sha256, require_valid_split, sha256_bytes, sha256_file, strict_json_loads,
)
from .severity import PROTOCOL_ID, SEVERITY_IDS, SEVERITY_NAMES, load_config
from .training import CHECKPOINT_PATH, CHECKPOINT_SHA256, EXPERIMENT_ID, PARENT_ID
from .validation_variants import (
    _canonical_path, _config_path, _output_path, load_validation_sources, verify_generated_files,
)

BRANCH = "04/low-light-detector"
CANONICAL_BASE = "013067277d331246959af1f6176584b5305828f4"
EVALUATION_ROOT = "outputs/experiments/low_light/evaluation"
TRAINING_ROOT = "outputs/training/low_light/LL-DETECTOR-01"
STRATEGIES = ("det-final-raw", "clahe-det-final", "ll-detector-raw")
CLASSES = ("Crack", "Breakage", "Honeycombing", "Hole", "Exposed Reinforcement", "Seepage")
OPERATING_CONFIDENCE = 0.25
AP_CONFIDENCE_FLOOR = 0.001
AGGREGATE_FIELDS = ("mAP50", "mAP50-95", "precision", "recall", "F1", "false_negative_rate")
PER_CLASS_FIELDS = ("class_id", "class_name", "AP50", "AP50-95", "recall", "false_negative_rate", "TP", "FP", "FN")
NON_OFFICIAL = "SMOKE / DEBUG ONLY — NOT OFFICIAL PERFORMANCE EVIDENCE"
REQUIRED_VERSIONS = {
    "python": "3.11.15", "opencv-python": "5.0.0.93", "ultralytics": "8.4.145",
    "torch": "2.14.0+cu130", "torchvision": "0.29.0+cu130", "numpy": "2.4.6", "PyYAML": "6.0.3",
}


def confidence_policy() -> dict:
    return {"operating_confidence": OPERATING_CONFIDENCE, "comparison": ">=",
            "operating_matching_iou": 0.5, "aggregate": "micro counts",
            "AP": {"confidence_floor": AP_CONFIDENCE_FLOOR, "confidence_sweep": True,
                   "iou_thresholds": [round(0.5 + i * 0.05, 2) for i in range(10)],
                   "implementation": "Ultralytics 8.4.145 DetectionValidator/DetMetrics"}}


def inference_config() -> dict:
    return dict(batch=8, imgsz=640, rect=True, pad=0.5, quantize=16, device="0", workers=0,
                cache=False, conf=AP_CONFIDENCE_FLOOR, iou=0.7, max_det=300, nms=False,
                augment=False, compile=False, single_cls=False, agnostic_nms=False,
                geometry="restore L0 EXIF orientation after enhancement, before approved loader resize",
                loader="ReadOnlyDetectionDataset; generated validation records only")


def require_condition(strategy: str, severity: str, source_split="valid", confidence=0.25) -> None:
    require_valid_split(source_split)
    if strategy not in STRATEGIES or severity not in SEVERITY_IDS:
        raise ValueError("unsupported strategy or severity")
    if type(confidence) is not float or confidence != OPERATING_CONFIDENCE:
        raise ValueError("all strategies and severities require confidence exactly 0.25")


def operating_metrics(tp: int, fp: int, fn: int) -> dict:
    if any(type(v) is not int or v < 0 for v in (tp, fp, fn)):
        raise ValueError("TP/FP/FN must be nonnegative integers")
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return dict(precision=precision, recall=recall,
                F1=2 * precision * recall / (precision + recall) if precision + recall else 0.0,
                false_negative_rate=fn / (tp + fn) if tp + fn else None)


def metric_payload(ap_by_class: dict, counts_by_class: dict) -> dict:
    """AP inputs must come from the sweep; no AP is inferred from TP/FP/FN."""
    if set(ap_by_class) != set(range(6)) or set(counts_by_class) != set(range(6)):
        raise ValueError("all six classes must be represented")
    per_class = []
    for c, name in enumerate(CLASSES):
        tp, fp, fn = counts_by_class[c]
        op = operating_metrics(tp, fp, fn)
        ap50, ap95 = ap_by_class[c]
        if tp + fn == 0 and (ap50 is not None or ap95 is not None):
            raise ValueError("AP is undefined for a class without ground truth")
        if tp + fn and (ap50 is None or ap95 is None):
            raise ValueError("ground-truth class requires sweep AP")
        per_class.append(dict(class_id=c, class_name=name, AP50=ap50, **{"AP50-95": ap95},
                              recall=op["recall"], false_negative_rate=op["false_negative_rate"],
                              TP=tp, FP=fp, FN=fn))
    def mean_defined(field):
        values = [r[field] for r in per_class if r[field] is not None]
        return math.fsum(values) / len(values) if values else None
    total = operating_metrics(*(sum(row[i] for row in counts_by_class.values()) for i in range(3)))
    total.update({"mAP50": mean_defined("AP50"), "mAP50-95": mean_defined("AP50-95")})
    payload = dict(aggregate=total, per_class=per_class)
    validate_metrics(payload)
    return payload


def validate_metrics(payload: dict) -> None:
    if set(payload) != {"aggregate", "per_class"} or set(payload["aggregate"]) != set(AGGREGATE_FIELDS):
        raise ValueError("missing/unsupported aggregate metrics (accuracy is prohibited)")
    if len(payload["per_class"]) != 6:
        raise ValueError("all six per-class rows required")
    for c, row in enumerate(payload["per_class"]):
        if set(row) != set(PER_CLASS_FIELDS) or row["class_id"] != c or row["class_name"] != CLASSES[c]:
            raise ValueError("missing/unsupported per-class schema or ordering")
        expected = operating_metrics(row["TP"], row["FP"], row["FN"])
        has_ground_truth = row["TP"] + row["FN"] > 0
        if any((row[key] is not None) != has_ground_truth for key in ("AP50", "AP50-95")):
            raise ValueError("per-class AP must be undefined exactly when ground truth is absent")
        if any(row[k] != expected[k] for k in ("recall", "false_negative_rate")):
            raise ValueError("per-class operating metrics disagree with counts")
    for values in [payload["aggregate"], *payload["per_class"]]:
        for key, value in values.items():
            if key not in ("class_id", "class_name", "TP", "FP", "FN") and value is not None:
                if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError("metric must be a finite probability or undefined (null)")
    aggregate = payload["aggregate"]
    counts = (sum(r[k] for r in payload["per_class"]) for k in ("TP", "FP", "FN"))
    if any(aggregate[k] != v for k, v in operating_metrics(*counts).items()):
        raise ValueError("aggregate metrics disagree with micro counts")
    for aggregate_key, class_key in (("mAP50", "AP50"), ("mAP50-95", "AP50-95")):
        values = [r[class_key] for r in payload["per_class"] if r[class_key] is not None]
        if aggregate[aggregate_key] != (math.fsum(values) / len(values) if values else None):
            raise ValueError("aggregate AP disagrees with per-class sweep AP")


def retention(low: float | None, normal: float | None) -> float | None:
    """Undefined denominators remain null; no fabricated zero or infinity."""
    if low is None or normal is None:
        return None
    if not all(math.isfinite(v) and v >= 0 for v in (low, normal)):
        raise ValueError("retention needs finite nonnegative metrics")
    return low / normal if normal else None


def comparisons(results: list[dict]) -> dict:
    """Require a complete, coherent 3 x 5 validation experiment before comparing."""
    ordered = order_results(results)
    expected = {(s, level) for s in STRATEGIES for level in SEVERITY_IDS}
    if {(r["strategy"], r["severity"]) for r in ordered} != expected or len(ordered) != 15:
        raise ValueError("comparison requires exactly all 15 strategy/severity results")
    for result in ordered:
        validate_result(result)
    for key in ("benchmark", "confidence_policy", "inference_configuration", "git_sha", "environment", "evidence"):
        if any(r[key] != ordered[0][key] for r in ordered):
            raise ValueError(f"mixed experiment identity: {key}")
    by_key = {(r["strategy"], r["severity"]): r for r in ordered}
    base = by_key[(STRATEGIES[0], "L0")]["metrics"]["aggregate"]
    deltas, ratios = [], []
    for strategy in STRATEGIES:
        normal = by_key[(strategy, "L0")]["metrics"]["aggregate"]
        models = [r["model"] for r in ordered if r["strategy"] == strategy]
        if any(m != models[0] for m in models):
            raise ValueError("checkpoint changed across severities")
        deltas.append(dict(strategy=strategy, reference="DET-FINAL-v1 + L0 Normal",
                           deltas={k: None if normal[k] is None or base[k] is None else normal[k] - base[k]
                                   for k in AGGREGATE_FIELDS}))
        for level in SEVERITY_IDS[1:]:
            low = by_key[(strategy, level)]["metrics"]["aggregate"]
            ratios.append(dict(strategy=strategy, severity=level,
                               metric_retention={k: retention(low[k], normal[k]) for k in AGGREGATE_FIELDS
                                                 if k != "false_negative_rate"},
                               false_negative_rate_ratio=retention(low["false_negative_rate"], normal["false_negative_rate"])))
    return dict(source_split="valid", locked_test_accessed=False, normal_light_regression=deltas,
                low_light_retention=ratios, undefined_policy="null for absent/zero normal denominator",
                fnr_ratio_interpretation="error ratio; lower is better, not retained performance",
                result_sha256=[sha256_bytes(deterministic_json_bytes(r)) for r in ordered])


def order_results(results):
    for r in results:
        require_condition(r["strategy"], r["severity"], r["source_split"])
    return sorted(results, key=lambda r: (STRATEGIES.index(r["strategy"]), SEVERITY_IDS.index(r["severity"])))


def checked_path(repo: Path, relative: str) -> Path:
    """Canonical nonredirected paths only; never accept a caller's dataset path."""
    path = _canonical_path(repo.resolve(), relative)
    if path.resolve().is_relative_to((repo / "data/raw").resolve()):
        raise ValueError("Task E path must be outside raw")
    return path


def write_new(repo: Path, relative: str, payload: object) -> str:
    if not relative.startswith(EVALUATION_ROOT + "/"):
        raise ValueError("Task E artifacts must remain under the frozen evaluation root")
    path = checked_path(repo, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = deterministic_json_bytes(payload)
    with checked_path(repo, relative).open("xb") as stream:
        stream.write(data)
    return sha256_bytes(data)


def checkpoint_identity(repo: Path, strategy: str) -> dict:
    require_condition(strategy, "L0")
    relative = TRAINING_ROOT + "/weights/best.pt" if strategy == STRATEGIES[2] else CHECKPOINT_PATH
    path = checked_path(repo, relative)
    if not path.is_file():
        raise FileNotFoundError(f"required local checkpoint absent: {relative}")
    digest = sha256_file(path)
    if strategy != STRATEGIES[2] and digest != CHECKPOINT_SHA256:
        raise ValueError("DET-FINAL-v1 checkpoint SHA-256 mismatch")
    return dict(id=EXPERIMENT_ID if strategy == STRATEGIES[2] else PARENT_ID,
                architecture="YOLO26s", checkpoint=relative, checkpoint_sha256=digest)


def environment_identity() -> dict:
    versions = {"python": platform.python_version()}
    for package in REQUIRED_VERSIONS.keys() - {"python"}:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return dict(versions=versions, system=platform.system(), machine=platform.machine(), host=platform.node())


def git_identity(repo: Path) -> dict:
    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                              check=True, timeout=30).stdout.strip()
    return dict(branch=git("branch", "--show-current"), sha=git("rev-parse", "HEAD"),
                # Generated evidence is expected to be untracked. Source/config changes are not.
                source_status=git("status", "--porcelain", "--", "src", "scripts", "configs", "tests", "requirements", "docs/low_light"))


def require_desktop(repo: Path, accepted_commit: str, host: str) -> dict:
    if host != "ARMOURY" or not re.fullmatch(r"[0-9a-f]{40}", accepted_commit or ""):
        raise ValueError("explicit ARMOURY host and accepted 40-character commit required")
    identity = git_identity(repo)
    if identity != dict(branch=BRANCH, sha=accepted_commit, source_status=""):
        raise ValueError("checkout must be the exact accepted branch/commit with clean task sources")
    env = environment_identity()
    if env["host"].casefold() != "armoury" or env["versions"] != REQUIRED_VERSIONS:
        raise ValueError("ARMOURY machine identity or required software versions differ")
    subprocess.run(["git", "merge-base", "--is-ancestor", CANONICAL_BASE, accepted_commit],
                   cwd=repo, check=True, capture_output=True, timeout=30)
    return dict(git=identity, environment=env)


@contextmanager
def no_raw_access(repo: Path):
    """Evaluation and static preflight need metadata/generated files, never raw bytes."""
    raw = (repo / "data/raw").resolve()
    active = [True]
    def audit(event, args):
        if active[0] and event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            if Path(os.fsdecode(args[0])).resolve().is_relative_to(raw):
                raise PermissionError("Task E static/evaluation mode cannot open raw data")
    sys.addaudithook(audit)
    try:
        yield
    finally:
        active[0] = False


def load_benchmark(repo: Path, config: Path, *, verify_pixels=True) -> tuple[list[dict], dict]:
    """Bind complete generated artifacts to approved valid metadata, never test."""
    load_config(_config_path(repo, config))
    sources, source_hash = load_validation_sources(repo)
    from detection.training.config import APPROVED_HASHES
    if source_hash != APPROVED_HASHES[VALID_MANIFEST.as_posix()]:
        raise ValueError("validation metadata differs from approved dataset identity")
    prefix = f"{BENCHMARK_ROOT}/manifests/"
    blobs = {name: checked_path(repo, prefix + name).read_bytes() for name in MANIFEST_NAMES}
    records = read_manifest_json(blobs[MANIFEST_NAMES[1]])
    if {r["source_relative_path"] for r in records} != {s.source_relative_path for s in sources}:
        raise ValueError("full validation membership required; no development prefix")
    by_source = {s.source_relative_path: s for s in sources}
    for row in records:
        src = by_source[row["source_relative_path"]]
        if (row["source_sha256"] != src.source_sha256 or row["source_label_relative_path"] != src.source_label_relative_path
                or row["output_label_relative_path"] is None):
            raise ValueError("source identity or copied labels missing/mismatched")
    if blobs[MANIFEST_NAMES[0]] != manifest_csv_bytes(records):
        raise ValueError("CSV/JSON manifests disagree")
    expected = benchmark_summary(records, available_source_count=len(sources), development_limit=None,
                                 source_manifest_sha256=source_hash,
                                 manifest_hashes={n: sha256_bytes(blobs[n]) for n in MANIFEST_NAMES[:2]})
    if strict_json_loads(blobs[MANIFEST_NAMES[2]]) != expected:
        raise ValueError("benchmark summary identity/sanity mismatch")
    if verify_pixels:
        verify_generated_files(repo, records)
    return records, dict(protocol_id=PROTOCOL_ID, manifest=prefix + MANIFEST_NAMES[1],
                         manifest_sha256=sha256_bytes(blobs[MANIFEST_NAMES[1]]),
                         summary_sha256=sha256_bytes(blobs[MANIFEST_NAMES[2]]),
                         source_manifest_sha256=source_hash, scope="full_validation")


def make_result(*, strategy, severity, model, benchmark, metrics, git_sha, environment,
                execution_host="Laptop 1", confidence=0.25, source_split="valid") -> dict:
    require_condition(strategy, severity, source_split, confidence)
    result = dict(schema_version="aegis-low-light-evaluation-v1", strategy=strategy, severity=severity,
                  severity_name=SEVERITY_NAMES[severity], model=model, benchmark=benchmark,
                  confidence_policy=confidence_policy(), inference_configuration=inference_config(),
                  metrics=metrics, source_split=source_split, git_sha=git_sha, environment=environment,
                  evidence=dict(kind="validation_development", locked_test_accessed=False,
                                official_scientific_performance=False,
                                label="ARMOURY VALIDATION DEVELOPMENT — NOT LOCKED-TEST EVIDENCE"
                                if execution_host == "ARMOURY" else NON_OFFICIAL))
    validate_result(result)
    return result


def validate_result(result: dict) -> None:
    keys = {"schema_version", "strategy", "severity", "severity_name", "model", "benchmark",
            "confidence_policy", "inference_configuration", "metrics", "source_split", "git_sha", "environment", "evidence"}
    if set(result) != keys or result["schema_version"] != "aegis-low-light-evaluation-v1":
        raise ValueError("result schema forbids extra identity fields including wall-clock timestamps")
    require_condition(result["strategy"], result["severity"], result["source_split"])
    if (result["confidence_policy"] != confidence_policy() or result["inference_configuration"] != inference_config()
            or result["severity_name"] != SEVERITY_NAMES[result["severity"]]):
        raise ValueError("result policy differs")
    model = result["model"]
    ll = result["strategy"] == STRATEGIES[2]
    if (set(model) != {"id", "architecture", "checkpoint", "checkpoint_sha256"}
            or model["id"] != (EXPERIMENT_ID if ll else PARENT_ID) or model["architecture"] != "YOLO26s"
            or model["checkpoint"] != (TRAINING_ROOT + "/weights/best.pt" if ll else CHECKPOINT_PATH)):
        raise ValueError("frozen model identity differs")
    require_sha256(model["checkpoint_sha256"])
    if not ll and model["checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise ValueError("DET-FINAL-v1 SHA differs")
    benchmark = result["benchmark"]
    if (set(benchmark) != {"protocol_id", "manifest", "manifest_sha256", "summary_sha256", "source_manifest_sha256", "scope"}
            or benchmark["protocol_id"] != PROTOCOL_ID or benchmark["scope"] != "full_validation"
            or benchmark["manifest"] != f"{BENCHMARK_ROOT}/manifests/{MANIFEST_NAMES[1]}"):
        raise ValueError("benchmark provenance missing or unsupported")
    for key in ("manifest_sha256", "summary_sha256", "source_manifest_sha256"):
        require_sha256(benchmark[key])
    if not re.fullmatch(r"[0-9a-f]{40}", result["git_sha"]):
        raise ValueError("exact Git SHA required")
    if set(result["environment"]) != {"versions", "system", "machine", "host"}:
        raise ValueError("explicit environment identity required; wall-clock fields prohibited")
    env = result["environment"]
    if set(env["versions"]) != set(REQUIRED_VERSIONS) or any(not isinstance(v, str) or not v for v in env["versions"].values()):
        raise ValueError("required environment versions missing")
    evidence = result["evidence"]
    if (set(evidence) != {"kind", "locked_test_accessed", "official_scientific_performance", "label"}
            or evidence["kind"] != "validation_development" or evidence["locked_test_accessed"] is not False
            or evidence["official_scientific_performance"] is not False
            or evidence["label"] not in (NON_OFFICIAL, "ARMOURY VALIDATION DEVELOPMENT — NOT LOCKED-TEST EVIDENCE")):
        raise ValueError("results must be unambiguously validation development evidence")
    if env["host"].casefold() != "armoury" and evidence["label"] != NON_OFFICIAL:
        raise ValueError("Laptop results require the smoke/debug label")
    validate_metrics(result["metrics"])


def enhance(image, strategy):
    require_condition(strategy, "L0")
    return clahe.apply_clahe(image) if strategy == STRATEGIES[1] else image


def benchmark_reader(repo: Path, records: list[dict], strategy: str):
    """Restore label geometry from generated L0 EXIF, without opening raw images.

Task C preserves L0 bytes, but PNG variants intentionally omit EXIF. The
approved detector uses EXIF-oriented labels. Apply the same L0 orientation to
every severity at the adapter boundary, leaving benchmark bytes/constants intact.
"""
    import cv2
    import numpy as np
    from PIL import Image
    normals = {r["source_relative_path"]: r for r in records if r["severity"] == "L0"}
    orientations = {}
    for source, row in normals.items():
        with Image.open(_output_path(repo, row["output_relative_path"])) as image:
            orientation = image.getexif().get(274, 1)
        if orientation not in (1, 6, 8):
            raise ValueError("unreviewed benchmark EXIF orientation")
        orientations[source] = orientation
    lookup = {str(_output_path(repo, r["output_relative_path"])): r for r in records}
    def read(filename, flags=None):
        row = lookup.get(str(Path(filename)))
        if row is None:
            raise ValueError("reader accepts only manifest-generated images")
        data = _output_path(repo, row["output_relative_path"]).read_bytes()
        if sha256_bytes(data) != row["generated_image_sha256"]:
            raise ValueError("benchmark image changed during execution")
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
        if image is None:
            raise ValueError("generated image failed decoding")
        image = enhance(image, strategy)
        orientation = orientations[row["source_relative_path"]]
        if orientation in (6, 8):
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE if orientation == 6 else cv2.ROTATE_90_COUNTERCLOCKWISE)
        return image
    def shape(filename):
        row = lookup[str(Path(filename))]
        h, w = row["generated_height"], row["generated_width"]
        return (w, h) if orientations[row["source_relative_path"]] in (6, 8) else (h, w)
    return read, shape


def validator_adapter(base):
    """Subclass factory is testable with synthetic tensors and a mock validator."""
    class OperatingValidator(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.operating_counts = {c: [0, 0, 0] for c in range(6)}

        def update_metrics(self, preds, batch):
            for si, pred in enumerate(preds):
                prepared = self._prepare_batch(si, batch)
                mask = pred["conf"] >= OPERATING_CONFIDENCE
                filtered = {k: v[mask] for k, v in pred.items()}
                # Rematch after thresholding: a below-threshold prediction cannot
                # consume an annotation for the operating point.
                correct = self._process_batch(filtered, prepared)["tp"][:, 0]
                classes = filtered["cls"].cpu().numpy()
                truth = prepared["cls"].cpu().numpy()
                for c in range(6):
                    tp = int(correct[classes == c].sum())
                    values = (tp, int((classes == c).sum()) - tp, int((truth == c).sum()) - tp)
                    self.operating_counts[c] = [a + b for a, b in zip(self.operating_counts[c], values)]
            # AP sees the entire confidence-sweep predictions, unchanged.
            return super().update_metrics(preds, batch)
    return OperatingValidator


def run_evaluation(repo: Path, *, config: Path, strategy: str, severity: str, source_split: str,
                   accepted_commit: str, host: str) -> dict:
    require_condition(strategy, severity, source_split)
    provenance = require_desktop(repo, accepted_commit, host)
    with no_raw_access(repo):
        model = checkpoint_identity(repo, strategy)
        records, benchmark = load_benchmark(repo, config)
        from detection.training.provenance import configure_runtime
        configure_runtime(repo)
        import torch
        from unittest.mock import patch
        from ultralytics.models.yolo.detect import DetectionValidator
        from ultralytics.data import build_dataloader
        from ultralytics.utils import callbacks
        from detection.training.dataset import ReadOnlyDetectionDataset
        if not torch.cuda.is_available():
            raise ValueError("Desktop evaluation requires CUDA")
        out = checked_path(repo, f"{EVALUATION_ROOT}/validation_development/{strategy}/{severity}")
        out.mkdir(parents=True, exist_ok=False)
        # Approved metadata supplies annotation/class counts for the existing verifier.
        import csv
        with checked_path(repo, VALID_MANIFEST.as_posix()).open(encoding="utf-8", newline="") as stream:
            metadata = {r["image_relative_path"]: r for r in csv.DictReader(stream)}
        selected = [r for r in records if r["severity"] == severity]
        dataset_records = [dict(metadata[r["source_relative_path"]], split="valid",
                                image=_output_path(repo, r["output_relative_path"]),
                                label=_output_path(repo, r["output_label_relative_path"])) for r in selected]
        data = dict(path=str(repo), val="generated-validation-only", names=dict(enumerate(CLASSES)), nc=6, channels=3)
        args = {k: v for k, v in inference_config().items() if k not in ("pad", "geometry", "loader")}
        args.update(mode="val", data="generated.yaml", split="val", plots=False, save_json=False,
                    save_txt=False, verbose=False, project=str(out.parent), name=severity, exist_ok=True)
        validator = validator_adapter(DetectionValidator)(args=args, save_dir=out, _callbacks=callbacks.get_default_callbacks())
        read, shape = benchmark_reader(repo, records, strategy)
        with patch("detection.training.dataset.imread", read), patch("detection.training.dataset.oriented_shape", shape):
            dataset = ReadOnlyDetectionDataset(records=dataset_records, img_path=data["val"], imgsz=640,
                batch_size=8, augment=False, hyp=copy(validator.args), rect=True, cache=False, single_cls=False,
                stride=32, pad=0.5, prefix="low-light valid: ", task="detect", classes=None, data=data, fraction=1.0)
            validator.dataloader = build_dataloader(dataset, 8, 0, shuffle=False, rank=-1,
                                                     drop_last=False, pin_memory=True, device=torch.device("cuda:0"))
            with patch("ultralytics.engine.validator.check_det_dataset", return_value=data), patch.object(
                    callbacks, "add_integration_callbacks", lambda _: None), patch(
                    "ultralytics.utils.downloads.safe_download", side_effect=RuntimeError("downloads prohibited")):
                validator(model=checked_path(repo, model["checkpoint"]))
        if validator.args.max_det != 300 or tuple(validator.names.values()) != CLASSES:
            raise ValueError("evaluator changed max_det or model class identity")
        ap = {c: (None, None) for c in range(6)}
        for i, c in enumerate(validator.metrics.ap_class_index):
            ap[int(c)] = (float(validator.metrics.box.ap50[i]), float(validator.metrics.box.ap[i]))
        # An empty prediction set can omit AP rows; zero AP is valid only with GT.
        for c, (tp, fp, fn) in validator.operating_counts.items():
            if tp + fn and ap[c] == (None, None):
                ap[c] = (0.0, 0.0)
        if checkpoint_identity(repo, strategy) != model:
            raise ValueError("checkpoint changed during evaluation")
        result = make_result(strategy=strategy, severity=severity, model=model, benchmark=benchmark,
                             metrics=metric_payload(ap, validator.operating_counts), git_sha=accepted_commit,
                             environment=provenance["environment"], execution_host=host)
        rel = f"{EVALUATION_ROOT}/validation_development/{strategy}/{severity}/result.json"
        digest = write_new(repo, rel, result)
        write_new(repo, rel.removesuffix(".json") + ".sha256.json", {"result.json": digest})
        return result
