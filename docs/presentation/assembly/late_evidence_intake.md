# P20 Late-Evidence Intake Map

## Intake authority

P20 may ingest a late scientific result only after 00 explicitly marks the result **ACCEPTED**, or supplies an equivalent final evidence classification. Reject partial Codex output, unreviewed logs, preliminary metrics, debug output, speculative calculations, and evidence still awaiting 00 review.

## P19 3D correspondence

| Item | Prepared destination |
| --- | --- |
| Slide | 14 |
| Title | `P19 3D Evaluation Status` |
| Generator section | `slide('P19 3D Evaluation Status', ...)` in `docs/presentation/deck/generate_deck.js` |
| Current visible status | `PENDING / CONTROLLED CORRESPONDENCE` |
| Status/caption transition | Replace only after 00 supplies accepted future wording. Until then retain `P19 3D correspondence - pending controlled experiment`. |
| Prepared field objects | `GT defect ID: pending`; `Mapped defect ID: pending`; `Estimated XYZ: pending`; `Ground-truth XYZ: pending`; `Euclidean 3D error: pending`; `Correspondence provenance: pending` |
| Visual slot | The outlined `Reserved evidence visual` region on the right of slide 14 |
| Expected evidence package | Accepted P19 3D evidence copied into a P20 evidence package with original path, hash, correspondence provenance, and image/visual identity |

Required accepted inputs are GT defect ID, mapped or estimated defect ID, GT XYZ, estimated XYZ, Euclidean 3D error, correspondence classification, evidence/provenance identity, an evidence image or visual, and future status wording from 00. Do not create a correspondence or populate any field from proximity, class similarity, or visual matching.

## Workstream 04 low-light robustness

| Item | Prepared destination |
| --- | --- |
| Slide | 15 |
| Title | `Workstream 04: Low-Light Robustness` |
| Generator section | `slide('Workstream 04: Low-Light Robustness', ...)` in `docs/presentation/deck/generate_deck.js` |
| Current visible status | `PENDING / ARMOURY RESULTS` and `AWAITING ACCEPTED WORKSTREAM 04 RESULTS` |
| Status/caption transition | Replace only after 00 supplies accepted final result wording. Until then retain the pending wording. |
| Chart placeholder | Empty L0-L4 axis frame, with `Accepted detector metric (mAP50-95 if accepted)` on the y-axis |
| Series placeholders | `RAW series reserved` first; `Additional series only if accepted` second |
| Optional visual slot | The slide 15 chart frame may receive only an accepted robustness figure with provenance retained in the P20 evidence package. |

Possible accepted RAW fields are L0-L4 mAP50, L0-L4 mAP50-95, precision, recall, degradation, retention, and an optional per-class highlight. CLAHE or learned comparison series may be added only if 00 accepts them. Do not draw points, bars, curves, or values before accepted evidence arrives.

## Minimum-change insertion procedure

1. Verify explicit 00 ACCEPTED status.
2. Verify evidence identity, hash, and source path.
3. Modify only the prepared destination slide/object and its presenter support record.
4. Replace pending text only where acceptance changes status.
5. Populate the prepared chart or evidence-image slot.
6. Leave all unaffected slides unchanged.
7. Regenerate PPTX and PDF.
8. Run structural/content QA.
9. Visually inspect the changed slide or slides and spot-check adjacent slides.
10. Run the prohibited-claim audit and calculate new hashes.
11. Preserve the bounded change in Git.
12. Return to 00 for final evidence-ingestion review.

This procedure does not authorize final deck freeze.

## Truthful fallback

If P19 3D evidence does not arrive, retain wording equivalent to `P19 3D - pending controlled correspondence`. If Workstream 04 evidence does not arrive, retain wording equivalent to `Low-light robustness evaluation - in progress`. Neither missing input should delay the presentation or lead to fabricated results.
