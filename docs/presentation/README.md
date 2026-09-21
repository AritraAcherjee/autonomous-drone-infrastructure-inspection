# P20 Presentation Evidence Foundation

This directory is the evidence-backed source for AegisInspect capstone
documentation and presentation content.

It is intentionally separate from operational implementation code.

## Frozen claim states

Only these presentation claim states are valid:

- `SUPPORTED`
- `IMPLEMENTED`
- `DEMONSTRATED`
- `MEASURED`
- `PENDING`

A `SUPPORTED`, `DEMONSTRATED`, or `MEASURED` claim requires objective
evidence. `IMPLEMENTED` identifies functionality without converting it into
an accuracy result.

No claim may be silently promoted because software exists, a synthetic
fixture passes, or an architecture is planned.

## Frozen evidence scopes

- `DATA_FOUNDATION`
- `REAL_HELD_OUT`
- `EXTERNAL_BENCHMARK`
- `SIMULATION_RUNTIME`
- `IMPLEMENTATION_TEST`
- `SYNTHETIC_DEMO`
- `PENDING`

Quantitative presentation material must preserve this scope either on the
slide, in a badge/subtitle, or in speaker-note/evidence metadata.

## Canonical structured sources

- `claim_matrix.json`
  - one record per presentation-safe or explicitly prohibited/pending claim
- `workstream_status.json`
  - current presentation status of relevant AegisInspect workstreams
- `results_table.json`
  - canonical quantitative table
- `evidence_inventory.json`
  - source references, commits, hashes and validation evidence

## Human-facing source material

- `presentation_outline.md`
  - working slide sequence and speaker-note source
- `limitations_and_qa.md`
  - required limitations and evidence-safe Q&A responses
- `demo_readiness_checklist.md`
  - pre-presentation/demo verification checklist

## Critical evidence boundaries

### Real held-out detector result

DET-FINAL-v1 has accepted one-time held-out GYU-DET test evidence.

These are detector metrics, not generic "accuracy" or "drone accuracy."

### External benchmark

DamSegment is a completed zero-shot external scientific result.

It evaluates only the shared Crack and Spalling-to-Breakage mapping.

Weak transfer, especially Crack recall, is part of the scientific result
and must remain visible.

### Simulation/runtime evidence

ROS/Gazebo, simulated depth and camera-frame XYZ projection have verified
simulation/runtime evidence.

This does not establish real-world depth accuracy or real map-frame
localization accuracy.

### Synthetic dashboard data

P16 demo records are synthetic/test-only.

They are not field-inspection records.

### Spatial results

Accepted LiDAR ICP localization ATE/RPE are `MEASURED` against simulation
ground truth. Final quantitative simulator-ground-truth correspondence
validation for 3D defect-position accuracy remains `PENDING`.

Never replace an unmeasured result with `0`, `N/A`, a synthetic fixture
value, or an inferred number.

## Final-title rule

The final Stop-level/title is controlled by 00.

P20 must remain adaptable to the eventual accepted Stop level.

Do not freeze "Stop A complete", "Stop B complete", or a higher system
completion claim in these materials without explicit 00 authorization.
