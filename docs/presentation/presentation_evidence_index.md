# P20 Compact Presentation Evidence Index

Classification: `P20 FINALIZATION_READY_FOR_LAST-EVIDENCE_INGESTION`

This index points to accepted evidence; it does not rewrite sealed artifacts.
Use it for presentation preparation and Q&A.

| Topic | Presentation state | Accepted result / identity | Evidence reference / provenance |
| --- | --- | --- | --- |
| DET-FINAL | `SUPPORTED` | `DET-FINAL-v1 / YOLO26s`; GYU test mAP50 `0.29669431228680787`; mAP50-95 `0.17480040543737643`; validation-selected threshold `0.18618618618618618` | `outputs/evaluation/defect_detection/DET-FINAL-v1/GYU-DET-TEST/`; checkpoint SHA-256 `4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3`; Git `d9cd2f5b58559d45e5d4a42ce702c595345e292b` |
| RAW low light L0-L4 | `SUPPORTED` | mAP50 `0.3886917344`, `0.3796280361`, `0.3342489847`, `0.1263098877`, `0.0031301687` | Accepted 00 Control Center P20 finalization directive, 2026-09-21; upstream archive/hash not supplied to this checkout |
| CLAHE low light L0-L4 | `SUPPORTED` | mAP50 `0.2657391403`, `0.2656420531`, `0.2240838264`, `0.0746161035`, `0.0033883546` | Accepted 00 Control Center P20 finalization directive, 2026-09-21; upstream archive/hash not supplied to this checkout |
| P15 mapped example | `DEMONSTRATED` | `P15D-10627c5f-3f84-5c64-ab2d-3e574b6e97ee`; map XYZ `(3.9000027127470087, -0.09877989958311785, 0.0032930137079122536)` | `outputs/presentation/p16_p17_evidence/input/mapped_defect.json`; lineage package below |
| P16 persistence/dashboard | `DEMONSTRATED` | Accepted record persisted with `UNREVIEWED` state; dashboard overview/detail available | `outputs/presentation/p16_p17_evidence/`; DB SHA-256 `5297ed89c50ea362ed229bc74155e1582882dd8284ebf07b2d951f27fe96bbd5` |
| P17 deterministic report | `DEMONSTRATED` | Accepted mapped record preserved without inferred severity or safety conclusion | Report SHA-256 `b5d506de2136349bafbec15aa225eb255ecb7c0ede348e2b29f98bc439c2551e`; Git preservation `eb4013fa236ab758c6b84e1a3ae02579bbfe488f` |
| P16/P17 source archive | `SUPPORTED` | Verified source package; manifest `108 / 108 PASS` | ZIP SHA-256 `df3f87f0edcea09f50394ca4ef7ca8d44e8718d93c3ca648b5a38a689f313ec2` |
| P18 first integrated retry | `DEMONSTRATED` | Same-observation chain validated; browser capture absent in first retry | Archive SHA-256 `afdf4aa12d589c5984d637fcb122f6ef2a810cfa1111434e9135fee63f3d2f2d`; `outputs/presentation/p18_evidence/runtime/first_integrated_result.json` |
| P18 dashboard completion | `DEMONSTRATED` | PASS; accepted browser screenshot | Archive SHA-256 `b52cf8db39c0a0fb936dc25eaf9f3a1af83b26a4310a3ee1e8fc5a671d28ae61`; screenshot SHA-256 `da9bbf465ebf11760a03ee0bf52846c8feef5108dc582e677f5938ff538d5a55` |
| P18 clean repeatability | `DEMONSTRATED` | PASS under unchanged source/configuration | Archive SHA-256 `0823e59a4267a3f6c844bbbf2f63bdb5f19091511dda36826f72f058cc911d82`; result SHA-256 `9a1636daa5d6fac503568801d3614a559820034a68f8d403f9533c1eb87e1b69` |
| P19 localization | `MEASURED` | ATE RMSE `0.595396782192 m` (76 samples); RPE translation RMSE `0.340604743330 m`; RPE rotation RMSE `1.707265244063 deg` (44 pairs) | P19 preservation Git `4c7bd79ad3b6356dff08b0adf30ece3e09a4d78a`; frozen 3-18 s methodology; no accuracy PASS/FAIL threshold |
| P19 3D correspondence | `PENDING` | Final quantitative simulator-ground-truth correspondence validation for 3D defect-position accuracy | Prepared dual-state slot on slide 14; insert only an accepted MSI result |
| LL-DETECTOR | `PENDING` | No model metric shown. Fallback: “Learned low-light adaptation was implemented, but final presentation-time model training/evaluation was not completed.” | Prepared State A/State B slot on slide 15; insert only accepted ARMOURY L0-L4 results |

## Presentation artifacts

- PPTX: `outputs/presentation/AegisInspect_P20_working_draft.pptx`
- PDF fallback: `docs/presentation/deck/rendered/AegisInspect_P20_working_draft.pdf`
- P16/P17 screenshots and records: `outputs/presentation/p16_p17_evidence/`
- P18 screenshots and accepted runtime/repeatability packages: `outputs/presentation/p18_evidence/`
- Offline demo order: `docs/presentation/assembly/demo_backup_plan.md`

The deck remains open only for bounded LL-DETECTOR and final P19 3D
evidence ingestion. It is not final-frozen.
