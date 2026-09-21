# P20 Compact Presentation Evidence Index

Classification: `P20 FINALIZATION_READY_FOR_LAST_ARMOURY_EVIDENCE`

This index points to accepted evidence; it does not rewrite sealed artifacts.
Use it for presentation preparation and Q&A.

| Topic | Presentation state | Accepted result / identity | Evidence reference / provenance |
| --- | --- | --- | --- |
| DET-FINAL | `SUPPORTED` | `DET-FINAL-v1 / YOLO26s`; GYU test mAP50 `0.29669431228680787`; mAP50-95 `0.17480040543737643`; validation-selected threshold `0.18618618618618618` | `outputs/evaluation/defect_detection/DET-FINAL-v1/GYU-DET-TEST/`; checkpoint SHA-256 `4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3`; Git `d9cd2f5b58559d45e5d4a42ce702c595345e292b` |
| RAW low light L0-L4 | `SUPPORTED` | mAP50 `0.3886917344`, `0.3796280361`, `0.3342489847`, `0.1263098877`, `0.0031301687` | Accepted 00 Control Center P20 finalization directive, 2026-09-21; upstream archive/hash not supplied to this checkout |
| CLAHE low light L0-L4 | `SUPPORTED` | mAP50 `0.2657391403`, `0.2656420531`, `0.2240838264`, `0.0746161035`, `0.0033883546` | Accepted 00 Control Center P20 finalization directive, 2026-09-21; upstream archive/hash not supplied to this checkout |
| P18 primary mapped example | `DEMONSTRATED` | Honeycombing machine class; confidence `0.011138029396533966`; camera XYZ approximately `[0.0056, -0.0028, 3.1251] m`; session-local map XYZ approximately `[3.8882, 0.0712, -0.0035] m`; `UNREVIEWED` | `outputs/presentation/p18_evidence/source_archives/stop_b_p18_clean_repeatability_run.zip`; mapped JSON SHA-256 `11073e46c33c10f6ffc80f7fd84f8b0d0cbc00068bbfb39b02130f65b0872808`; overview `6338820ad43d629c39fa7c3761a5ac3809359dfd87f306c980baea6dd50e6fa6`; detail `68319d3f9b8ea8e754d7cceae29c411bf924c3cc0ca1cff7824dcbab67da5b05`; report `810f1e9dfa9c3e0b4a78e6d4e2448bb2bd2057e595028a32e3e69c49affa3f93` |
| P16 persistence/dashboard | `DEMONSTRATED` | Accepted record persisted with `UNREVIEWED` state; dashboard overview/detail available | `outputs/presentation/p16_p17_evidence/`; DB SHA-256 `5297ed89c50ea362ed229bc74155e1582882dd8284ebf07b2d951f27fe96bbd5` |
| P17 deterministic report | `DEMONSTRATED` | Accepted mapped record preserved without inferred severity or safety conclusion | Report SHA-256 `b5d506de2136349bafbec15aa225eb255ecb7c0ede348e2b29f98bc439c2551e`; Git preservation `eb4013fa236ab758c6b84e1a3ae02579bbfe488f` |
| P16/P17 source archive | `SUPPORTED` | Verified source package; manifest `108 / 108 PASS` | ZIP SHA-256 `df3f87f0edcea09f50394ca4ef7ca8d44e8718d93c3ca648b5a38a689f313ec2` |
| P18 first integrated retry | `DEMONSTRATED` | Same-observation chain validated; browser capture absent in first retry | Archive SHA-256 `afdf4aa12d589c5984d637fcb122f6ef2a810cfa1111434e9135fee63f3d2f2d`; `outputs/presentation/p18_evidence/runtime/first_integrated_result.json` |
| P18 dashboard completion | `DEMONSTRATED` | PASS; accepted browser screenshot | Archive SHA-256 `b52cf8db39c0a0fb936dc25eaf9f3a1af83b26a4310a3ee1e8fc5a671d28ae61`; screenshot SHA-256 `da9bbf465ebf11760a03ee0bf52846c8feef5108dc582e677f5938ff538d5a55` |
| P18 clean repeatability | `DEMONSTRATED` | PASS under unchanged source/configuration | Archive SHA-256 `0823e59a4267a3f6c844bbbf2f63bdb5f19091511dda36826f72f058cc911d82`; result SHA-256 `9a1636daa5d6fac503568801d3614a559820034a68f8d403f9533c1eb87e1b69` |
| P19 localization | `MEASURED` | Presentation-rounded ATE translational RMSE `0.595 m` (76 samples); RPE translational RMSE `0.341 m`; RPE rotational RMSE `1.707 degrees` (44 pairs) | P19 preservation Git `4c7bd79ad3b6356dff08b0adf30ece3e09a4d78a`; frozen 3-18 s methodology; trajectory accuracy only, not absolute defect-position accuracy |
| P19 3D correspondence | `PENDING` | `FROZEN PENDING / FINAL QUANTITATIVE CORRESPONDENCE NOT COMPLETED`; P19 development closed for capstone | Accepted 00/MSI capstone-freeze disposition, 2026-09-21; no further MSI scientific result expected |
| LL-DETECTOR | `PENDING` | No model metric shown. Fallback: “Learned low-light adaptation was implemented, but final presentation-time model training/evaluation was not completed.” | Prepared State A/State B slot on slide 15; insert only accepted ARMOURY L0-L4 results |

## Optional P19 technical-Q&A references

The independently supplied and verified MSI artifacts substantiate these
advanced R&D validation-infrastructure facts. They are retained for technical
Q&A and are not production runtime requirements or a completed 3D
correspondence result.

| MSI evidence file | Verified point |
| --- | --- |
| `P19 qualifying receipt 0001.json` | `CONSECUTIVE_VALID_INDEX = 710` |
| `P19 RGB/depth binding result.json` | `RGB_NATIVE_TO_OPERATIONAL = PASS`; `DEPTH_NATIVE_TO_OPERATIONAL = PASS`; `TIMESTAMP_MATCHING_USED = FALSE` |
| `P19 startup alignment result.json` | `RESULT = PASS`; `CONTRACT_VALIDATOR = PASS`; `FRAME_IDENTITY = PASS`; `PRE_MOTION_SOURCE = PASS`; `FINITE_HOMOGENEOUS_ORTHONORMAL_DETERMINANT_SCALE = PASS`; `SELECTED_CANDIDATE_RECOMPUTED_TRANSFORM = PASS`; `OPERATIONAL_GT_PUBLICATION = NO` |
| `P19 truth result.json` | `RESULT = PASS`; `TARGET_PIXELS = 307200`; `TOTAL_PIXELS = 307200`; `BACKGROUND_PIXELS = 0`; `OTHER_TARGET_PIXELS = 0`; `UNRESOLVED_PIXELS = 0` |

These are component/sub-gate PASS results only. Final label:
`FINAL 3D CORRESPONDENCE VALIDATION = PENDING`.

## Presentation artifacts

- PPTX: `outputs/presentation/AegisInspect_P20_working_draft.pptx`
- PDF fallback: `docs/presentation/deck/rendered/AegisInspect_P20_working_draft.pdf`
- P16/P17 screenshots and records: `outputs/presentation/p16_p17_evidence/`
- P18 screenshots and accepted runtime/repeatability packages: `outputs/presentation/p18_evidence/`
- Offline demo order: `docs/presentation/assembly/demo_backup_plan.md`

The MSI slot is resolved. The deck remains open only for bounded LL-DETECTOR
evidence ingestion from ARMOURY. It is not final-frozen.
