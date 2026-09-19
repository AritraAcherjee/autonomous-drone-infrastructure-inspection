# Verified accepted-record lineage

`DET-FINAL-v1` detector observation `21.813000000-0` in `camera_optical_frame` → P15 mapped defect `P15D-10627c5f-3f84-5c64-ab2d-3e574b6e97ee` in `map` → P16 handoff DTO and persisted SQLite record → original P16 dashboard screenshots → deterministic P17 report.

| Stage | Verified facts | Original source |
|---|---|---|
| Detector/P15 | Honeycombing; confidence `0.004553093574941158`; timestamp `1970-01-01T00:00:21.813000Z`; model `DET-FINAL-v1` | `input/mapped_defect.json` |
| P15 map | XYZ `3.9000027127470087`, `-0.09877989958311785`, `0.0032930137079122536`; frame `map` | `input/mapped_defect.json` |
| P16 persistence | one inspection, one defect, one evidence; observation count `1`; `UNREVIEWED` | `database/real_handoff.sqlite3` |
| P16 dashboard | original manifest-verified overview and detail screenshots | `dashboard/` |
| P17 | deterministic report SHA-256 `b5d506de2136349bafbec15aa225eb255ecb7c0ede348e2b29f98bc439c2551e` | `report/inspection_2026091901.md` |

`provenance/lineage.json` is runtime lineage. Git preservation provenance is separately `eb4013fa236ab758c6b84e1a3ae02579bbfe488f`.

This is extremely-low-confidence, **UNREVIEWED machine output**, not a confirmed physical defect, diagnosis, severity assessment, repair recommendation, or structural-safety conclusion.
