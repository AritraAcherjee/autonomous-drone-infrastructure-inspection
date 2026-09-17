"""Static dependency-boundary tests for the pure P15 package."""

from __future__ import annotations

import ast
from pathlib import Path


PURE_PACKAGE = Path("src/defect_mapping")

FORBIDDEN_PREFIXES = (
    "src.storage",
    "rclpy",
    "tf2_ros",
    "gazebo",
    "ultralytics",
    "torch",
    "streamlit",
    "sqlite3",
)


def _imports_from_file(path: Path) -> set[str]:
    tree = ast.parse(
        path.read_text(encoding="utf-8-sig"),
        filename=str(path),
    )

    imported: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                imported.add(node.module)

    return imported


def test_pure_package_has_no_forbidden_direct_dependencies() -> None:
    violations: list[str] = []

    for path in sorted(PURE_PACKAGE.glob("*.py")):
        for imported in sorted(_imports_from_file(path)):
            if imported.startswith(FORBIDDEN_PREFIXES):
                violations.append(
                    f"{path.as_posix()}: {imported}"
                )

    assert violations == []


def test_pure_package_never_imports_p16_storage_models() -> None:
    for path in sorted(PURE_PACKAGE.glob("*.py")):
        imported = _imports_from_file(path)

        assert "src.storage.models" not in imported
        assert "src.storage" not in imported


def test_pure_package_contains_no_ros_transform_or_database_code() -> None:
    forbidden_text = (
        "rclpy",
        "tf2_ros",
        "camera_optical_frame -> map",
        "SQLiteInspectionRepository",
        "InspectionService",
        "streamlit",
        "ultralytics",
    )

    for path in sorted(PURE_PACKAGE.glob("*.py")):
        text = path.read_text(
            encoding="utf-8-sig"
        )

        for token in forbidden_text:
            assert token not in text, (
                f"{token!r} unexpectedly found in "
                f"{path.as_posix()}"
            )
