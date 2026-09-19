"""Synthetic boundary regressions, separate from real handoff evidence."""
from dataclasses import replace
from datetime import datetime, timezone
import sqlite3
import pytest
from dashboard.components import defect_table_rows, evidence_table_rows
from src.storage.models import ReviewStatus
from src.storage.repository import DuplicateDefectError, DuplicateEvidenceError
from src.storage.service import InspectionService
from src.storage.validation import ValidationError
from src.integrations.p16_p17_adapter import build_inspection_report
from src.reporting.rendering import render_report
from tests.storage.fixtures import make_structure, make_inspection, make_defect, make_evidence

CONFIDENCE = 0.004553093574941158
STAMP = datetime(1970, 1, 1, 0, 0, 21, 813000, tzinfo=timezone.utc)


def setup_service(tmp_path):
    service = InspectionService.from_database_path(tmp_path/'precision.sqlite3')
    service.initialize()
    structure = service.create_structure(make_structure())
    return service, make_inspection(structure.structure_id)


def test_subsecond_precision_survives_storage_replay_and_p17(tmp_path):
    service, inspection_input = setup_service(tmp_path)
    inspection = service.create_inspection(replace(inspection_input, started_at=STAMP))
    assert service.get_inspection(inspection.inspection_id).started_at == STAMP
    record = make_defect(inspection_id=inspection.inspection_id, confidence=CONFIDENCE,
                         first_seen=STAMP, last_seen=STAMP, observation_count=1)
    created = service.ingest_mapped_defect(record)
    evidence = make_evidence(record.defect_id, timestamp=STAMP, confidence=CONFIDENCE)
    stored_evidence = service.add_evidence(evidence)
    assert created.first_seen == created.last_seen == stored_evidence.timestamp == STAMP
    with pytest.raises(DuplicateDefectError): service.ingest_mapped_defect(record)
    with pytest.raises(DuplicateEvidenceError): service.add_evidence(evidence)
    assert service.get_defect(record.defect_id) == created
    assert len(service.list_evidence(record.defect_id)) == 1
    assert created.review_status == ReviewStatus.UNREVIEWED and created.review_notes is None
    report = render_report(build_inspection_report(service, inspection.inspection_id))
    assert '1970-01-01T00:00:21.813000Z' in report
    assert repr(CONFIDENCE) in report
    assert report == render_report(build_inspection_report(service, inspection.inspection_id))


def test_upstream_inspection_identity_is_optional_and_no_existing_row_overwritten(tmp_path):
    service, record = setup_service(tmp_path)
    assert service.create_inspection(record).inspection_id == 1
    preserved = service.create_inspection(record, inspection_id=2026091901)
    assert preserved.inspection_id == 2026091901
    assert service.get_inspection(2026091901) == preserved
    with pytest.raises(sqlite3.IntegrityError):
        service.create_inspection(record, inspection_id=2026091901)
    assert service.get_inspection(2026091901) == preserved
    assert len(service.list_inspections()) == 2


@pytest.mark.parametrize('value', [True, 0, -1, '2', 1.0, 2**63])
def test_invalid_explicit_inspection_ids_fail_closed(tmp_path, value):
    service, record = setup_service(tmp_path)
    with pytest.raises(ValidationError): service.create_inspection(record, inspection_id=value)
    assert service.list_inspections() == []


def test_dashboard_retains_low_confidence_and_unreviewed_state(tmp_path):
    service, inspection_input = setup_service(tmp_path)
    inspection = service.create_inspection(inspection_input)
    record = make_defect(inspection_id=inspection.inspection_id, confidence=CONFIDENCE)
    defect = service.ingest_mapped_defect(record)
    evidence = service.add_evidence(make_evidence(record.defect_id, confidence=CONFIDENCE))
    rows = defect_table_rows([defect])
    assert rows[0]['Confidence'] == repr(CONFIDENCE)
    assert rows[0]['Review'] == 'UNREVIEWED'
    assert evidence_table_rows([evidence])[0]['Confidence'] == repr(CONFIDENCE)
    assert not {'Severity','Dimensions','Safety','Repair Recommendation'} & set(rows[0])
