"""Isolated synthetic software tests; no real ML workloads or outputs."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from evaluation.framework import (FIELDS, presentation_rows, stop_a_status,
                                  validate_evidence, validate_experiment,
                                  validate_failure, validate_metric)
from evaluation.prepare import DIRECTORIES, initialize
from evaluation.plots import plot_spec


class StopATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-stop-a-unit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.protocol = json.loads((ROOT / "configs/evaluation/stop_a_protocol.yaml").read_text())
        self.exp = dict.fromkeys(FIELDS["experiment"])
        self.exp.update(experiment_id="synthetic-unit-only", name="Software fixture", claim_id="unit", workstream="Chat19", owner="unit", status="PLANNED", evidence_type="SW", dataset="software-fixture", dataset_version="unit", split="unit", accepted=False, synthetic=True)

    def bundle(self):
        # False flags exercise the acceptance boundary with fabricated SW data
        # inside a disposable test root only; these are never production records.
        e = self.exp
        e.update(status="ACCEPTED", accepted=True, synthetic=False, git_sha="a" * 40, config_path="config.json", command="unit-test", hardware="unit-machine", environment_ref="environment.json", started_at="2026-01-01T00:00:00Z", completed_at="2026-01-01T00:00:01Z", raw_result_path="raw.json")
        for name in ["config.json", "environment.json", "raw.json", "command.txt"]:
            (self.root / name).write_text("{}")
        v = dict.fromkeys(FIELDS["evidence"])
        for key in set(e) & set(v):
            v[key] = e[key]
        v.update(evidence_id="unit-evidence", description="Isolated software fixture", artifact_path="metrics.json", config_ref="config.json", command_ref="command.txt", generated_at=e["completed_at"], machine="unit-machine", acceptance_status="ACCEPTED", reviewer_note="unit only")
        m = dict.fromkeys(FIELDS["metric"])
        m.update(metric_id="unit-metric", experiment_id=e["experiment_id"], dataset=e["dataset"], split=e["split"], scope="unit", metric="tests passed", value=1, unit="count", status="ACCEPTED", source_artifact="metrics.json", evidence_type="SW")
        self.write_source(v, {"metrics": [m]})
        return m, e, v

    def write_source(self, evidence, payload):
        data = json.dumps(payload).encode()
        (self.root / evidence["artifact_path"]).write_bytes(data)
        evidence["artifact_sha256"] = hashlib.sha256(data).hexdigest()

    def test_valid_registry(self):
        self.assertIs(validate_experiment(self.exp, self.protocol), self.exp)

    def test_invalid_evidence_type(self):
        self.exp["evidence_type"] = "SW+ML"
        with self.assertRaises(ValueError):
            validate_experiment(self.exp, self.protocol)

    def test_missing_metric_stays_null_not_zero(self):
        m, e, v = self.bundle()
        m.update(value=None, status="PENDING")
        validate_metric(m, e, v, self.protocol, self.root)
        self.assertIsNone(json.loads(json.dumps(m))["value"])
        self.assertNotEqual(m["value"], 0)

    def test_external_blocked_all_progress_states(self):
        for status in ["READY", "RUNNING", "COMPLETE", "ACCEPTED"]:
            with self.subTest(status=status):
                self.exp.update(workstream="Chat03", status=status, accepted=status == "ACCEPTED")
                with self.assertRaisesRegex(ValueError, "BLOCKED"):
                    validate_experiment(self.exp, self.protocol)

    def test_ml_checkpoint_required(self):
        _, e, _ = self.bundle()
        e.update(evidence_type="ML", workstream="Chat02")
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            validate_experiment(e, self.protocol)

    def test_sw_cannot_populate_predictive_metrics(self):
        m, e, v = self.bundle()
        for name in ["mAP@0.5", "precision", "recall", "F1", "detection count"]:
            m["metric"] = name
            with self.assertRaisesRegex(ValueError, "taxonomy"):
                validate_metric(m, e, v, self.protocol, self.root)

    def test_required_provenance_missing(self):
        _, e, v = self.bundle()
        for key in ["git_sha", "command", "environment_ref", "raw_result_path", "completed_at"]:
            invalid = {**e, key: None}
            with self.assertRaises(ValueError):
                validate_evidence(v, invalid, self.protocol, self.root)

    def test_chat02_pending(self):
        status = stop_a_status(self.protocol)
        self.assertEqual(status["status"], "NOT COMPLETE")
        self.assertEqual(status["detector"], "PENDING")

    def test_chat03_pending(self):
        self.protocol["detector"]["status"] = "FROZEN"
        status = stop_a_status(self.protocol)
        self.assertEqual(status["status"], "NOT COMPLETE")
        self.assertEqual(status["external"], "BLOCKED")

    def test_flags_cannot_finalize(self):
        self.protocol["definition_of_done"] = dict.fromkeys(self.protocol["definition_of_done"], "COMPLETE")
        self.assertEqual(stop_a_status(self.protocol)["status"], "NOT COMPLETE")

    def test_initializer_idempotent_no_execution(self):
        with patch("subprocess.run", side_effect=AssertionError("No execution")), patch("socket.socket", side_effect=AssertionError("No network")):
            initialize(self.root, self.protocol)
            before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
            initialize(self.root, self.protocol)
            after = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        for directory in DIRECTORIES:
            self.assertTrue((self.root / directory).is_dir())
        for path in (self.root / "presentation").glob("*.json"):
            self.assertEqual(json.loads(path.read_text())["rows"], [])

    def test_preserves_existing_evidence(self):
        initialize(self.root, self.protocol)
        path = self.root / "manifests/experiment.json"
        path.write_text("preserve failed experiment")
        initialize(self.root, self.protocol)
        self.assertEqual(path.read_text(), "preserve failed experiment")

    def test_synthetic_never_accepted(self):
        m, e, v = self.bundle()
        e["synthetic"] = True
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            presentation_rows([(m, e, v)], self.protocol, self.root)

    def test_pending_synthetic_not_presented(self):
        m, e, v = self.bundle()
        e.update(accepted=False, status="PLANNED", synthetic=True)
        v.update(acceptance_status="PENDING", synthetic=True)
        m.update(status="PENDING", value=None)
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            presentation_rows([(m, e, v)], self.protocol, self.root)

    def test_incomplete_summary_hides_values(self):
        m, e, v = self.bundle()
        m["status"] = "INCOMPLETE"
        result = presentation_rows([(m, e, v)], self.protocol, self.root)
        self.assertIsNone(result["rows"][0]["value"])
        self.assertEqual(result["rows"][0]["status"], "INCOMPLETE")

    def test_accepted_missing_rejected(self):
        m, e, v = self.bundle()
        m["value"] = None
        with self.assertRaises(ValueError):
            presentation_rows([(m, e, v)], self.protocol, self.root)

    def test_source_integrity_and_source_value(self):
        m, e, v = self.bundle()
        validate_metric(m, e, v, self.protocol, self.root)
        m["value"] = 2
        with self.assertRaisesRegex(ValueError, "absent"):
            validate_metric(m, e, v, self.protocol, self.root)
        (self.root / "metrics.json").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_metric(m, e, v, self.protocol, self.root)

    def test_bad_numeric_values(self):
        m, e, v = self.bundle()
        for value in [True, "N/A", float("nan"), float("inf")]:
            m["value"] = value
            with self.assertRaises(ValueError):
                validate_metric(m, e, v, self.protocol, self.root)

    def test_paths_confined_and_models_rejected(self):
        _, e, v = self.bundle()
        for name in ["../escape.json", "model.pt"]:
            v["artifact_path"] = name
            with self.assertRaises(ValueError):
                validate_evidence(v, e, self.protocol, self.root)

    def test_failure_tags_and_nulls(self):
        case = dict.fromkeys(FIELDS["failure"])
        case.update(case_id="unit", experiment_id="unit", dataset="unit", image_or_frame_id="unit", outcome="FN", failure_type="miss", difficulty_tags=["SMALL_DEFECT"], presentation_candidate=False)
        validate_failure(case)
        case["difficulty_tags"] = ["UNKNOWN"]
        with self.assertRaises(ValueError):
            validate_failure(case)

    def test_runtime_plot_interface(self):
        _, e, v = self.bundle()
        e["evidence_type"] = v["evidence_type"] = "SIM"
        payload = {"kind": "runtime", "synthetic": False, "data": {"series": [{"label": "unit only", "x": [1], "y": [2]}], "unit": "ms"}}
        self.write_source(v, payload)
        spec = plot_spec("runtime", v, e, self.protocol, self.root)
        self.assertEqual(spec["status"], "RENDER_INPUT_ONLY")
        payload["data"]["series"][0]["y"] = []
        self.write_source(v, payload)
        with self.assertRaises(ValueError):
            plot_spec("runtime", v, e, self.protocol, self.root)

    def ml_bundle(self):
        _, e, v = self.bundle()
        e.update(evidence_type="ML", workstream="Chat02", dataset="GYU-DET", dataset_version="v3/baseline-v1", split="test", checkpoint_id="synthetic-unit-only", checkpoint_sha256="b" * 64, seed=7)
        for key in set(e) & set(v):
            v[key] = e[key]
        self.protocol["state"] = "FROZEN"
        self.protocol["detector"].update(status="FROZEN", pretraining_gate="PASS", checkpoint_path="never-opened.pt", checkpoint_id=e["checkpoint_id"], checkpoint_sha256=e["checkpoint_sha256"], git_sha="a" * 40, seed=7, configuration="config.json")
        self.protocol["dataset"]["split_sha256"] = "c" * 64
        return e, v

    def test_ml_provenance_path_and_hash_mismatch(self):
        e, v = self.ml_bundle()
        validate_evidence(v, e, self.protocol, self.root)
        e["checkpoint_sha256"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "Checkpoint mismatch"):
            validate_experiment(e, self.protocol)

    def test_predictive_plot_interfaces(self):
        e, v = self.ml_bundle()
        (self.root / "unit-image.txt").write_text("not a real image; interface path test")
        payloads = {
            "confusion_matrix": {"labels": ["unit"], "matrix": [[1]]},
            "pr_curves": {"series": [{"label": "unit", "x": [0.5], "y": [0.5]}]},
            "training_validation_curves": {"series": [{"label": "unit", "x": [1], "y": [1]}]},
            "example_panel": {"cases": [{"outcome": "FN", "image_path": "unit-image.txt", "evidence_id": "unit"}]},
        }
        for kind, data in payloads.items():
            with self.subTest(kind=kind):
                self.write_source(v, {"kind": kind, "synthetic": False, "data": data})
                self.assertEqual(plot_spec(kind, v, e, self.protocol, self.root)["status"], "RENDER_INPUT_ONLY")
                self.write_source(v, {"kind": kind, "synthetic": True, "data": data})
                with self.assertRaises(ValueError):
                    plot_spec(kind, v, e, self.protocol, self.root)

    def test_domain_comparison_requires_authorization_and_evidence(self):
        e, v = self.ml_bundle()
        for record in [e, v]:
            record.update(workstream="Chat03", dataset="unit-external", dataset_version="unit", split="unit-subset")
        e["class_mapping_version"] = "unit-mapping"
        self.protocol["external"].update(external_evaluation_authorized=True, authorization_ref="unit-review", benchmark="unit-external", dataset_version="unit", subset="unit-subset", class_mapping_version="unit-mapping", checkpoint_sha256=e["checkpoint_sha256"], not_used_for_tuning_ref="unit-attestation")
        data = {"series": [{"label": domain, "domain": domain, "x": [1], "y": [1]} for domain in ["in_domain", "external"]]}
        self.write_source(v, {"kind": "domain_comparison", "synthetic": False, "data": data})
        self.assertEqual(plot_spec("domain_comparison", v, e, self.protocol, self.root)["status"], "RENDER_INPUT_ONLY")
        self.protocol["external"]["external_evaluation_authorized"] = False
        with self.assertRaisesRegex(ValueError, "BLOCKED"):
            plot_spec("domain_comparison", v, e, self.protocol, self.root)
        self.protocol["external"]["external_evaluation_authorized"] = True
        v["acceptance_status"] = "PENDING"
        with self.assertRaises(ValueError):
            plot_spec("domain_comparison", v, e, self.protocol, self.root)


if __name__ == "__main__":
    unittest.main()
