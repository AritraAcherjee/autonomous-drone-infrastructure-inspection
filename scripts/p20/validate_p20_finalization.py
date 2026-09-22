from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
PPTX = ROOT / "outputs/presentation/AegisInspect_P20_working_draft.pptx"
PDF = ROOT / "docs/presentation/deck/rendered/AegisInspect_P20_working_draft.pdf"
PROVENANCE = PPTX.with_suffix(".provenance.json")
SOURCE = ROOT / "docs/presentation/assembly/slide_content.md"
RESULTS = ROOT / "docs/presentation/results_table.json"
INDEX = ROOT / "docs/presentation/presentation_evidence_index.md"
CHART = ROOT / "outputs/presentation/low_light_evidence/raw_clahe_ll_detector_map50.png"
EXPECTED_CHART_SHA = "71d13ee2e58edf0d49f7ca406decc3c82700e6b66abea08ddec391aad9861576"
MODEL_SHA = "87941c7a57f9f501518dd50fcb06ac16fdab004d35f237c7b656a6d785e144d9"
PACKAGE_SHA = "49ad62f55e3aba973d6d1ab03bfc3564db88d4c1719a540a1e1ecd47d3f44f44"

ALLOWED_STATES = ("SUPPORTED", "IMPLEMENTED", "DEMONSTRATED", "MEASURED", "PENDING")
SOURCE_LITERALS = (
    "0.29669431228680787",
    "0.17480040543737643",
    "0.595 m",
    "0.341 m",
    "1.707 degrees",
    "0.011138029396533966",
    "These metrics evaluate localization trajectory accuracy, not absolute defect-position accuracy.",
    "remained pending at the capstone freeze",
    "0.3886917344",
    "0.3796280361",
    "0.3342489847",
    "0.1263098877",
    "0.0031301687",
    "0.2657391403",
    "0.2656420531",
    "0.2240838264",
    "0.0746161035",
    "0.0033883546",
    "0.3659127801830558",
    "0.35998511822145635",
    "0.3438492823402624",
    "0.29042521214928224",
    "0.12412879850381782",
    MODEL_SHA,
    PACKAGE_SHA,
    "Preliminary learned low-light adaptation substantially improved robustness under severe controlled low-light conditions, while producing a small tradeoff under normal and mild illumination.",
    "PRESENTATION / DEMONSTRATION MODEL",
)
LOW_LIGHT_SLIDE_LITERALS = (
    "0.388692", "0.379628", "0.334249", "0.126310", "0.003130",
    "0.265739", "0.265642", "0.224084", "0.074616", "0.003388",
    "0.365913", "0.359985", "0.343849", "0.290425", "0.124129",
    "PRESENTATION / DEMONSTRATION MODEL",
    "Locked GYU test accessed: FALSE",
)
PROHIBITED_AFFIRMATIVE = (
    "fully autonomous",
    "production-ready",
    "confirmed structural defect",
    "proven real-world accuracy",
    "complete end-to-end validation",
    "final low-light model",
    "P19 3D PASS",
    "0.595 m defect-position error",
    "globally surveyed map coordinates",
    "completed simulator-ground-truth correspondence validation",
    "LL-DETECTOR is always better than RAW",
    "canonical scientific LL-DETECTOR result",
    "production-qualified low-light robustness",
    "locked-test validated LL-DETECTOR",
)

STALE_ARMOURY_WORDING = (
    "LAST ARMOURY EVIDENCE OPEN",
    "LL-DETECTOR INSERTION SLOT",
    "Learned low-light adaptation was implemented, but final presentation-time model training/evaluation was not completed.",
    "only remaining late-evidence",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xml_text(blob: bytes) -> str:
    root = ET.fromstring(blob)
    return " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))


def main() -> int:
    for path in (PPTX, PDF, PROVENANCE, SOURCE, RESULTS, INDEX, CHART):
        if not path.is_file() or path.stat().st_size == 0:
            raise AssertionError(f"missing or empty artifact: {path.relative_to(ROOT)}")

    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    if provenance["classification"] != "P20 READY_FOR_FINAL_FREEZE":
        raise AssertionError("deck classification drift")
    if provenance["slide_count"] != 19:
        raise AssertionError("expected 19 slides")
    if provenance["output_sha256"] != sha256(PPTX):
        raise AssertionError("PPTX provenance hash mismatch")
    if sha256(CHART) != EXPECTED_CHART_SHA:
        raise AssertionError("accepted low-light chart hash mismatch")
    if provenance.get("low_light_chart_sha256") != EXPECTED_CHART_SHA:
        raise AssertionError("low-light chart provenance hash mismatch")
    if provenance.get("ll_detector_model_sha256") != MODEL_SHA:
        raise AssertionError("LL-DETECTOR model identity drift")
    if provenance.get("ll_detector_evidence_zip_sha256") != PACKAGE_SHA:
        raise AssertionError("ARMOURY evidence package identity drift")
    if provenance.get("armoury_evidence_wait") != "CLOSED" or provenance.get("msi_evidence_wait") != "CLOSED":
        raise AssertionError("late-evidence wait is not closed")
    expected_control = {
        "p19_capstone_disposition": "FROZEN_PENDING",
        "p19_development": "CLOSED",
        "p18_core_integration": "ACCEPTED",
        "workstream_04_experiments": "CLOSED",
        "remaining_scientific_evidence_dependencies": 0,
        "final_deck": False,
        "final_freeze": False,
        "main_merge": False,
    }
    for key, value in expected_control.items():
        if provenance.get(key) != value:
            raise AssertionError(f"control-state drift: {key}")

    source = SOURCE.read_text(encoding="utf-8")
    result_text = RESULTS.read_text(encoding="utf-8")
    index_text = INDEX.read_text(encoding="utf-8")
    combined_sources = " ".join("\n".join((source, result_text, index_text)).split())
    for literal in SOURCE_LITERALS:
        if " ".join(literal.split()) not in combined_sources:
            raise AssertionError(f"accepted literal absent from sources: {literal}")

    with ZipFile(PPTX) as archive:
        names = set(archive.namelist())
        slides = [f"ppt/slides/slide{i}.xml" for i in range(1, 20)]
        notes = [f"ppt/notesSlides/notesSlide{i}.xml" for i in range(1, 20)]
        if not all(name in names for name in slides):
            raise AssertionError("PPTX slide structure is incomplete")
        if not all(name in names for name in notes):
            raise AssertionError("speaker notes are not present on all slides")
        slide_texts = [xml_text(archive.read(name)) for name in slides]
        note_texts = [xml_text(archive.read(name)) for name in notes]

    all_slide_text = "\n".join(slide_texts)
    all_note_text = "\n".join(note_texts)
    slide_15 = slide_texts[14]
    note_15 = note_texts[14]
    for literal in LOW_LIGHT_SLIDE_LITERALS:
        if literal not in slide_15:
            raise AssertionError(f"accepted low-light literal absent from slide 15: {literal}")

    if "0.124113" in all_slide_text or "0.124113" in all_note_text:
        raise AssertionError("superseded 0.124113 value remains in slide or note content")
    for phrase in STALE_ARMOURY_WORDING:
        if phrase.lower() in (all_slide_text + "\n" + all_note_text).lower():
            raise AssertionError(f"stale ARMOURY wording remains in deck: {phrase}")

    for literal in (
        "Preliminary learned low-light adaptation substantially improved robustness",
        "inference executed exactly once",
        "inference was not rerun",
        "predictions were not changed",
        "training was not rerun",
    ):
        if literal.lower() not in note_15.lower():
            raise AssertionError(f"slide 15 note lacks required boundary/provenance: {literal}")

    for number, text in enumerate(slide_texts[1:], start=2):
        if not any(state in text for state in ALLOWED_STATES):
            raise AssertionError(f"slide {number} lacks an allowed claim state")

    for phrase in PROHIBITED_AFFIRMATIVE:
        if phrase.lower() in all_slide_text.lower():
            raise AssertionError(f"prohibited affirmative wording in PPTX: {phrase}")

    for number in (8, 12, 14):
        if "0.595 m" in slide_texts[number - 1]:
            raise AssertionError(f"slide {number} misuses localization ATE as a spatial/defect metric")

    if "FROZEN PENDING" not in slide_texts[13] or "P19 development: CLOSED" not in slide_texts[13]:
        raise AssertionError("slide 14 does not preserve the final P19 capstone disposition")

    if "0.011138029396533966" not in slide_texts[11] or "UNREVIEWED" not in slide_texts[11]:
        raise AssertionError("slide 12 does not preserve the accepted P18 record boundary")

    for number, text in enumerate(note_texts, start=1):
        if "Speaker note:" not in text or len(text.split("Speaker note:", 1)[1].strip()) < 25:
            raise AssertionError(f"slide {number} lacks a substantive speaker note")

    print("P20 finalization validation: PASS")
    print("Slides / speaker-note pages: 19 / 19")
    print("RAW / CLAHE / LL-DETECTOR exact metrics: PASS")
    print("LL-DETECTOR chart/package/model identity: PASS")
    print("Workstream 04 claim audit: PASS")
    print("ARMOURY evidence slot: CLOSED")
    print("P19 frozen-pending capstone disposition: PASS")
    print("Allowed claim-state audit: PASS")
    print("Prohibited affirmative wording audit: PASS")
    print(f"PPTX SHA-256: {sha256(PPTX)}")
    print(f"PDF SHA-256:  {sha256(PDF)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, ValueError) as exc:
        print(f"P20 finalization validation: FAIL: {exc}")
        raise SystemExit(1)
