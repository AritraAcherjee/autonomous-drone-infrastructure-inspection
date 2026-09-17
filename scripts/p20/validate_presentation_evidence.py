from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "presentation"

EXPECTED_BASE = "ffd5f23dd2086fc095728a2d445f51a4cb013e07"

CLAIM_STATUSES = (
    "SUPPORTED",
    "IMPLEMENTED_NOT_REAL_EVIDENCE",
    "PENDING_NOT_YET_VERIFIED",
    "OUT_OF_SCOPE",
)

EVIDENCE_SCOPES = (
    "DATA_FOUNDATION",
    "REAL_HELD_OUT",
    "EXTERNAL_BENCHMARK",
    "SIMULATION_RUNTIME",
    "IMPLEMENTATION_TEST",
    "SYNTHETIC_DEMO",
    "PENDING",
)

EXPECTED_COUNTS = {
    "SUPPORTED": 11,
    "IMPLEMENTED_NOT_REAL_EVIDENCE": 4,
    "PENDING_NOT_YET_VERIFIED": 6,
    "OUT_OF_SCOPE": 1,
}

EXPECTED_SCOPE = {
    "docs/presentation/README.md",
    "docs/presentation/claim_matrix.json",
    "docs/presentation/demo_readiness_checklist.md",
    "docs/presentation/evidence_inventory.json",
    "docs/presentation/limitations_and_qa.md",
    "docs/presentation/presentation_outline.md",
    "docs/presentation/results_table.json",
    "docs/presentation/workstream_status.json",
    "scripts/p20/validate_presentation_evidence.py",
}

REQUIRED_CLAIM_FIELDS = {
    "claim_id",
    "workstream",
    "claim_text",
    "claim_status",
    "evidence_scope",
    "evidence_reference",
    "commit_sha",
    "artifact_hash_or_test_result",
    "presentation_safe",
    "limitations",
    "notes",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def load_json(name: str) -> dict:
    return json.loads(
        (DOCS / name).read_text(encoding="utf-8")
    )


def changed_files() -> set[str]:
    tracked = git("diff", "--name-only").splitlines()
    untracked = git(
        "ls-files",
        "--others",
        "--exclude-standard",
    ).splitlines()

    return {
        item
        for item in tracked + untracked
        if item
    }


def require_commit(sha: str) -> None:
    subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    claim_matrix = load_json("claim_matrix.json")
    workstreams = load_json("workstream_status.json")
    results = load_json("results_table.json")
    inventory = load_json("evidence_inventory.json")

    if claim_matrix["canonical_base"] != EXPECTED_BASE:
        fail("claim matrix canonical base drift")

    if workstreams["canonical_base"] != EXPECTED_BASE:
        fail("workstream canonical base drift")

    if results["canonical_base"] != EXPECTED_BASE:
        fail("results canonical base drift")

    if inventory["canonical_base"] != EXPECTED_BASE:
        fail("inventory canonical base drift")

    if tuple(claim_matrix["claim_status_taxonomy"]) != CLAIM_STATUSES:
        fail("claim-status taxonomy drift")

    if tuple(claim_matrix["evidence_scope_taxonomy"]) != EVIDENCE_SCOPES:
        fail("evidence-scope taxonomy drift")

    claims = claim_matrix["claims"]

    ids = [claim["claim_id"] for claim in claims]

    if len(ids) != len(set(ids)):
        fail("duplicate claim IDs")

    counts = {
        status: sum(
            claim["claim_status"] == status
            for claim in claims
        )
        for status in CLAIM_STATUSES
    }

    if counts != EXPECTED_COUNTS:
        fail(f"claim-count drift: {counts}")

    supported_scopes = {
        "DATA_FOUNDATION",
        "REAL_HELD_OUT",
        "EXTERNAL_BENCHMARK",
        "SIMULATION_RUNTIME",
    }

    implemented_scopes = {
        "IMPLEMENTATION_TEST",
        "SYNTHETIC_DEMO",
    }

    for claim in claims:
        if set(claim) != REQUIRED_CLAIM_FIELDS:
            fail(
                f"claim fields drift: {claim['claim_id']}"
            )

        status = claim["claim_status"]
        scope = claim["evidence_scope"]

        if status not in CLAIM_STATUSES:
            fail(
                f"invalid status: {claim['claim_id']}"
            )

        if scope not in EVIDENCE_SCOPES:
            fail(
                f"invalid evidence scope: {claim['claim_id']}"
            )

        if status == "SUPPORTED":
            if scope not in supported_scopes:
                fail(
                    f"SUPPORTED claim uses unsafe scope: "
                    f"{claim['claim_id']}"
                )

            if not claim["evidence_reference"]:
                fail(
                    f"SUPPORTED claim lacks evidence: "
                    f"{claim['claim_id']}"
                )

            if claim["presentation_safe"] is not True:
                fail(
                    f"SUPPORTED claim not presentation-safe: "
                    f"{claim['claim_id']}"
                )

        elif status == "IMPLEMENTED_NOT_REAL_EVIDENCE":
            if scope not in implemented_scopes:
                fail(
                    f"implemented claim uses unsafe scope: "
                    f"{claim['claim_id']}"
                )

            if claim["presentation_safe"] is not True:
                fail(
                    f"implemented claim not presentation-safe: "
                    f"{claim['claim_id']}"
                )

        elif status == "PENDING_NOT_YET_VERIFIED":
            if scope != "PENDING":
                fail(
                    f"pending claim scope drift: "
                    f"{claim['claim_id']}"
                )

            if claim["artifact_hash_or_test_result"] != "PENDING":
                fail(
                    f"pending claim has fabricated result: "
                    f"{claim['claim_id']}"
                )

            if claim["evidence_reference"] != "":
                fail(
                    f"pending claim unexpectedly binds result evidence: "
                    f"{claim['claim_id']}"
                )

            if claim["commit_sha"] != "":
                fail(
                    f"pending claim unexpectedly binds result commit: "
                    f"{claim['claim_id']}"
                )

            if claim["presentation_safe"] is not False:
                fail(
                    f"pending claim incorrectly marked presentation-safe: "
                    f"{claim['claim_id']}"
                )

        elif status == "OUT_OF_SCOPE":
            if claim["presentation_safe"] is not False:
                fail(
                    f"out-of-scope claim marked presentation-safe: "
                    f"{claim['claim_id']}"
                )

    inventory_rows = inventory["evidence"]

    if len(inventory_rows) != 16:
        fail(
            f"evidence inventory count drift: "
            f"{len(inventory_rows)}"
        )

    inventory_ids = [
        row["evidence_id"]
        for row in inventory_rows
    ]

    if len(inventory_ids) != len(set(inventory_ids)):
        fail("duplicate evidence IDs")

    inventory_refs = {
        row["reference"]
        for row in inventory_rows
    }

    for row in inventory_rows:
        if row["scope"] not in EVIDENCE_SCOPES:
            fail(
                f"inventory scope invalid: {row['evidence_id']}"
            )

        reference = ROOT / row["reference"]

        if not reference.exists():
            fail(
                f"evidence reference missing: "
                f"{row['evidence_id']} -> {row['reference']}"
            )

        if row["commit_sha"]:
            require_commit(row["commit_sha"])

    for claim in claims:
        if claim["claim_status"] == "PENDING_NOT_YET_VERIFIED":
            continue

        if claim["evidence_reference"]:
            if claim["evidence_reference"] not in inventory_refs:
                fail(
                    f"claim evidence absent from inventory: "
                    f"{claim['claim_id']}"
                )

            if not (ROOT / claim["evidence_reference"]).exists():
                fail(
                    f"claim evidence path missing: "
                    f"{claim['claim_id']}"
                )

        if claim["commit_sha"]:
            require_commit(claim["commit_sha"])

    expected_sections = [
        "DATASET",
        "IN_DOMAIN_DETECTION",
        "EXTERNAL_GENERALIZATION",
        "LOCALIZATION",
        "3D DEFECT LOCALIZATION",
        "SYSTEM / RUNTIME",
    ]

    actual_sections = [
        section["section"]
        for section in results["sections"]
    ]

    if actual_sections != expected_sections:
        fail(
            f"results section drift: {actual_sections}"
        )

    if results["pending_literal"] != "PENDING":
        fail("pending literal drift")

    result_rows = {
        row["metric"]: row
        for section in results["sections"]
        for row in section["results"]
    }

    expected_values = {
        "supervised_images": 10398,
        "annotations": 48392,
        "classes": 6,
        "DET-FINAL-v1 GYU test mAP50": 0.29669431228680787,
        "DET-FINAL-v1 GYU test mAP50-95": 0.17480040543737643,
        "DamSegment shared-class mAP50": 0.053176162102447924,
        "DamSegment shared-class mAP50-95": 0.031339626242648855,
    }

    for metric, expected in expected_values.items():
        if result_rows[metric]["value"] != expected:
            fail(
                f"result drift: {metric}"
            )

    for row in result_rows.values():
        if row["status"] == "PENDING_NOT_YET_VERIFIED":
            if row["value"] != "PENDING":
                fail(
                    f"unresolved result is not PENDING: "
                    f"{row['metric']}"
                )

            if row["scope"] != "PENDING":
                fail(
                    f"unresolved result has non-PENDING scope: "
                    f"{row['metric']}"
                )

    outline = (
        DOCS / "presentation_outline.md"
    ).read_text(encoding="utf-8")

    qa = (
        DOCS / "limitations_and_qa.md"
    ).read_text(encoding="utf-8")

    checklist = (
        DOCS / "demo_readiness_checklist.md"
    ).read_text(encoding="utf-8")

    readme = (
        DOCS / "README.md"
    ).read_text(encoding="utf-8")

    slide_numbers = [
        int(value)
        for value in re.findall(
            r"(?m)^## Slide (\d+) - ",
            outline,
        )
    ]

    if slide_numbers != list(range(1, 19)):
        fail(
            f"slide sequence drift: {slide_numbers}"
        )

    if "PENDING 00 CONTROL CENTER DECISION" not in outline:
        fail("final title placeholder missing")

    if "Final-title rule" not in readme:
        fail("README final-title guard missing")

    required_limitations = (
        "Detector metrics are not generic accuracy",
        "External generalization is weak",
        "DamSegment is a shared-class benchmark",
        "Depth evidence is simulated",
        "Camera XYZ stops in camera_optical_frame",
        "P16 demonstration data is synthetic",
        "Implemented modules do not prove a full mission",
        "Real VIO metrics remain pending",
        "Real 3D defect localization remains pending",
        "End-to-end autonomy remains pending",
    )

    for item in required_limitations:
        if item not in qa:
            fail(
                f"required limitation missing: {item}"
            )

    pending_tokens = (
        "ATE: **PENDING**",
        "RPE translation: **PENDING**",
        "RPE rotation: **PENDING**",
        "timestamp-alignment coverage: **PENDING**",
    )

    for token in pending_tokens:
        if token not in outline:
            fail(
                f"outline pending token missing: {token}"
            )

    checklist_pending = (
        "ATE: `PENDING`",
        "RPE translation: `PENDING`",
        "RPE rotation: `PENDING`",
        "alignment coverage: `PENDING`",
        "mean error: `PENDING`",
        "median error: `PENDING`",
        "RMSE: `PENDING`",
        "P95: `PENDING`",
    )

    for token in checklist_pending:
        if token not in checklist:
            fail(
                f"checklist pending token missing: {token}"
            )

    spatial_numeric_pattern = re.compile(
        r"(?im)^\s*[-*]?\s*"
        r"(ATE|RPE(?: translation| rotation)?|"
        r"alignment coverage|mean error|median error|RMSE|P95)"
        r"\s*:\s*(?:\*\*)?[0-9]"
    )

    for name, text in (
        ("presentation_outline.md", outline),
        ("limitations_and_qa.md", qa),
        ("demo_readiness_checklist.md", checklist),
    ):
        match = spatial_numeric_pattern.search(text)

        if match:
            fail(
                f"unsupported real spatial number in {name}: "
                f"{match.group(0)}"
            )

    supported_text = " ".join(
        claim["claim_text"]
        for claim in claims
        if claim["claim_status"] == "SUPPORTED"
    ).lower()

    for forbidden in (
        "verified vio accuracy",
        "successful autonomous localization",
        "full autonomous inspection validated",
        "autonomous mission successfully completed",
        "real defects localized globally",
    ):
        if forbidden in supported_text:
            fail(
                f"unsupported claim promoted to SUPPORTED: "
                f"{forbidden}"
            )

    p16 = next(
        claim
        for claim in claims
        if claim["claim_id"] == "P20-C013"
    )

    if p16["evidence_scope"] != "SYNTHETIC_DEMO":
        fail("P16 synthetic scope drift")

    if "synthetic" not in p16["claim_text"].lower():
        fail("P16 claim no longer identifies synthetic records")

    if "synthetic/test-only" not in readme:
        fail("README synthetic-data boundary missing")

    if (
        "demonstrated using synthetic mapped-defect records"
        not in outline
    ):
        fail("outline synthetic-dashboard wording drift")

    if (
        "current P16 demo records are synthetic/test-only"
        not in qa
    ):
        fail("Q&A synthetic-dashboard boundary drift")

    if changed_files() != EXPECTED_SCOPE:
        fail(
            "P20 implementation scope is not the expected nine files"
        )

    print("=== P20 PRESENTATION EVIDENCE VALIDATION ===")
    print(f"SUPPORTED claims                      : {counts['SUPPORTED']}")
    print(
        "IMPLEMENTED_NOT_REAL_EVIDENCE claims : "
        f"{counts['IMPLEMENTED_NOT_REAL_EVIDENCE']}"
    )
    print(
        "PENDING_NOT_YET_VERIFIED claims      : "
        f"{counts['PENDING_NOT_YET_VERIFIED']}"
    )
    print(f"OUT_OF_SCOPE claims                   : {counts['OUT_OF_SCOPE']}")
    print(f"Evidence inventory entries            : {len(inventory_rows)}")
    print("Claim-status taxonomy                 : PASS")
    print("Evidence-scope taxonomy               : PASS")
    print("Claim/evidence inventory linkage      : PASS")
    print("Canonical detector numbers            : PASS")
    print("Canonical DamSegment numbers          : PASS")
    print("PENDING result literal                : PASS")
    print("18-slide working sequence             : PASS")
    print("Required limitations                  : PASS")
    print("Unsupported-claim audit               : PASS")
    print("Synthetic-as-real audit               : PASS")
    print("Real VIO metrics invented             : NO")
    print("Real 3D localization metrics invented : NO")
    print("Final Stop-level/title frozen          : NO")
    print("Operational source modified           : NO")
    print("P20 evidence validator                : PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        AssertionError,
        KeyError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"P20 VALIDATION FAILURE: {exc}", file=sys.stderr)
        raise SystemExit(1)
