# Existing P16/P17 architecture and scoped boundary corrections

Inspection was read-only before editing. The localization checkout is the preserved
07 branch at `190bf7653b203c97418842474aa7cbd8016bfd44`, independently equal to live
origin. Canonical main is `3fc6ac001e71c1ab56b2b810cd2d595358a55e28`, already containing
P16. P17 exists on `origin/P17/reporting` at
`66d33acd00704d2f79b157471702e3709ce9d716`. Its existing implementation was used in a
detached worktree `/tmp/aegis-stopb-p16p17.J0c6Zg/source`; no integration branch or
merge was created. Original main and 07 sources were not modified.

## Paths and contracts

- `src/integrations/p15_p16_adapter.py`: existing mapped record/evidence DTO boundary.
- `src/storage/models.py`: frozen dataclasses, review and inspection status enums.
- `database/schema.sql`, `src/storage/schema.py`: existing SQLite schema, four tables,
  foreign keys; no migration required or performed. `user_version=0` is recorded,
  not misrepresented as an application migration number.
- `src/storage/repository.py`: transaction-managed, foreign-key-enforced SQLite.
  Create-only defect ingestion rejects an existing ID with `DuplicateDefectError`.
  Evidence uniqueness rejects the same frame/bbox with `DuplicateEvidenceError`.
- `src/storage/service.py`: supported application API used for every actual write.
- `dashboard/app.py`, `dashboard/components.py`: existing Streamlit UI, database path
  via `AEGISINSPECT_DB_PATH`, separate machine data and human review form.
- `src/integrations/p16_p17_adapter.py`: existing read-only service-to-report adapter.
- `src/reporting/models.py`, `validation.py`, `rendering.py`: existing deterministic
  Markdown pipeline. Float repr and UTC ISO timestamps; no engineering inference.
- `tests/storage`, `tests/integrations`, `tests/reporting`: 206 existing tests passed
  before correction; 215 passed after adding nine focused boundary regressions.

## Proven small integration defects

1. `_datetime_to_text(... timespec="seconds")` discarded the accepted .813 seconds.
   Removing the forced seconds precision preserves subseconds and leaves whole-second
   formatting unchanged. This changes serialization, not schema or source timestamps.
2. `create_inspection` exposed only an auto-allocated ID while the immutable P15 DTO
   references inspection 2026091901. Add an optional keyword identity on the existing
   service/repository create call, validated as positive signed SQLite 64-bit integer.
   Default auto-allocation remains unchanged; collisions fail rather than overwrite.
   The upstream DTO, models, and schema are untouched.
3. UI rounded confidence to .005. Use full float repr in defect/evidence table data and
   detail view. Caption now describes persisted inspection data rather than demo data.
   No change to the stored confidence, review state, coordinates, or scientific logic.

Nine regressions failed before these corrections and passed afterward; raw red/green
logs are retained. These five files (four modified, one new test) remain UNCOMMITTED
in the detached worktree. Exact diff and file snapshots are preserved under `git/`.
No P17 source correction, schema migration, detector change, localization change,
P15 change, depth/TF change, commit, push, merge, START, RESET, or P18 was performed.

## Real data and time semantics

The accepted JSON and DTO are copied byte-for-byte. Datetimes are parsed, not replaced.
Full-precision numeric values are preserved. P15 first/last_seen and evidence time
encode ROS simulation 21.813 s as a UTC-aware epoch datetime; they are NOT wall-clock
capture time. Inspection started_at is the recorded original runtime invocation UTC.
The structure row is explicitly an evidence-session container for simulated imagery,
not a claim of surveying a physical asset. Completed time and location remain absent.

Default UNREVIEWED and null review notes remain. No review form is submitted. Confidence
0.004553093574941158 is extremely low and proves integration only. It is not physical
confirmation of Honeycombing or an engineering/safety conclusion.

## Browser capture

Installed Windows Chrome 153 captured the existing UI served by isolated Streamlit
1.64.0 on loopback. The first virtual-time screenshot was premature loading evidence
only (`real_dashboard.png`), NOT the accepted screenshot. Linux could not access the
Windows-local CDP port. Native Windows CDP then waited for exact record text and saved
`dashboard_overview.png` and `dashboard_detail.png`; these are unedited browser pixels.
Only normal viewport scrolling occurred. DOM, displayed data, browser/process identity,
server logs, and cleanup records are preserved. No invented screenshot or UI was used.
