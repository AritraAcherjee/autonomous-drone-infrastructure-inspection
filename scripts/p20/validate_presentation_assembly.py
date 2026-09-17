from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]
ASSEMBLY = ROOT / "docs" / "presentation" / "assembly"

EXPECTED_BASE = "a0d9271813c78c6a773379468045c5be507f9097"

EXPECTED_SCOPE = {
    "docs/presentation/assembly/demo_backup_plan.md",
    "docs/presentation/assembly/localization_engineering_story.md",
    "docs/presentation/assembly/runtime_placeholders.json",
    "docs/presentation/assembly/section_readiness.json",
    "docs/presentation/assembly/slide_content.md",
    "scripts/p20/validate_presentation_assembly.py",
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


def changed_files() -> set[str]:
    values = (
        git("diff", "--name-only").splitlines()
        + git(
            "ls-files",
            "--others",
            "--exclude-standard",
        ).splitlines()
    )
    return {value for value in values if value}


def load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if git("branch", "--show-current") != "P20/presentation-assembly":
        fail("wrong presentation-assembly branch")

    if git("rev-parse", "HEAD") != EXPECTED_BASE:
        fail("assembly base drift")

    if changed_files() != EXPECTED_SCOPE:
        fail("assembly scope differs from expected six files")

    canonical_claims = load_json(
        ROOT / "docs" / "presentation" / "claim_matrix.json"
    )
    canonical_results = load_json(
        ROOT / "docs" / "presentation" / "results_table.json"
    )

    placeholders = load_json(
        ASSEMBLY / "runtime_placeholders.json"
    )
    readiness = load_json(
        ASSEMBLY / "section_readiness.json"
    )

    slides = (
        ASSEMBLY / "slide_content.md"
    ).read_text(encoding="utf-8")

    story = (
        ASSEMBLY / "localization_engineering_story.md"
    ).read_text(encoding="utf-8")

    demo = (
        ASSEMBLY / "demo_backup_plan.md"
    ).read_text(encoding="utf-8")

    supported = sum(
        row["claim_status"] == "SUPPORTED"
        for row in canonical_claims["claims"]
    )

    if supported != 11:
        fail("canonical SUPPORTED claim count drift")

    result_rows = {
        row["metric"]: row
        for section in canonical_results["sections"]
        for row in section["results"]
    }

    expected_numbers = {
        "DET-FINAL-v1 GYU test mAP50": "0.29669431228680787",
        "DET-FINAL-v1 GYU test mAP50-95": "0.17480040543737643",
        "DamSegment shared-class mAP50": "0.053176162102447924",
        "DamSegment shared-class mAP50-95": "0.031339626242648855",
    }

    for metric, literal in expected_numbers.items():
        value = result_rows[metric]["value"]

        if str(value) not in slides or literal not in slides:
            fail(f"slide source missing canonical number: {metric}")

    if "DET-FINAL-v1 held-out GYU-DET detection performance" not in slides:
        fail("detector result label drift")

    if "weak zero-shot external-domain transfer" not in slides:
        fail("DamSegment scientific limitation missing")

    if "OpenVINS Mono + IMU" not in slides:
        fail("OpenVINS primary-backend wording missing")

    if "RTAB-Map RGB-D + IMU" not in slides:
        fail("RTAB-Map fallback wording missing")

    required_story = (
        "Compatibility and build integration succeeded",
        "Live initialization did not succeed",
        "One evidence-derived correction was tested",
        "Additional blind tuning was rejected",
        "pre-designed RTAB-Map RGB-D + IMU fallback",
        "downstream localization interface/contract was kept stable",
    )

    for token in required_story:
        if token not in story:
            fail(f"engineering story missing: {token}")

    pending_paths = [
        placeholders["localization"]["backend_runtime_result"],
        placeholders["localization"]["ate_translation_rmse_m"],
        placeholders["localization"]["rpe_translation_rmse_m_1s"],
        placeholders["localization"]["rpe_rotation_rmse_deg_1s"],
        placeholders["localization"]["timestamp_alignment_coverage"],
        placeholders["defect_localization_3d"]["mean_error_m"],
        placeholders["defect_localization_3d"]["median_error_m"],
        placeholders["defect_localization_3d"]["rmse_m"],
        placeholders["defect_localization_3d"]["p95_error_m"],
        placeholders["defect_localization_3d"]["matched_count"],
        placeholders["system"]["stop_b_runtime_status"],
        placeholders["system"]["p18_integrated_run_status"],
    ]

    if not all(value == "PENDING" for value in pending_paths):
        fail("runtime placeholder was prematurely populated")

    if readiness["final_title"] != "PENDING":
        fail("final title prematurely frozen")

    if readiness["highest_stop_level"] != "PENDING":
        fail("highest Stop level prematurely frozen")

    sections = readiness["core_sections"]

    if len(sections) != 18:
        fail("core presentation section count is not 18")

    if [row["section"] for row in sections] != list(range(1, 19)):
        fail("presentation section numbering drift")

    if len(readiness["insertable_sections"]) != 1:
        fail("localization insertable-section contract drift")

    localization = readiness["insertable_sections"][0]

    if localization["runtime_result"] != "PENDING":
        fail("localization runtime result prematurely populated")

    forbidden_supported_phrases = (
        "OpenVINS successfully provided drone odometry",
        "verified VIO accuracy",
        "full autonomous inspection validated",
        "real defects localized globally",
        "successful cross-domain robustness",
    )

    combined = "\n".join((slides, story, demo))

    for line in combined.splitlines():
        lowered = line.strip().lower()

        for phrase in forbidden_supported_phrases:
            if phrase.lower() not in lowered:
                continue

            negated = (
                "do not" in lowered
                or "does not" in lowered
                or "did not" in lowered
                or "not yet" in lowered
                or "never" in lowered
                or "prohibited" in lowered
            )

            if not negated:
                fail(
                    f"unsupported affirmative wording present: {line.strip()}"
                )

    spatial_numeric = re.compile(
        r"(?im)(ATE RMSE|RPE translation RMSE|"
        r"RPE rotation RMSE|timestamp-alignment coverage|"
        r"mean error|median error|P95)\s*:\s*"
        r"(?!\*{0,2}PENDING)[0-9]"
    )

    if spatial_numeric.search(slides):
        fail("unsupported numeric spatial result found in slide source")

    if "one synthetic structure" not in slides:
        fail("P16 synthetic-demo scope missing")

    if "Do not fabricate" not in demo:
        fail("demo fabrication guard missing")

    if "PENDING_CAPTURE" not in demo:
        fail("backup screenshot/clip state missing")

    print("=== P20 PRESENTATION ASSEMBLY VALIDATION ===")
    print("Canonical evidence linkage              : PASS")
    print("Detector result literals                : PASS")
    print("DamSegment result literals              : PASS")
    print("DamSegment limitation                   : PASS")
    print("OpenVINS engineering story              : PASS")
    print("RTAB-Map fallback wording               : PASS")
    print("RTAB-Map runtime result                 : PENDING")
    print("VIO quantitative fields                 : PENDING")
    print("3D localization quantitative fields     : PENDING")
    print("18 core sections                        : PASS")
    print("Insertable localization section         : PASS")
    print("P16 synthetic-as-real audit             : PASS")
    print("Unsupported-claim audit                 : PASS")
    print("Demo fabrication audit                  : PASS")
    print("Final title frozen                      : NO")
    print("Highest Stop-level frozen               : NO")
    print("Operational source modified             : NO")
    print("Assembly validator                      : PASS")
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
        print(f"P20 ASSEMBLY VALIDATION FAILURE: {exc}", file=sys.stderr)
        raise SystemExit(1)
