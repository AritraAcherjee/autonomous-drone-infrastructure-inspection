"""Presentation helpers for the P16 Streamlit dashboard."""

from __future__ import annotations

from collections.abc import Iterable

from src.storage.models import Defect, Evidence


def format_confidence(value: float) -> str:
    """Preserve the stored value, including very low detector confidence."""

    return repr(value)


def _timestamp_text(value) -> str:
    if value is None:
        return "N/A"

    return value.isoformat()


def defect_table_rows(
    defects: Iterable[Defect],
) -> list[dict[str, object]]:
    """Convert persisted defects to dashboard-safe table rows."""

    return [
        {
            "Defect ID": defect.defect_id,
            "Class": defect.class_name,
            "Confidence": format_confidence(defect.confidence),
            "X (m)": defect.x_m,
            "Y (m)": defect.y_m,
            "Z (m)": defect.z_m,
            "Frame": defect.coordinate_frame,
            "Observations": defect.observation_count,
            "Review": defect.review_status.value,
            "Model": defect.model_version,
        }
        for defect in defects
    ]


def evidence_table_rows(
    evidence: Iterable[Evidence],
) -> list[dict[str, object]]:
    """Convert evidence rows to dashboard-safe presentation data."""

    return [
        {
            "Evidence ID": item.evidence_id,
            "Frame ID": item.frame_id,
            "Timestamp": _timestamp_text(item.timestamp),
            "Confidence": format_confidence(item.confidence),
            "BBox": (
                f"({item.bbox_x1:.1f}, {item.bbox_y1:.1f}) - "
                f"({item.bbox_x2:.1f}, {item.bbox_y2:.1f})"
            ),
            "Image Path": item.image_path or "N/A",
            "Crop Path": item.crop_path or "N/A",
        }
        for item in evidence
    ]
