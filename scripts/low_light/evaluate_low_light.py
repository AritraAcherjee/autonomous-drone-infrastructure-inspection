"""Explicit validation-only evaluation/latency entry points; default is a static plan."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPOSITORY = Path(__file__).resolve().parents[2]
for entry in (REPOSITORY, REPOSITORY / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from src.low_light import evaluation as e
from src.low_light import latency
from src.low_light.manifest import deterministic_json_bytes
from src.low_light.severity import SEVERITY_IDS, load_config
from src.low_light.validation_variants import _config_path


def run_latency(repo, *, config, strategy, severity, source_split, accepted_commit, host):
    e.require_condition(strategy, severity, source_split)
    provenance = e.require_desktop(repo, accepted_commit, host)
    with e.no_raw_access(repo):
        model_identity = e.checkpoint_identity(repo, strategy)
        records, benchmark = e.load_benchmark(repo, config)
        from detection.training.provenance import configure_runtime
        configure_runtime(repo)
        import torch
        from ultralytics import YOLO
        from unittest.mock import patch
        if not torch.cuda.is_available():
            raise ValueError("official latency requires CUDA")
        # Stable 32-image prefix, identical across strategies. All decoding,
        # integrity checks and EXIF orientation are outside the timed boundary.
        read, _ = e.benchmark_reader(repo, records, e.STRATEGIES[0])
        selected = [r for r in records if r["severity"] == severity][:32]
        images = [read(e._output_path(repo, r["output_relative_path"])) for r in selected]
        with patch("ultralytics.utils.downloads.safe_download", side_effect=RuntimeError("downloads prohibited")):
            model = YOLO(e.checked_path(repo, model_identity["checkpoint"]), task="detect")
            if tuple(model.names.values()) != e.CLASSES:
                raise ValueError("unexpected model class identity")
            def detect(image, *, batch, imgsz):
                return model.predict(source=image, batch=batch, imgsz=imgsz, conf=0.25, iou=0.7,
                    max_det=300, nms=False, augment=False, rect=False, quantize=16, device="0",
                    save=False, verbose=False, stream=False)
            report = latency.measure(strategy=strategy, images=images, detector=detect, iterations=100,
                device="cuda:0", host=host, synchronize=lambda: torch.cuda.synchronize(0),
                hardware=dict(host=provenance["environment"]["host"], gpu=torch.cuda.get_device_name(0),
                              gpu_total_memory=torch.cuda.get_device_properties(0).total_memory,
                              cpu=__import__("platform").processor(), cuda=torch.version.cuda,
                              cudnn=torch.backends.cudnn.version()))
        if e.checkpoint_identity(repo, strategy) != model_identity:
            raise ValueError("checkpoint changed during latency execution")
        report.update(model=model_identity, source_split="valid", severity=severity, benchmark=benchmark,
                      git_sha=accepted_commit, environment=provenance["environment"], locked_test_accessed=False,
                      selected_images=[r["output_relative_path"] for r in selected],
                      input_geometry="EXIF-oriented decoded BGR; orientation/decoding excluded from timing",
                      inference_configuration=dict(batch=1, imgsz=640, conf=0.25, iou=0.7, max_det=300,
                                                   nms=False, rect=False, quantize=16, device="0", augment=False))
        relative = f"{e.EVALUATION_ROOT}/latency/{strategy}/{severity}.json"
        digest = e.write_new(repo, relative, report)
        e.write_new(repo, relative.removesuffix(".json") + ".sha256.json", {Path(relative).name: digest})
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "Locked GYU test is prohibited. plan performs no inference. evaluate and latency require "
        "the accepted clean ARMOURY checkout, local checkpoints and full validation benchmark."))
    parser.add_argument("--mode", choices=("plan", "evaluate", "latency"), default="plan")
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--strategy", choices=e.STRATEGIES, required=True)
    parser.add_argument("--severity", choices=SEVERITY_IDS, required=True)
    parser.add_argument("--config", type=Path, required=True, help="frozen benchmark_v1.yaml")
    parser.add_argument("--source-split", choices=("valid",), default="valid")
    parser.add_argument("--accepted-commit", help="exact 40-character accepted Laptop commit; never canonical base as a substitute")
    parser.add_argument("--host", choices=("ARMOURY",), help="explicit Desktop execution acknowledgement")
    args = parser.parse_args(argv)
    try:
        repo = args.repo_root.resolve()
        e.require_condition(args.strategy, args.severity, args.source_split)
        load_config(_config_path(repo, args.config))
        if args.mode == "plan":
            result = dict(mode="static_plan", strategy=args.strategy, severity=args.severity, source_split="valid",
                          confidence_policy=e.confidence_policy(), inference_configuration=e.inference_config(),
                          latency_protocol=latency.latency_contract(), output_root=e.EVALUATION_ROOT,
                          locked_test="prohibited", detector_inference_executed=False, label=e.NON_OFFICIAL)
        else:
            runner = e.run_evaluation if args.mode == "evaluate" else run_latency
            result = runner(repo, config=args.config, strategy=args.strategy, severity=args.severity,
                            source_split=args.source_split, accepted_commit=args.accepted_commit, host=args.host)
        print(deterministic_json_bytes(result).decode("utf-8"))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Task E refused: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
