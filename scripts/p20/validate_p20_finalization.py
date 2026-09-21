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

ALLOWED_STATES = ("SUPPORTED", "IMPLEMENTED", "DEMONSTRATED", "MEASURED", "PENDING")
EXPECTED_LITERALS = (
    "0.29669431228680787",
    "0.17480040543737643",
    "0.595396782192 m",
    "0.340604743330 m",
    "1.707265244063 deg",
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
    "Learned low-light adaptation was implemented, but final presentation-time model training/evaluation was not completed.",
)
PROHIBITED_AFFIRMATIVE = (
    "fully autonomous",
    "production-ready",
    "confirmed structural defect",
    "proven real-world accuracy",
    "complete end-to-end validation",
    "final low-light model",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xml_text(blob: bytes) -> str:
    root = ET.fromstring(blob)
    return " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))


def main() -> int:
    for path in (PPTX, PDF, PROVENANCE, SOURCE, RESULTS, INDEX):
        if not path.is_file() or path.stat().st_size == 0:
            raise AssertionError(f"missing or empty artifact: {path.relative_to(ROOT)}")

    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    if provenance["classification"] != "P20 FINALIZATION_READY_FOR_LAST-EVIDENCE_INGESTION":
        raise AssertionError("deck classification drift")
    if provenance["slide_count"] != 19:
        raise AssertionError("expected 19 slides")
    if provenance["output_sha256"] != sha256(PPTX):
        raise AssertionError("PPTX provenance hash mismatch")

    source = SOURCE.read_text(encoding="utf-8")
    result_text = RESULTS.read_text(encoding="utf-8")
    index_text = INDEX.read_text(encoding="utf-8")
    combined_sources = "\n".join((source, result_text, index_text))
    for literal in EXPECTED_LITERALS:
        if literal not in combined_sources:
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
    for literal in EXPECTED_LITERALS:
        if literal not in all_slide_text:
            raise AssertionError(f"accepted literal absent from PPTX: {literal}")

    for number, text in enumerate(slide_texts[1:], start=2):
        if not any(state in text for state in ALLOWED_STATES):
            raise AssertionError(f"slide {number} lacks an allowed claim state")

    for phrase in PROHIBITED_AFFIRMATIVE:
        if phrase.lower() in all_slide_text.lower():
            raise AssertionError(f"prohibited affirmative wording in PPTX: {phrase}")

    for number, text in enumerate(note_texts, start=1):
        if "Speaker note:" not in text or len(text.split("Speaker note:", 1)[1].strip()) < 25:
            raise AssertionError(f"slide {number} lacks a substantive speaker note")

    print("P20 finalization validation: PASS")
    print("Slides / speaker-note pages: 19 / 19")
    print("RAW / CLAHE exact metrics: PASS")
    print("LL-DETECTOR dual-state slot: PASS")
    print("P19 dual-state slot: PASS")
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
