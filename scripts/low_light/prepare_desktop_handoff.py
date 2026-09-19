"""Deterministic ARMOURY instructions, static preflight, and guarded Desktop stages.

No model construction, training or inference occurs in static/preflight. Smoke is a
separate engineering wrapper around the accepted guarded trainer and Task D
hook. It never changes or loosens the accepted LL-DETECTOR-01 configuration.
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import math
from pathlib import Path
import re
import sys

REPOSITORY = Path(__file__).resolve().parents[2]
for entry in (REPOSITORY, REPOSITORY / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from src.low_light import evaluation as e
from src.low_light import training as ll
from src.low_light.latency import latency_contract
from src.low_light.manifest import BENCHMARK_ROOT, deterministic_json_bytes, sha256_file, strict_json_loads
from src.low_light.severity import load_config as load_benchmark_config, SEVERITY_IDS

HANDOFF_PATH = "docs/low_light/desktop_handoff.json"
BENCHMARK_CONFIG = "configs/low_light/benchmark_v1.yaml"
TRAINING_CONFIG = "configs/low_light/ll_detector_01.yaml"
SMOKE_ROOT = "outputs/training/low_light/LL-DETECTOR-01-SMOKE"
GEOMETRY_GATE = "outputs/validation/defect_detection/exif_alignment/geometry.json"
TEST_GATE = "outputs/validation/defect_detection/training_pipeline/before/ready.json"
GATE_PATHS = (GEOMETRY_GATE, TEST_GATE)
OUTPUT_ROOTS = dict(benchmark=str(BENCHMARK_ROOT), evaluation=e.EVALUATION_ROOT,
                    training=e.TRAINING_ROOT, smoke=SMOKE_ROOT)
RETURN_EVIDENCE = {
    "benchmark": ["validation_manifest.csv", "validation_manifest.json", "benchmark_summary.json",
                  "sanity_luminance_report.json", "SHA-256 hashes"],
    "det_final_raw": ["L0-L4 aggregate metrics", "L0-L4 per-class metrics", "result SHA-256 hashes"],
    "clahe": ["L0-L4 aggregate metrics", "L0-L4 per-class metrics", "result SHA-256 hashes"],
    "ll_smoke": ["smoke config", "finite-loss evidence", "optimizer-update evidence", "validation evidence",
                 "checkpoint-save evidence", "no-OOM evidence", "raw immutability result", "locked-test non-access statement"],
    "ll_detector_01": ["exact config", "training log", "best.pt", "last.pt", "checkpoint hashes", "best epoch",
                       "validation metrics", "environment/provenance"],
    "post_training": ["L0-L4 aggregate metrics", "L0-L4 per-class metrics", "normal-light regression deltas",
                      "low-light retention metrics", "result SHA-256 hashes"],
    "latency": ["per-strategy raw timing samples", "mean", "median", "p95", "end-to-end FPS", "hardware identity",
                "batch=1", "imgsz=640", "50 untimed warmups", "CUDA synchronization", "timing boundary definition"],
}


def smoke_config() -> dict:
    return dict(id="LL-DETECTOR-01-SMOKE", evidence=e.NON_OFFICIAL, parent_config=TRAINING_CONFIG,
                parent_checkpoint_sha256=ll.CHECKPOINT_SHA256, epochs=1, train_images=16, valid_images=8,
                selection="sha256('42:{split}:{source_relative_path}') sorted prefix", seed=42,
                device="0", cuda_required=True, batch=4, imgsz=640, close_mosaic=0,
                output_root=SMOKE_ROOT, low_light_hook="accepted Task D canonical config, train only",
                test_policy="prohibited", raw_policy="read-only; hash selected files before/after, never enumerate test")


def require_accepted_commit(accepted_commit):
    if not isinstance(accepted_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", accepted_commit):
        raise ValueError("an exact accepted Workstream 04 commit is required, not TBD")
    if accepted_commit == e.CANONICAL_BASE:
        raise ValueError("canonical base cannot substitute for the accepted Workstream 04 commit")


def engineering_gate_readiness(repo: Path) -> dict:
    """Reuse accepted receipt gates read-only; readiness never authorizes execution."""
    from detection.training.exif import require_pass
    from detection.training.trainer import require_tests

    blockers = []
    with e.no_raw_access(repo):
        for relative, require_gate in ((GEOMETRY_GATE, require_pass), (TEST_GATE, require_tests)):
            try:
                require_gate(repo)
            except (OSError, ValueError, RuntimeError, ImportError, KeyError, TypeError, AttributeError) as exc:
                blockers.append(f"{relative}: {exc}")
    return dict(target="04 ENGINEERING HANDOFF — READY FOR FINAL COMMIT",
                status="BLOCKED" if blockers else "READY_FOR_FINAL_COMMIT",
                blocker="; ".join(blockers) if blockers else None)


def handoff(accepted_commit="TBD", *, repo: Path = REPOSITORY) -> dict:
    if accepted_commit != "TBD":
        require_accepted_commit(accepted_commit)
    engineering = engineering_gate_readiness(repo)
    common = 'python scripts/low_light/prepare_desktop_handoff.py'
    runtime = ' --accepted-commit $AcceptedCommit --host ARMOURY'
    evaluate = 'python scripts/low_light/evaluate_low_light.py'
    config = f' --config {BENCHMARK_CONFIG} --source-split valid'
    def evaluation_commands(strategy, mode="evaluate"):
        return [f'{evaluate} --mode {mode} --strategy {strategy} --severity {level}{config}{runtime}' for level in SEVERITY_IDS]
    stages = [
        ("checkout accepted 04 commit", [f'$AcceptedCommit = "{accepted_commit}"',
            'if ($AcceptedCommit -notmatch "^[0-9a-f]{40}$") { throw "Set accepted Laptop commit; TBD cannot execute" }',
            f'if ($AcceptedCommit -eq "{e.CANONICAL_BASE}") {{ throw "Canonical base is not the accepted Workstream 04 commit" }}',
            f'git fetch origin {e.BRANCH}', f'git switch {e.BRANCH}', 'git merge --ff-only $AcceptedCommit',
            'if ((git rev-parse HEAD) -ne $AcceptedCommit) { throw "Exact accepted commit required" }',
            f'git merge-base --is-ancestor {e.CANONICAL_BASE} $AcceptedCommit']),
        ("verify environment", ['python --version', 'python -m pip check',
            f'{common} --mode preflight --accepted-commit $AcceptedCommit',
            f'{common} --mode desktop-check{runtime}']),
        ("verify DET-FINAL checkpoint/hash", [f'{common} --mode preflight --accepted-commit $AcceptedCommit']),
        ("verify dataset identity", [f'{common} --mode preflight --accepted-commit $AcceptedCommit']),
        ("generate full validation benchmark", [f'python scripts/low_light/generate_validation_variants.py --config {BENCHMARK_CONFIG} --source-split valid']),
        ("validate benchmark manifests/sanity", [f'{common} --mode validate-benchmark{runtime}']),
        ("evaluate DET-FINAL raw L0-L4", evaluation_commands(e.STRATEGIES[0])),
        ("evaluate CLAHE + DET-FINAL L0-L4", evaluation_commands(e.STRATEGIES[1])),
        ("bounded LL-DETECTOR smoke training", [f'{common} --mode smoke{runtime}']),
        ("if smoke passes, full LL-DETECTOR-01 100-epoch configured run", [f'{common} --mode train-full{runtime}']),
        ("evaluate LL-DETECTOR-01 L0-L4", evaluation_commands(e.STRATEGIES[2]) + [f'{common} --mode compare{runtime}']),
        ("official latency protocol", [command for strategy in e.STRATEGIES for command in evaluation_commands(strategy, "latency")]),
        ("return evidence bundle", [f'{common} --mode bundle{runtime}']),
    ]
    return dict(schema_version="aegis-low-light-desktop-handoff-v1", branch=e.BRANCH, accepted_commit=accepted_commit,
                canonical_base=e.CANONICAL_BASE, det_final=dict(id=ll.PARENT_ID, architecture="YOLO26s",
                checkpoint=ll.CHECKPOINT_PATH, checkpoint_sha256=ll.CHECKPOINT_SHA256),
                configs=[BENCHMARK_CONFIG, TRAINING_CONFIG], output_roots=OUTPUT_ROOTS.copy(),
                source_split="valid", development_splits=["train", "valid"], locked_test="PROHIBITED; no opt-in exists",
                required_versions=e.REQUIRED_VERSIONS, cuda_required=True, smoke=smoke_config(),
                latency=latency_contract(), confidence_policy=e.confidence_policy(),
                stages=[dict(number=i, stage=name, commands=commands) for i, (name, commands) in enumerate(stages, 1)],
                return_evidence=RETURN_EVIDENCE, execution_shell="PowerShell; stop on every nonzero exit code",
                shell_setup=['$ErrorActionPreference = "Stop"', '$PSNativeCommandUseErrorActionPreference = $true',
                             'function python { & ./.venv-detection/Scripts/python.exe @args; if ($LASTEXITCODE -ne 0) { throw "Python failed" } }',
                             'function git { & git.exe @args; if ($LASTEXITCODE -ne 0) { throw "Git failed" } }'],
                environment_setup="Use the reviewed Python 3.11.15 environment with requirements/detection.txt; no detector downloads.",
                preconditions=["Transfer approved local DET-FINAL checkpoint and approved dataset without modifying raw data.",
                               "Use a clean accepted source checkout; do not substitute canonical base for the accepted commit.",
                               "Output namespaces must be empty; failed/previous evidence is never overwritten.",
                               "Stage 5 onward runs only on ARMOURY after successful preflight and desktop-check.",
                               "The full config requests 100 epochs with accepted patience=30; early stopping is retained and actual epochs must be reported.",
                               "AP is the existing sweep, operating metrics are at 0.25; accuracy is prohibited.",
                               "Both refreshed detector safety gates and their supporting evidence must travel with the accepted 04 commit and pass preflight before stage 5.",
                               "Do not run full repository data-validation commands that access locked test to regenerate a gate.",
                               "If an existing training gate is missing/stale, STOP and return the explicit blocker; never bypass it."],
                existing_training_gate_paths=list(GATE_PATHS),
                readiness=("04 ENGINEERING HANDOFF — BLOCKED" if engineering["blocker"] else engineering["target"]),
                engineering_readiness=engineering,
                desktop_execution_authorized=False,
                execution_authorization="DESKTOP EXECUTION AUTHORIZED only after a real 40-character accepted Workstream 04 commit exists, ARMOURY checks out that exact commit cleanly, and preflight plus desktop-check pass. ENGINEERING HANDOFF READY alone does not authorize execution; TBD and canonical base cannot authorize it.",
                gate_resolution="The existing geometry.json and training_pipeline/before/ready.json are the required source-specific/current-implementation detector safety receipts. They were refreshed after the authorized Workstream 04 changes and must travel with the accepted 04 commit. Current local engineering readiness is determined by the existing require_pass and require_tests gates without regenerating receipts. Missing, non-PASS, stale, hash-mismatched or checkout-inconsistent receipts fail closed; neither gate may be bypassed or replaced by a parallel gate path.",
                preflight_contract=["Exact branch and supplied accepted commit; clean source checkout; canonical base is a strict ancestor.",
                    "Both existing gate files and supporting test evidence are tracked in the accepted checkout.",
                    "Geometry PASS, checked/passed 594/594, test_accessed false, raw immutability PASS, current loader/adapter hashes.",
                    "ready.json PASS, exact current implementation/test hashes and unchanged supporting evidence hashes.",
                    "Local DET-FINAL-v1 checkpoint exists and matches the frozen SHA-256; both frozen configs load.",
                    "Source split valid; development splits train/valid only; locked test prohibited; output roots outside raw.",
                    "CUDA requirement declared; required software versions recorded and checked.",
                    "No training, detector inference, benchmark generation or locked-test image access."],
                laptop_execution="static/help/synthetic unit tests only; no stages 5-13", scientific_performance_claim=False)


def geometry_source_identity(repo):
    """Hash the existing geometry gate's loader sources without importing model APIs."""
    spec = importlib.util.find_spec("ultralytics")
    if spec is None or spec.origin is None:
        raise ValueError("installed Ultralytics loader sources are unavailable")
    package = Path(spec.origin).parent
    modules = ("data.base", "data.dataset", "data.utils", "data.augment", "utils.patches")
    identity = {"ultralytics." + name: sha256_file(package / (name.replace(".", "/") + ".py"))
                for name in modules}
    identity["detection.training.dataset"] = sha256_file(e.checked_path(repo, "src/detection/training/dataset.py"))
    return identity


def training_gate_diagnostics(repo):
    """Inspect both accepted gates read-only; never refresh receipts or access raw."""
    from detection.training.trainer import implementation_identity
    reasons = []
    evidence_paths = []
    try:
        receipt = strict_json_loads(e.checked_path(repo, TEST_GATE).read_bytes())
        if receipt.get("status") != "PASS":
            reasons.append("ready.json status must be PASS")
        current = implementation_identity(repo)
        recorded = receipt.get("implementation")
        if not isinstance(recorded, dict) or not recorded:
            raise ValueError("ready.json implementation hashes are missing")
        mismatched = sorted(key for key in current.keys() | recorded.keys() if current.get(key) != recorded.get(key))
        if mismatched:
            reasons.append("ready.json implementation hash mismatch (stale binding): " + ", ".join(mismatched))
        evidence = receipt.get("evidence_sha256")
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError("ready.json supporting evidence hashes are missing")
        for relative, digest in evidence.items():
            if not relative.startswith(str(Path(TEST_GATE).parent.as_posix()) + "/") or relative == TEST_GATE:
                raise ValueError("unexpected training gate evidence path")
            if sha256_file(e.checked_path(repo, relative)) != digest:
                reasons.append(f"ready.json supporting evidence hash mismatch: {relative}")
            evidence_paths.append(relative)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        reasons.append(f"{TEST_GATE}: {exc}")
    try:
        receipt = strict_json_loads(e.checked_path(repo, GEOMETRY_GATE).read_bytes())
        if receipt.get("status") != "PASS":
            reasons.append("geometry status must be PASS")
        if any(type(receipt.get(key)) is not int or receipt[key] != 594 for key in ("checked", "passed")):
            reasons.append("geometry checked/passed must be 594/594")
        if receipt.get("test_accessed") is not False:
            reasons.append("geometry test_accessed must be false")
        if receipt.get("raw_immutability", {}).get("status") != "PASS":
            reasons.append("geometry raw immutability must be PASS")
        if receipt.get("source_identity") != geometry_source_identity(repo):
            reasons.append("geometry loader/adapter source hashes differ from the current implementation")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        reasons.append(f"{GEOMETRY_GATE}: {exc}")
    return dict(status="BLOCKED" if reasons else "PASS", blockers=reasons,
                paths=list(GATE_PATHS), evidence_paths=sorted(evidence_paths),
                policy="preserve accepted receipts and enforce both existing detector safety gates")


def preflight(repo: Path, accepted_commit: str) -> dict:
    """Read configs, checkpoint and train/valid metadata only; never GPU/model APIs."""
    require_accepted_commit(accepted_commit)
    with e.no_raw_access(repo):
        identity = e.git_identity(repo)
        if identity != dict(branch=e.BRANCH, sha=accepted_commit, source_status=""):
            raise ValueError("branch/commit/source cleanliness mismatch")
        import subprocess
        subprocess.run(["git", "merge-base", "--is-ancestor", e.CANONICAL_BASE, accepted_commit],
                       cwd=repo, capture_output=True, check=True, timeout=30)
        # Later stages create untracked outputs, but tracked files (including
        # receipts) and all sources must still match the accepted commit.
        roots = OUTPUT_ROOTS
        status = subprocess.run(["git", "-c", "core.quotePath=false", "status", "--porcelain", "--untracked-files=all"],
                                cwd=repo, capture_output=True, text=True, check=True, timeout=30).stdout
        for line in status.splitlines():
            if not (line.startswith("?? ") and any(line[3:].startswith(root + "/") for root in roots.values())):
                raise ValueError("clean accepted checkout required, including gate receipts: " + line)
        gates = training_gate_diagnostics(repo)
        if gates["status"] != "PASS":
            raise ValueError("detector safety gates blocked: " + "; ".join(gates["blockers"]))
        subprocess.run(["git", "ls-files", "--error-unmatch", "--", *GATE_PATHS, *gates["evidence_paths"]],
                       cwd=repo, capture_output=True, check=True, timeout=30)
        load_benchmark_config(e.checked_path(repo, BENCHMARK_CONFIG))
        training = ll.load_config(e.checked_path(repo, TRAINING_CONFIG))
        checkpoint = e.checkpoint_identity(repo, e.STRATEGIES[0])
        # Existing loader checks exact YAML, immutable hashes, train/valid lists,
        # membership and path containment. It stats train/valid files, not pixels.
        from detection.training.config import load_development_data, APPROVED_HASHES
        _, splits = load_development_data(repo)
        if set(splits) != {"train", "valid"} or training["data"]["test_policy"] != "prohibited":
            raise ValueError("train/valid-only contract violated")
        for relative in roots.values():
            e.checked_path(repo, relative)
        from detection.data.raw_guard import mutable_path
        try:
            mutable_path(repo / "data/raw/__task_e_readonly_probe__", repo / "data/raw")
        except (ValueError, PermissionError):
            raw_guard_verified = True
        else:
            raise ValueError("raw write protection does not reject a proposed raw output")
        env = e.environment_identity()
        if env["versions"] != e.REQUIRED_VERSIONS:
            raise ValueError(f"required Python/OpenCV/Ultralytics environment differs: {env['versions']}")
    return dict(status="STATIC_PREFLIGHT_PASS", git=identity, detector_safety_gates=gates,
                accepted_commit=accepted_commit, desktop_execution_authorized=False,
                configs=[BENCHMARK_CONFIG, TRAINING_CONFIG],
                checkpoint=checkpoint, dataset_identity="GYU-DET V3 baseline-v1", dataset_hashes=APPROVED_HASHES,
                split_counts={k: len(v) for k, v in splits.items()}, locked_test_accessed=False,
                raw_readonly=dict(policy="enforced by approved development_access/readonly_raw guards during training; no raw opens in preflight/evaluation",
                                  write_path_guard_verified=raw_guard_verified,
                                  filesystem_acl="not changed or inferred; native loader read-only behavior plus content hashes required"),
                output_roots=roots, cuda_required=True, cuda_checked=False, environment=env,
                inference_executed=False, training_executed=False, benchmark_generation_executed=False)


def validate_benchmark(repo):
    with e.no_raw_access(repo):
        records, identity = e.load_benchmark(repo, Path(BENCHMARK_CONFIG))
        from src.low_light.manifest import MANIFEST_NAMES
        summary = strict_json_loads(e.checked_path(repo, f"{BENCHMARK_ROOT}/manifests/{MANIFEST_NAMES[2]}").read_bytes())
        means = [summary["aggregate_luminance_by_severity"][level]["mean_luminance"] for level in SEVERITY_IDS]
        report = dict(status="PASS", benchmark=identity, source_split="valid", locked_test_accessed=False,
                      verified_variants=len(records), aggregate_luminance_by_severity=summary["aggregate_luminance_by_severity"],
                      monotonic_mean_luminance=all(a >= b for a, b in zip(means, means[1:])),
                      note="Monotonicity is reported, not assumed; noise can increase near-black luminance.",
                      scientific_detector_performance=False)
        e.write_new(repo, f"{e.EVALUATION_ROOT}/handoff/sanity_luminance_report.json", report)
        return report


def snapshot_selected(records):
    paths = sorted({r[k] for rows in records.values() for r in rows for k in ("image", "label")})
    return {str(p): dict(sha256=sha256_file(p), size=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns) for p in paths}


def smoke_passed(repo, accepted_commit):
    report = strict_json_loads(e.checked_path(repo, SMOKE_ROOT + "/smoke_evidence.json").read_bytes())
    if (report.get("status") != "PASS" or report.get("git_sha") != accepted_commit
            or report.get("smoke_config") != smoke_config() or report.get("locked_test_accessed") is not False
            or report.get("raw_immutability") != "PASS" or report.get("finite_losses") is not True
            or report.get("no_oom") is not True or report.get("epochs") != 1
            or min(report.get("optimizer_steps", 0), report.get("parameter_updates", 0), report.get("validation_calls", 0)) < 1):
        raise ValueError("passing smoke evidence for this exact commit is required")
    if report.get("parent_checkpoint") != e.checkpoint_identity(repo, e.STRATEGIES[0]):
        raise ValueError("smoke parent identity differs")
    for name in ("best.pt", "last.pt"):
        if sha256_file(e.checked_path(repo, SMOKE_ROOT + "/weights/" + name)) != report["checkpoints"][name]:
            raise ValueError("smoke checkpoint missing/changed")
    return report


def run_full(repo, accepted_commit):
    """Keep every accepted gate; capture selected epoch before optimizer stripping.

Ultralytics replaces best.pt's train_results with the full training history
at finalization. Inferring best epoch from the last history row would be wrong.
"""
    smoke_passed(repo, accepted_commit)
    from unittest.mock import patch
    from detection.training import trainer as existing
    original_factory = existing.trainer_class
    selection = {}
    def factory():
        class SelectionTrainer(original_factory()):
            def save_model(self):
                super().save_model()
                if self.best_fitness == self.fitness:
                    selection.update(best_epoch_zero_based=int(self.epoch), fitness=float(self.fitness))
        return SelectionTrainer
    with patch.object(existing, "trainer_class", factory):
        result = existing.run(repo, repo / TRAINING_CONFIG, acquire=False)
    if result.get("status") != "PASS" or "best_epoch_zero_based" not in selection:
        raise ValueError("full training lacks checkpoint selection proof")
    selection.update(git_sha=accepted_commit, checkpoint_sha256=sha256_file(e.checked_path(repo, e.TRAINING_ROOT + "/weights/best.pt")))
    e.write_new(repo, f"{e.EVALUATION_ROOT}/training_checkpoint_selection.json", selection)
    return result


def run_smoke(repo, accepted_commit):
    """Explicit Desktop-only engineering wrapper; never called by preflight."""
    from unittest.mock import patch
    from detection.training.config import load_development_data, select_records
    from detection.training.provenance import configure_runtime, development_access, write_json
    from detection.training.trainer import trainer_class, training_arguments
    configure_runtime(repo)
    import torch
    from ultralytics.utils import callbacks, LOGGER
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise ValueError("smoke requires CUDA/BF16")
    config = ll.load_config(e.checked_path(repo, TRAINING_CONFIG))
    parent = e.checkpoint_identity(repo, e.STRATEGIES[0])
    out = e.checked_path(repo, SMOKE_ROOT)
    out.mkdir(parents=True, exist_ok=False)
    evidence = dict(status="FAIL", git_sha=accepted_commit, smoke_config=smoke_config(), parent_checkpoint=parent,
                    label=e.NON_OFFICIAL, locked_test_accessed=False, requested_batch=4,
                    optimizer_steps=0, parameter_updates=0, validation_calls=0, epochs=0,
                    finite_losses=True, loss_history=[], no_oom=False, raw_immutability="NOT_CHECKED")
    handler = logging.FileHandler(out / "trainer.log", encoding="utf-8")
    LOGGER.addHandler(handler)
    with development_access(repo):
        _, all_records = load_development_data(repo)
        records = select_records(all_records, dict(training={"seed": 42}, smoke={"train_images": 16, "valid_images": 8}))
        before = snapshot_selected(records)
        try:
            for rows in records.values():
                for row in rows:
                    if before[str(row["image"])]["sha256"] != row["image_sha256"]:
                        raise ValueError("approved smoke source hash differs")
            write_json(out / "smoke_config.json", smoke_config(), repo)
            write_json(out / "parent_config.json", config, repo)
            write_json(out / "selected_records.json", {k: [r["image_relative_path"] for r in v] for k, v in records.items()}, repo)
            for split, rows in records.items():
                (out / f"{split}.txt").write_text("".join(str(r["image"]) + "\n" for r in rows), encoding="utf-8")
            data = dict(path=str(repo), train=str(out / "train.txt"), val=str(out / "valid.txt"),
                        names=dict(enumerate(e.CLASSES)), nc=6, channels=3)
            write_json(out / "development_data.yaml", data, repo)
            args = training_arguments(config, repo, e.checked_path(repo, parent["checkpoint"]), out / "development_data.yaml")
            args.update(epochs=1, name="LL-DETECTOR-01-SMOKE", close_mosaic=0)
            write_json(out / "smoke_runtime_arguments.json", args, repo)
            callback_map = callbacks.get_default_callbacks()
            def loss_check(trainer):
                losses = {k: float(v.detach().cpu()) for k, v in trainer.loss_items.items()}
                if not losses or not all(math.isfinite(v) for v in losses.values()) or not torch.isfinite(trainer.loss).item():
                    evidence["finite_losses"] = False
                    raise FloatingPointError("nonfinite smoke loss")
                evidence["loss_history"].append(losses)
            def validation_check(validator):
                evidence["validation_calls"] += 1
            def epoch_end(trainer):
                evidence["epochs"] += 1
            callback_map["on_train_batch_end"].append(loss_check)
            callback_map["on_val_end"].append(validation_check)
            callback_map["on_train_epoch_end"].append(epoch_end)
            with patch.object(callbacks, "add_integration_callbacks", lambda _: None), patch(
                    "ultralytics.utils.downloads.safe_download", side_effect=RuntimeError("downloads prohibited")):
                # The full-run constructor accepts only the frozen 100-epoch args.
                # This explicitly named engineering wrapper installs the unchanged
                # hook on the same guarded trainer, with recorded bounded args.
                trainer = trainer_class()(records=records, development_data=data, expected_output=out,
                    evidence=evidence, overrides=args, _callbacks=callback_map)
                trainer.low_light_config = config
                trainer.add_callback("on_train_epoch_start", ll.propagate_training_epoch)
                trainer.train()
                torch.cuda.synchronize(0)
            if (evidence["epochs"] != 1 or not evidence["loss_history"] or
                    min(evidence[k] for k in ("optimizer_steps", "parameter_updates", "validation_calls")) < 1):
                raise ValueError("smoke proof incomplete")
            if not trainer.metrics or not all(math.isfinite(float(v)) for v in trainer.metrics.values()):
                raise ValueError("smoke validation metrics missing/nonfinite")
            evidence.update(no_oom=True, validation_metrics=trainer.metrics,
                            checkpoints={n: sha256_file(out / "weights" / n) for n in ("best.pt", "last.pt")},
                            environment=e.environment_identity(), gpu=torch.cuda.get_device_name(0), status="PASS")
        except BaseException as exc:
            evidence.update(status="FAIL", error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            after = snapshot_selected(records)
            evidence["raw_immutability"] = "PASS" if before == after else "FAIL"
            if before != after:
                evidence["status"] = "FAIL"
            write_json(out / "raw_before.json", before, repo)
            write_json(out / "raw_after.json", after, repo)
            write_json(out / "smoke_evidence.json", evidence, repo)
            LOGGER.removeHandler(handler)
            handler.close()
    if evidence["status"] != "PASS":
        raise ValueError("smoke failed raw immutability")
    return evidence


def compare_results(repo):
    results = [strict_json_loads(e.checked_path(repo, f"{e.EVALUATION_ROOT}/validation_development/{s}/{level}/result.json").read_bytes())
               for s in e.STRATEGIES for level in SEVERITY_IDS]
    report = e.comparisons(results)
    e.write_new(repo, f"{e.EVALUATION_ROOT}/comparisons.json", report)
    return report


def verify_result_bundle(repo, accepted_commit):
    """Check content and sidecar hashes before calling an evidence bundle complete."""
    results = []
    for strategy in e.STRATEGIES:
        model = e.checkpoint_identity(repo, strategy)
        for level in SEVERITY_IDS:
            relative = f"{e.EVALUATION_ROOT}/validation_development/{strategy}/{level}/result.json"
            blob = e.checked_path(repo, relative).read_bytes()
            result = strict_json_loads(blob)
            e.validate_result(result)
            if (result["strategy"] != strategy or result["severity"] != level or result["git_sha"] != accepted_commit
                    or result["model"] != model or result["environment"]["host"].casefold() != "armoury"):
                raise ValueError("evaluation evidence identity mismatch")
            sidecar = strict_json_loads(e.checked_path(repo, relative.removesuffix(".json") + ".sha256.json").read_bytes())
            if sidecar != {"result.json": e.sha256_bytes(blob)}:
                raise ValueError("result sidecar hash mismatch")
            results.append(result)
            relative = f"{e.EVALUATION_ROOT}/latency/{strategy}/{level}.json"
            blob = e.checked_path(repo, relative).read_bytes()
            timing = strict_json_loads(blob)
            if (timing.get("strategy") != strategy or timing.get("severity") != level or timing.get("model") != model
                    or timing.get("git_sha") != accepted_commit or timing.get("source_split") != "valid"
                    or timing.get("locked_test_accessed") is not False or timing.get("official") is not True
                    or timing.get("protocol") != latency_contract() or timing.get("benchmark") != result["benchmark"]
                    or timing.get("hardware", {}).get("host", "").casefold() != "armoury"):
                raise ValueError("official latency evidence identity/contract mismatch")
            from src.low_light.latency import summarize
            samples = timing.get("samples", [])
            if len(samples) != 100 or timing.get("timed_iterations") != 100:
                raise ValueError("official latency requires all 100 timed samples")
            for sample in samples:
                if (set(sample) != {"enhancement_ms", "detector_ms", "end_to_end_ms"}
                        or sample["end_to_end_ms"] < sample["enhancement_ms"] + sample["detector_ms"]
                        or (strategy != e.STRATEGIES[1] and sample["enhancement_ms"] != 0.0)):
                    raise ValueError("latency samples violate timing boundaries")
            summary = {k: summarize(s[k] for s in samples) for k in samples[0]}
            if (timing.get("summary") != summary or summary["end_to_end_ms"]["mean"] <= 0
                    or timing.get("end_to_end_fps") != 1000 / summary["end_to_end_ms"]["mean"]):
                raise ValueError("latency summary/FPS mismatch")
            sidecar = strict_json_loads(e.checked_path(repo, relative.removesuffix(".json") + ".sha256.json").read_bytes())
            if sidecar != {Path(relative).name: e.sha256_bytes(blob)}:
                raise ValueError("latency sidecar hash mismatch")
    expected = e.comparisons(results)
    recorded = strict_json_loads(e.checked_path(repo, e.EVALUATION_ROOT + "/comparisons.json").read_bytes())
    if expected != recorded:
        raise ValueError("comparison report differs from returned metrics")


def bundle(repo, accepted_commit):
    """Hash an explicit evidence inventory; no discovery/reading of any test file."""
    smoke_passed(repo, accepted_commit)
    verify_result_bundle(repo, accepted_commit)
    paths = [BENCHMARK_CONFIG, TRAINING_CONFIG, HANDOFF_PATH,
             f"{BENCHMARK_ROOT}/manifests/validation_manifest.csv",
             f"{BENCHMARK_ROOT}/manifests/validation_manifest.json", f"{BENCHMARK_ROOT}/manifests/benchmark_summary.json",
             f"{e.EVALUATION_ROOT}/handoff/sanity_luminance_report.json", f"{e.EVALUATION_ROOT}/comparisons.json",
             f"{e.EVALUATION_ROOT}/training_checkpoint_selection.json"]
    paths += [f"{SMOKE_ROOT}/{n}" for n in ("smoke_config.json", "smoke_runtime_arguments.json", "smoke_evidence.json",
        "selected_records.json", "parent_config.json", "raw_before.json", "raw_after.json", "trainer.log", "weights/best.pt", "weights/last.pt")]
    paths += [f"{e.TRAINING_ROOT}/{n}" for n in ("requested_config.json", "resolved_config.json", "trainer.log",
        "provenance.json", "dataset_identity.json", "run_evidence.json", "raw_immutability.json", "results.csv", "weights/best.pt", "weights/last.pt")]
    for strategy in e.STRATEGIES:
        for level in SEVERITY_IDS:
            paths += [f"{e.EVALUATION_ROOT}/validation_development/{strategy}/{level}/{n}" for n in ("result.json", "result.sha256.json")]
            paths += [f"{e.EVALUATION_ROOT}/latency/{strategy}/{level}{suffix}" for suffix in (".json", ".sha256.json")]
    hashes = {rel: sha256_file(e.checked_path(repo, rel)) for rel in sorted(paths)}
    full = strict_json_loads(e.checked_path(repo, e.TRAINING_ROOT + "/run_evidence.json").read_bytes())
    if full.get("status") != "PASS" or full.get("test_accessed") is not False or full.get("raw_immutability", {}).get("status") != "PASS":
        raise ValueError("full training evidence failed")
    selection = strict_json_loads(e.checked_path(repo, e.EVALUATION_ROOT + "/training_checkpoint_selection.json").read_bytes())
    best_epoch = selection.get("best_epoch_zero_based")
    if (type(best_epoch) is not int or best_epoch < 0 or selection.get("git_sha") != accepted_commit
            or selection.get("checkpoint_sha256") != hashes[e.TRAINING_ROOT + "/weights/best.pt"]):
        raise ValueError("best checkpoint epoch unavailable; return evidence incomplete")
    report = dict(status="COMPLETE", accepted_commit=accepted_commit, source_split="valid", locked_test_accessed=False,
                  files_sha256=hashes, required_evidence=RETURN_EVIDENCE, best_epoch_zero_based=best_epoch,
                  actual_training_epochs=full.get("epochs"), scientific_locked_test_evidence=False,
                  transfer="Return this index and every listed file preserving relative paths, including both LL weights; no raw data.")
    e.write_new(repo, f"{e.EVALUATION_ROOT}/desktop_return_evidence.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog="Default static mode only prints the handoff; locked GYU test is always prohibited.")
    parser.add_argument("--mode", choices=("static", "preflight", "desktop-check", "validate-benchmark", "smoke", "train-full", "compare", "bundle"), default="static")
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY)
    parser.add_argument("--accepted-commit", default="TBD")
    parser.add_argument("--host", choices=("ARMOURY",))
    parser.add_argument("--write", action="store_true", help=f"static only: exclusively create {HANDOFF_PATH}")
    args = parser.parse_args(argv)
    try:
        repo = args.repo_root.resolve()
        if args.write and args.mode != "static":
            raise ValueError("--write is only for static handoff generation")
        if args.mode == "static":
            result = handoff(args.accepted_commit, repo=repo)
            if args.write:
                path = e.checked_path(repo, HANDOFF_PATH)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(deterministic_json_bytes(result))
        elif args.mode == "preflight":
            result = preflight(repo, args.accepted_commit)
        else:
            require_accepted_commit(args.accepted_commit)
            e.require_desktop(repo, args.accepted_commit, args.host)
            checked = preflight(repo, args.accepted_commit)
            if args.mode == "desktop-check":
                result = checked
                import torch
                if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
                    raise ValueError("CUDA with BF16 required")
                result.update(cuda_checked=True, gpu=torch.cuda.get_device_name(0))
            elif args.mode == "validate-benchmark":
                result = validate_benchmark(repo)
            elif args.mode == "smoke":
                result = run_smoke(repo, args.accepted_commit)
            elif args.mode == "train-full":
                result = run_full(repo, args.accepted_commit)
            elif args.mode == "compare":
                result = compare_results(repo)
            else:
                result = bundle(repo, args.accepted_commit)
        print(deterministic_json_bytes(result).decode("utf-8"))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Task E handoff refused: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
