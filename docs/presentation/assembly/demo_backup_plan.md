# P20 Demo and Backup Evidence Plan

The purpose of this plan is to prevent presentation success from depending
on a single live runtime path.

## 1. Live demo

Current state:

**NOT YET FROZEN**

Candidate live components may include:

- ROS/Gazebo simulation foundation;
- simulated metric depth;
- camera-frame projection service;
- dashboard;
- deterministic report output;
- localization only if accepted runtime evidence is available.

Do not improvise unapproved localization runtime commands in P20.

Use the owner-approved MSI command sequence when that sequence is frozen.

## 2. Backup screenshots

Current state:

**PARTIALLY PREPARED FROM VERIFIED ORIGINALS**

Required screenshot categories:

- simulation/world and drone;
- live ROS topic evidence;
- depth image / depth validation evidence;
- camera projection result;
- verified P16 dashboard overview and detail;
- deterministic P17 report excerpt;
- P19 accepted trajectory/error plots where preserved by the P19 package;
- provenance and hash summary.

The verified P16/P17 assets and the verified P18 dashboard-completion and
repeatability screenshots are suitable for an offline backup demo. P19 3D
metrics and Workstream 04 results remain pending.

## 3. Backup recorded clips

Current state:

**PENDING_CAPTURE**

Candidate clips:

- Gazebo sensor/runtime sequence;
- depth/projection demonstration;
- dashboard review workflow;
- report workflow;
- future RTAB-Map localization;
- future integrated P18 run.

Do not fabricate or stage a clip as evidence for a result that has not run.

## 4. Command-sequence package

Current state:

**PENDING_OWNER_FREEZE**

Package should eventually contain:

- exact terminal/window name;
- repository/worktree;
- canonical SHA;
- environment activation;
- launch command;
- evidence command;
- expected success signature;
- stop/fallback instruction.

## 5. Canonical evidence already available

Detector:

- DET-FINAL-v1 held-out GYU result;
- frozen checkpoint SHA256;
- aggregate metrics;
- per-class metrics;
- provenance;
- timing.

External generalization:

- `GEN-DAMSEGMENT-ZS-001`;
- scientific completion evidence;
- domain comparison;
- shared-class metrics.

Simulation / geometry:

- Stop-B ROS/Gazebo foundation runtime report;
- simulated metric depth report;
- camera-frame projection report.

Application layer:

- verified P15→P16 DTO and mapped-defect lineage;
- verified P16 dashboard overview/detail and persisted database record;
- verified deterministic P17 report excerpt;
- P19 localization provenance and accepted plots when included from its
  preservation package.

## 6. Evidence still pending

- explicit GT↔mapped-defect correspondence and P19 3D metrics;
- Workstream 04 final low-light robustness evidence.

## 7. Day-of-presentation fallback order

Recommended fallback order:

1. live demo when verified and stable;
2. recorded clip from the same canonical evidence run;
3. screenshot/evidence sequence;
4. static architecture + quantitative result slide.

A fallback must represent the same evidence scope as the claim being made.

## 8. Final safety check

Before presenting:

- verify canonical commit SHAs;
- verify detector numbers;
- verify DamSegment numbers;
- verify the P16/P17 example remains labelled extremely-low-confidence and UNREVIEWED;
- verify P19 localization remains labelled MEASURED, without an accuracy PASS claim;
- verify every formerly PENDING value has objective accepted evidence;
- keep unresolved values as PENDING;
- confirm final title and Stop level with 00.
