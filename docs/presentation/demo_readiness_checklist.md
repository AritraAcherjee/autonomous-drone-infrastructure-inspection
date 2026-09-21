# P20 Demo Readiness Checklist

This checklist prevents presentation setup from silently converting
implementation or synthetic evidence into real-system claims.

## A. Repository / evidence state

- [x] P20 claim matrix exists.
- [x] P20 results table exists.
- [x] P20 evidence inventory exists.
- [x] P20 workstream-status matrix exists.
- [ ] Final Stop-level/title authorized by 00.

## B. Dataset slide

Before presenting:

- [x] show 10,398 supervised baseline-v1 images;
- [x] show 48,392 annotations;
- [x] show six defect classes;
- [x] label counts `DATA_FOUNDATION`;
- [ ] do not imply dataset counts are detector accuracy.

## C. Internal detector results

Before presenting:

- [x] use DET-FINAL-v1 only;
- [x] label GYU TEST as `REAL_HELD_OUT`;
- [x] show mAP50 and mAP50-95 from canonical results;
- [x] identify validation-selected diagnostic threshold;
- [x] state test threshold was not optimized on held-out data;
- [ ] do not label mAP as generic accuracy;
- [ ] do not claim whole-system FPS from detector timing.

## D. DamSegment external benchmark

Before presenting:

- [x] label result `EXTERNAL_BENCHMARK`;
- [x] identify `GEN-DAMSEGMENT-ZS-001`;
- [x] state one held-out frozen evaluation;
- [x] state shared classes only;
- [x] show weak zero-shot transfer;
- [x] retain Crack-recall limitation;
- [ ] do not label as six-class GYU performance.

## E. ROS/Gazebo demonstration

If demonstrating live simulation:

- [x] evidence exists for Stop-B foundation runtime;
- [x] depth evidence exists for `32FC1` metric simulated depth;
- [x] ProjectCamera runtime evidence exists;
- [ ] verify MSI runtime environment is actually available before relying
      on a live demonstration;
- [ ] have recorded evidence/screenshots/logs ready as fallback;
- [ ] label all runtime evidence `SIMULATION_RUNTIME`.

## F. Simulated depth

Before presenting:

- [x] label metres / `32FC1`;
- [x] label `camera_optical_frame`;
- [x] identify 640 x 480 depth stream;
- [ ] do not call this real-world depth accuracy.

## G. Camera-frame projection

Before presenting:

- [x] identify ProjectCamera service;
- [x] state result frame is `camera_optical_frame`;
- [x] mention fail-closed/invalid XYZ behavior if useful;
- [ ] do not call camera-frame XYZ map localization;
- [ ] do not show a real defect XYZ accuracy value.

## H. P15 mapping

- [x] software implementation may be demonstrated/described;
- [x] use `IMPLEMENTED` or `DEMONSTRATED` as supported by the evidence;
- [x] accepted P18 map-frame workflow is demonstrated; absolute defect-position accuracy remains frozen pending.

## I. P16 dashboard

- [x] persistence/dashboard may be demonstrated;
- [x] label current records `SYNTHETIC_DEMO`;
- [x] explain explicit human-review state;
- [ ] do not describe synthetic records as field data.

## J. P17 reporting

- [x] deterministic report-generation implementation may be shown;
- [x] use `IMPLEMENTED` or `DEMONSTRATED` as supported by the evidence;
- [ ] do not claim the report came from a completed autonomous mission
      unless new accepted evidence exists.

## K. VIO / localization

Current presentation values:

- ATE translational RMSE: `0.595 m` over 76 samples (`MEASURED`);
- RPE translational RMSE: `0.341 m` (`MEASURED`);
- RPE rotational RMSE: `1.707 degrees` over 44 pairs (`MEASURED`);
- qualification: trajectory accuracy, not absolute defect-position accuracy;
- accuracy classification: no frozen PASS/FAIL threshold.

- [x] accepted P19 trajectory evaluation is represented;
- [x] frozen methodology and evidence identity are retained;
- [x] values are labelled `MEASURED`, not accuracy `PASS`.

## L. 3D defect localization

Current presentation values:

- mean error: `PENDING`
- median error: `PENDING`
- RMSE: `PENDING`
- P95: `PENDING`
- matched/unmatched real performance: `PENDING`

Before replacing `PENDING`:

- [ ] estimated map-frame defects exist;
- [ ] explicit GT defects exist;
- [ ] explicit correspondence exists;
- [ ] evaluation-only `T_map_from_world` exists;
- [ ] provenance/hash evidence exists;
- [ ] canonical P19 evaluator produces the result.

## M. Integrated-demo claim

- [x] accepted P18 core-system integration and repeatability evidence exists.
- [ ] full autonomous inspection language authorized by 00.

Until both are checked:

**Do not claim full autonomous inspection validation.**

## N. Final presentation check

Immediately before presentation:

- [ ] verify final canonical presentation SHA after late-evidence ingestion;
- [x] verify no P20 claim was silently upgraded;
- [x] verify quantitative slides match `results_table.json`;
- [x] verify detector and low-light limitations are visible;
- [x] verify the accepted dashboard record remains `UNREVIEWED`;
- [x] verify localization is `MEASURED` and P19 3D correspondence is `FROZEN PENDING`;
- [x] verify LL-DETECTOR is `PENDING` unless accepted results arrive;
- [ ] final-freeze only after ARMOURY disposition from 00; MSI is resolved;
- [x] keep the compact evidence index available for Q&A.
