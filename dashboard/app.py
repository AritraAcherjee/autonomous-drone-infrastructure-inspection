"""AegisInspect P16 inspection database and human-review dashboard."""

from __future__ import annotations

import os
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


import streamlit as st  # noqa: E402

from dashboard.components import (  # noqa: E402
    defect_table_rows,
    evidence_table_rows,
)
from src.storage.models import ReviewStatus  # noqa: E402
from src.storage.service import InspectionService  # noqa: E402


DEFAULT_DATABASE_PATH = (
    REPOSITORY_ROOT
    / "database"
    / "aegisinspect.sqlite3"
)


def database_path() -> Path:
    """Resolve the P16 database path using the frozen precedence."""

    configured = os.environ.get("AEGISINSPECT_DB_PATH")

    if configured:
        return Path(configured).expanduser().resolve()

    return DEFAULT_DATABASE_PATH


def review_counts(defects) -> dict[ReviewStatus, int]:
    return {
        status: sum(
            defect.review_status == status
            for defect in defects
        )
        for status in ReviewStatus
    }


st.set_page_config(
    page_title="AegisInspect Inspection Review",
    page_icon="🔎",
    layout="wide",
)

st.title("AegisInspect Inspection Review")
st.caption(
    "P16 synthetic/test dashboard — human review remains "
    "separate from machine-generated defect output."
)

db_path = database_path()

service = InspectionService.from_database_path(db_path)
service.initialize()

inspections = service.list_inspections()

with st.sidebar:
    st.header("Inspection Filters")

    st.caption("Database")
    st.code(str(db_path), language=None)

    if not inspections:
        st.warning(
            "No inspections are available in the selected database."
        )
        st.stop()

    inspection_labels = {
        inspection.inspection_id: (
            f"Inspection {inspection.inspection_id} — "
            f"{inspection.status.value}"
        )
        for inspection in inspections
    }

    selected_inspection_id = st.selectbox(
        "Inspection",
        options=[
            inspection.inspection_id
            for inspection in inspections
        ],
        format_func=lambda value: inspection_labels[value],
    )

selected_inspection = service.get_inspection(
    selected_inspection_id
)

if selected_inspection is None:
    st.error("Selected inspection could not be loaded.")
    st.stop()

structure = service.get_structure(
    selected_inspection.structure_id
)

all_defects = service.list_inspection_defects(
    selected_inspection_id
)

class_options = sorted(
    {
        defect.class_name
        for defect in all_defects
    }
)

with st.sidebar:
    selected_class = st.selectbox(
        "Defect class",
        options=["All", *class_options],
    )

    selected_review = st.selectbox(
        "Review status",
        options=[
            "All",
            *[status.value for status in ReviewStatus],
        ],
    )

    minimum_confidence = st.slider(
        "Minimum confidence",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.01,
    )

class_filter = (
    None
    if selected_class == "All"
    else selected_class
)

review_filter = (
    None
    if selected_review == "All"
    else ReviewStatus(selected_review)
)

filtered_defects = service.list_defects(
    inspection_id=selected_inspection_id,
    class_name=class_filter,
    review_status=review_filter,
    min_confidence=minimum_confidence,
)

counts = review_counts(all_defects)

st.subheader("Inspection Summary")

summary_col_1, summary_col_2, summary_col_3 = st.columns(3)

with summary_col_1:
    st.write(
        "**Structure:**",
        (
            structure.name
            if structure is not None
            else "Unknown structure"
        ),
    )
    st.write(
        "**Inspection ID:**",
        selected_inspection.inspection_id,
    )

with summary_col_2:
    st.write(
        "**Inspection status:**",
        selected_inspection.status.value,
    )
    st.write(
        "**System version:**",
        selected_inspection.system_version,
    )

with summary_col_3:
    st.write(
        "**Started:**",
        selected_inspection.started_at.isoformat(),
    )
    st.write(
        "**Completed:**",
        (
            selected_inspection.completed_at.isoformat()
            if selected_inspection.completed_at is not None
            else "N/A"
        ),
    )

metric_1, metric_2, metric_3, metric_4 = st.columns(4)

metric_1.metric(
    "Total defects",
    len(all_defects),
)
metric_2.metric(
    "Filtered defects",
    len(filtered_defects),
)
metric_3.metric(
    "Confirmed",
    counts[ReviewStatus.CONFIRMED],
)
metric_4.metric(
    "Needs Investigation",
    counts[ReviewStatus.NEEDS_INVESTIGATION],
)

if selected_inspection.notes:
    st.info(selected_inspection.notes)

st.subheader("Defect Table")

if filtered_defects:
    st.dataframe(
        defect_table_rows(filtered_defects),
        hide_index=True,
        width="stretch",
    )
else:
    st.info("No defects match the current filters.")

st.subheader("Defect Detail")

if not filtered_defects:
    st.caption(
        "Adjust the filters to select a defect for detailed review."
    )
    st.stop()

defect_ids = [
    defect.defect_id
    for defect in filtered_defects
]

selected_defect_id = st.selectbox(
    "Select defect",
    options=defect_ids,
)

defect = service.get_defect(selected_defect_id)

if defect is None:
    st.error("Selected defect could not be loaded.")
    st.stop()

st.markdown("### AI suggestion / machine output")
st.caption(
    "These fields are persisted machine output. "
    "They are not a human confirmation."
)

detail_1, detail_2, detail_3 = st.columns(3)

with detail_1:
    st.write("**Defect ID:**", defect.defect_id)
    st.write(
        "**Track ID:**",
        defect.track_id or "N/A",
    )
    st.write("**Class:**", defect.class_name)
    st.write(
        "**Confidence:**",
        f"{defect.confidence:.3f}",
    )

with detail_2:
    st.write(
        "**Map XYZ (m):**",
        (
            f"({defect.x_m:.3f}, "
            f"{defect.y_m:.3f}, "
            f"{defect.z_m:.3f})"
        ),
    )
    st.write(
        "**Coordinate frame:**",
        defect.coordinate_frame,
    )
    st.write(
        "**Observation count:**",
        defect.observation_count,
    )

with detail_3:
    st.write(
        "**Model version:**",
        defect.model_version,
    )
    st.write(
        "**First seen:**",
        defect.first_seen.isoformat(),
    )
    st.write(
        "**Last seen:**",
        defect.last_seen.isoformat(),
    )

st.markdown("### Evidence")

evidence = service.list_evidence(
    defect.defect_id
)

if evidence:
    st.dataframe(
        evidence_table_rows(evidence),
        hide_index=True,
        width="stretch",
    )
else:
    st.info(
        "No evidence rows are currently attached to this defect."
    )

st.markdown("### Human Review")

st.write(
    "**Current review status:**",
    defect.review_status.value,
)

review_options = list(ReviewStatus)

current_review_index = review_options.index(
    defect.review_status
)

with st.form(
    key=f"review-form-{defect.defect_id}"
):
    selected_review_status = st.selectbox(
        "Human review decision",
        options=review_options,
        index=current_review_index,
        format_func=lambda status: status.value,
    )

    review_notes = st.text_area(
        "Review notes",
        value=defect.review_notes or "",
        placeholder=(
            "Optional human-review notes. "
            "Do not add unsupported measurements or severity claims."
        ),
    )

    save_review = st.form_submit_button(
        "Save Review"
    )

if save_review:
    service.set_review_status(
        defect.defect_id,
        selected_review_status,
        review_notes,
    )

    st.success(
        "Human review saved to the inspection database."
    )
    st.rerun()
