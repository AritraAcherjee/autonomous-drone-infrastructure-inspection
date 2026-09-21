# P20 Late-Evidence Intake Map

## Intake authority

P20 may ingest a late scientific result only after 00 explicitly marks the result **ACCEPTED**, or supplies an equivalent final evidence classification. Reject partial Codex output, unreviewed logs, preliminary metrics, debug output, speculative calculations, and evidence still awaiting 00 review.

## P19 3D correspondence

| Item | Prepared destination |
| --- | --- |
| Slide | 14 |
| Title | `P19 Spatial Validation Status` |
| Generator section | `slide('P19 Spatial Validation Status', ...)` in `docs/presentation/deck/generate_deck.js` |
| Current visible status | `PENDING / FINAL 3D CORRESPONDENCE` |
| Status/caption transition | Replace only after 00 supplies an accepted correspondence result. Otherwise retain the explicit fallback wording. |
| Prepared field objects | One outlined `FINAL RESULT SLOT` on the right; the left-side implementation, demonstration and localization statements remain unchanged. |
| Visual slot | The outlined final-result region on the right of slide 14. |
| Expected evidence package | Accepted P19 3D evidence copied into a P20 evidence package with original path, hash, correspondence provenance, and image/visual identity |

Required accepted inputs are GT defect ID, mapped or estimated defect ID, GT XYZ, estimated XYZ, Euclidean 3D error, correspondence classification, evidence/provenance identity, an evidence image or visual, and future status wording from 00. Do not create a correspondence or populate any field from proximity, class similarity, or visual matching.

## Workstream 04 low-light robustness

| Item | Prepared destination |
| --- | --- |
| Slide | 15 |
| Title | `Workstream 04: Low-Light Robustness` |
| Generator section | `slide('Workstream 04: Low-Light Robustness', ...)` in `docs/presentation/deck/generate_deck.js` |
| Current visible status | `SUPPORTED / FROZEN VALIDATION BENCHMARK` for RAW and CLAHE; LL-DETECTOR remains pending. |
| Status/caption transition | Keep RAW/CLAHE fixed. Add LL-DETECTOR only after 00 supplies accepted L0-L4 evaluation results. |
| Chart | Populated RAW and CLAHE mAP50 L0-L4 comparison. |
| Series placeholder | Third LL-DETECTOR series reserved as State A. |
| State B fallback | `Learned low-light adaptation was implemented, but final presentation-time model training/evaluation was not completed.` |

Accepted RAW and CLAHE mAP50 values are already shown. Possible future LL-DETECTOR fields are L0-L4 mAP50 values plus the accepted evidence identity and provenance. Do not infer or interpolate a learned series.

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

If P19 3D evidence does not arrive, retain the prepared implemented/demonstrated/measured/pending wording. If LL-DETECTOR evidence does not arrive, retain the State B sentence verbatim. Neither missing input should delay the presentation or lead to fabricated results.
