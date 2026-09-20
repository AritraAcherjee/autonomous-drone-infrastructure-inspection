# P20 Rehearsal Plan

Target duration: approximately **14 minutes 30 seconds**. Explain the system chain rather than reading every value on screen.

| Slide | Title | Target | Key message | Skippable detail if behind |
| --- | --- | ---: | --- | --- |
| 1 | AegisInspect title | 0:20 | State the evidence-bound inspection scope. | Subtitle wording. |
| 2 | Inspection Problem and Objective | 0:45 | Explain traceable inspection and review. | Input-sensor enumeration. |
| 3 | Evidence-Bound System Architecture | 1:00 | Walk through detector to report chain. | Status-card detail. |
| 4 | GYU-DET Dataset and Defect Classes | 0:45 | Establish data foundation and classes. | Full class list. |
| 5 | DET-FINAL-v1 Held-Out Detection Evidence | 1:15 | Explain held-out metrics and validation/test separation. | Individual precision/recall values. |
| 6 | Localization and Simulation Architecture | 0:50 | Separate runtime acceptance from measured accuracy. | ROS/Gazebo version detail. |
| 7 | Simulated Depth and Camera-Frame XYZ | 0:55 | Explain simulated depth and camera-frame boundary. | Test-count detail. |
| 8 | Map-Frame Defect Localization / P15 | 1:00 | Show the defect-to-map transition. | Full identifier/timestamp. |
| 9 | P16 Persistence and Dashboard Review | 1:10 | Show persisted reviewable machine output. | Screenshot microtext. |
| 10 | P17 Deterministic Reporting | 0:55 | Show reportable lineage. | Report field-by-field reading. |
| 11 | P18 Integrated-System Demonstration | 1:00 | Explain package-level dashboard-completion evidence and retry limitation. | Full side-panel prose. |
| 12 | P18 Clean Repeatability | 0:50 | Explain accepted clean repeatability. | New run identity detail. |
| 13 | P19 Localization Evaluation | 1:10 | Present frozen measured metrics without a PASS threshold. | Method subclauses. |
| 14 | P19 3D Evaluation Status | 0:35 | State controlled-correspondence dependency. | Placeholder field list. |
| 15 | Workstream 04: Low-Light Robustness | 0:30 | State results await acceptance. | Future chart labels. |
| 16 | Evidence, Provenance and Reproducibility | 0:40 | Emphasize hash-bound evidence and reproducibility. | Concise identifiers. |
| 17 | Limitations and Evidence Boundaries | 0:50 | State the most material limits. | Repeating prior caveats. |
| 18 | Current Demonstrated Capability | 0:40 | Close with demonstrated capability and pending inputs. | Supporting sentence. |

## Essential slides

Slides 3, 5, 8, 9, and 13 should not be skipped. They explain the system chain, detector evidence, map relation, reviewable persistence, and measured localization.

## Compressible slides

Slides 4, 6, 7, 12, 14, 15, and 16 can be summarized verbally if time is limited.

## Demonstration transition

Switch to a live demonstration after slide 10, once the defect-to-report chain is established. Continue with slide 11 if the live demonstration is skipped or unstable; it begins the verified P18 fallback evidence sequence.

Use `docs/presentation/assembly/demo_backup_plan.md` for the ordered fallback assets.
