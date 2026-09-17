# P16 Inspection Persistence Database

This directory contains the SQLite schema for the AegisInspect P16
Database + Dashboard foundation.

## Scope

P16 persists inspection product data that has already been decided by
upstream perception and fusion workstreams.

P16 does not decide:

- spatial clustering or deduplication
- track association
- defect fusion rules
- persistent defect identity
- localization or coordinate transforms
- defect severity
- safety conclusions

The future P15 boundary supplies an already-decided MappedDefectRecord.

## Tuesday schema

The Tuesday foundation intentionally contains four application entities:

1. structures
2. inspections
3. defects
4. evidence

Human review state is stored separately from machine-produced fields.

Allowed review states:

- UNREVIEWED
- CONFIRMED
- REJECTED
- NEEDS_INVESTIGATION

Machine-created defects begin as UNREVIEWED. The machine ingest boundary
cannot auto-confirm a defect.

## Coordinates and provenance

Mapped defect coordinates retain:

- x_m
- y_m
- z_m
- coordinate_frame

The Tuesday synthetic demonstration uses the map frame.

Additional provenance includes:

- model_version
- observation_count
- first_seen
- last_seen
- evidence frame IDs
- timestamps
- confidence
- bounding boxes

## SQLite behavior

Foreign-key enforcement is enabled for every repository connection.

Deletion relationships:

- Structure to Inspection: RESTRICT
- Inspection to Defect: CASCADE
- Defect to Evidence: CASCADE

The dashboard does not expose deletion controls.

## Database path

The dashboard resolves its database in this order:

1. AEGISINSPECT_DB_PATH
2. database/aegisinspect.sqlite3

Generated *.sqlite3 files are ignored by Git.

## Synthetic demo data

Create or recreate the deterministic test-only database with:

python scripts/p16/seed_demo.py

The generated demo contains:

- one synthetic structure
- one synthetic inspection
- three synthetic mapped defects
- four synthetic evidence rows

All demo content is synthetic/test-only. It must not be presented as
field inspection evidence or detector evaluation evidence.

## Dashboard

Run locally with:

python -m streamlit run dashboard/app.py

The dashboard accesses persistence through InspectionService and does not
execute SQLite statements directly.

It provides:

- inspection selection
- inspection summary
- class filtering
- review-status filtering
- minimum-confidence filtering
- mapped defect table
- defect detail and XYZ/frame provenance
- evidence display
- explicit human-review controls

## Requirements

P16-specific Python dependencies are listed in requirements-p16.txt.
