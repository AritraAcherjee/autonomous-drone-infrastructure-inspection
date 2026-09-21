# P20 Rehearsal Plan

Target duration: approximately **14 minutes** plus Q&A. Explain the system chain rather than reading every value on screen.

| Slide | Title | Target | Key message | Skippable detail if behind |
| --- | --- | ---: | --- | --- |
| 1 | AegisInspect title | 0:20 | State the evidence-bound inspection scope. | Subtitle wording. |
| 2 | Inspection Problem and Objective | 0:35 | Explain traceable inspection and review. | Input-sensor enumeration. |
| 3 | Evidence-Bound System Architecture | 0:55 | Walk through detector to report chain. | Status-card detail. |
| 4 | GYU-DET Dataset and Defect Classes | 0:35 | Establish data foundation and classes. | Full class list. |
| 5 | DET-FINAL-v1 Held-Out Detection Evidence | 1:00 | Explain held-out metrics and validation/test separation. | Individual precision/recall values. |
| 6 | Localization and Simulation Architecture | 0:40 | Separate runtime acceptance from measured accuracy. | ROS/Gazebo version detail. |
| 7 | Simulated Depth and Camera-Frame XYZ | 0:45 | Explain simulated depth and camera-frame boundary. | Test-count detail. |
| 8 | Map-Frame Defect Localization / P15 | 0:55 | Show the defect-to-map transition. | Full identifier/timestamp. |
| 9 | P16 Persistence and Dashboard Review | 1:00 | Show persisted reviewable machine output. | Screenshot microtext. |
| 10 | P17 Deterministic Reporting | 0:45 | Show reportable lineage. | Report field-by-field reading. |
| 11 | P18 Integrated-System Demonstration | 0:55 | Explain package-level dashboard-completion evidence and retry limitation. | Full side-panel prose. |
| 12 | P18 Integrated Inspection Evidence | 0:40 | Trace the accepted low-confidence UNREVIEWED observation through projection, session-local mapping, dashboard and report. | Exact coordinates. |
| 13 | P19 Localization Evaluation | 0:55 | Present rounded trajectory metrics and distinguish them from defect-position accuracy. | Method subclauses. |
| 14 | P19 Capstone Disposition | 0:45 | State P18 demonstrated, localization measured, and final 3D correspondence frozen pending. | Technical-Q&A infrastructure. |
| 15 | Workstream 04: Low-Light Robustness | 0:55 | Explain RAW degradation, CLAHE comparison and optional LL result. | Exact table values. |
| 16 | Evidence, Provenance and Reproducibility | 0:30 | Emphasize hash-bound evidence and reproducibility. | Concise identifiers. |
| 17 | Limitations and Evidence Boundaries | 0:45 | State the most material limits. | Repeating prior caveats. |
| 18 | Application and Commercial Value | 0:45 | Connect the implementation to reviewable inspection workflows. | Individual vertical examples. |
| 19 | Current Demonstrated Capability | 0:35 | Close with demonstrated capability and ARMOURY as the only open late-evidence input. | Supporting sentence. |

## Essential slides

Slides 3, 5, 8, 9, 11, 13 and 15 should not be skipped. They explain the system chain, detector evidence, map relation, reviewable persistence, P18 integration, measured localization and low-light robustness.

## Compressible slides

Slides 4, 6, 7, 10, 12, 14 and 16 can be summarized verbally if time is limited.

## Demonstration transition

Use the offline P18 evidence sequence by default after slide 10. A live
demonstration is optional and must never be required for presentation success.

Use `docs/presentation/assembly/demo_backup_plan.md` for the ordered fallback assets.
