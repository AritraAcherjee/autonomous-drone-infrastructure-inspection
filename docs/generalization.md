# Generalization evaluation infrastructure

This is pre-freeze infrastructure. No detector inference, scientific evaluation,
holdout acquisition, robustness experiment, or checkpoint selection was performed.
The Chat 02 checkpoint and operating settings remain unknown. Draft configuration
values are intentionally null. Configuration files use JSON-form YAML, matching
the approved data configuration convention; the scripts use the standard JSON reader.

## Commands

From the repository with Python 3.11+:

```powershell
python scripts/prepare_generalization.py --experiment-id chat03-prefreeze
python scripts/verify_generalization_infrastructure.py
```

Preparation accepts no dataset/checkpoint input. It writes a draft manifest,
configuration snapshots and header-only CSV interfaces below
`outputs/validation/defect_detection/generalization/<experiment-id>/`.
It does not produce scientific results. Use a new ID for later scientific work.

Future post-freeze command template (not executed on scientific data):

```powershell
python scripts/evaluate_generalization.py --manifest <frozen-experiment.json> --predictions <normalized-export.json> --ontology <approved-crosswalk.yaml> --protocol <frozen-protocol.yaml>
```

The integrated base has no detector inference adapter or `configs/detection/`
files. This scorer consumes a future adapter's normalized export. It does not
construct a detector, open image files, perform NMS, or download weights. An
adapter and separate authorization to access holdouts remain prerequisites for
scientific use. It must export all detections surviving frozen NMS/max-detection
settings at the AP floor, never just detections above the operating threshold.
Neither thresholds nor checkpoints are selected by these commands.

## Frozen provenance contract

`schema.validate_manifest(..., scientific=True)` fails closed for incomplete,
unfrozen, malformed, or inconsistent provenance. Required fields:

- `schema_version: 1`, safe `experiment_id`, `phase: frozen`, `frozen: true`,
  `freeze_approval` review reference.
- `architecture`, `architecture_version`, absolute `checkpoint_path`,
  lowercase 64-character `checkpoint_sha256`, 40-character `training_git_sha`
  and `evaluation_git_sha`.
- Nonempty inline `training_config`, `resolved_inference_config`, and
  `validation_evidence`; exact six-class `class_mapping` keyed by strings.
- `dataset: {identity, version, split, sha256}`. SHA binds canonical normalized
  `{images, regions}` content including empty-image identities. For GYU require
  identity `GYU-DET`, version `v3/baseline-v1`, split `test`, and
  `source_manifest_sha256` equal to the approved test manifest hash in VERSION.json.
  The future adapter must prove inventory membership and retain original
  image/annotation source hashes; this scorer cannot attest an adapter's truthfulness.
- `ontology_version`, canonical `ontology_sha256`, canonical `protocol_sha256`.
- `image_size: [height, width]`, `ap_confidence_floor`, `operating_confidence`,
  `matching_iou`, `ap_ious` (`[0.5]` or 0.50 through 0.95 at 0.05 intervals),
  `nms_iou`, `nms_mode` (`class_aware`, `class_agnostic`, `none`),
  positive `max_detections`, nonnegative integer `seed`.
- `environment: {python, platform, packages: {name: version}}`.
- For CODEBRIM, `external_review` with `taxonomy_approved: true`,
  `leakage_audit_passed: true`, and a nonempty `evidence` reference.

Resolved inference config repeats and agrees with image size, both confidence
settings, NMS settings, maximum detections and seed. Freeze the protocol status
and settings as well, version it, review the ontology before exposure, then
compute canonical hashes with `manifest.object_hash` (sorted compact JSON, UTF-8,
no NaN). A separate, complete manifest is required per domain/experiment.

The execution gate checks metadata, ontology/protocol bindings, the running Git
SHA and source cleanliness before reading the checkpoint for SHA verification.
Only after that does it reserve an output directory and read the normalized
scoring export. Frozen fields are declarations by the approving workstream, not
cryptographic proof of a human review. Missing evidence is never synthesized.

## Export interface

```json
{
  "manifest_sha256": "canonical hash of full frozen experiment manifest",
  "dataset": {"identity": "...", "version": "...", "split": "...", "sha256": "..."},
  "inference_config": {"...": "exact resolved inference config"},
  "images": ["synthetic-image", "synthetic-empty-image"],
  "regions": [{"id": "r1", "image_id": "synthetic-image", "box": [0, 0, 10, 10], "labels": [0, 1]}],
  "predictions": [{"id": "p1", "image_id": "synthetic-image", "box": [0, 0, 10, 10], "class_id": 0, "confidence": 0.9}]
}
```

Boxes are finite, nonnegative pixel xyxy coordinates in the same original-image
frame, with positive area. IDs must be unique within predictions/regions. The
image inventory is mandatory and includes empty images. For external regions,
`taxonomy.map_region_labels` returns approved IDs plus excluded external labels.
Retain excluded-label/region counts in the future adapter's evidence. Regions
without any approved labels are omitted from scoring regions while their images
remain in the inventory. Predictions of approved classes on those images count
as FP when unmatched. Unknown external labels fail, never silently become GYU.

CODEBRIM mappings start as **candidate**, including Breakage/Spallation. Nothing
is approved by default. Approval requires a versioned crosswalk and a review
reference on each approved row. Honeycombing, Hole and Seepage are unmapped;
Efflorescence and Corrosion/stain remain external-only. A multi-label region is
stored once with multiple labels. Each class independently matches its positive
regions; one region can be a TP for different classes. No duplicated-box global
single-label scoring is performed.

## Metric definitions and limits

Matching is greedy per class in descending confidence order; ties sort by image
ID then prediction ID. Each prediction matches the highest-IoU unused same-class
region in its image if IoU is at least the declared matching threshold. Region-ID
ordering breaks IoU ties. Matching is repeated independently for every AP IoU.
Duplicates, wrong classes, and failed localization are unmatched predictions;
they do not automatically receive a reviewed causal failure tag.

AP is the mean interpolated precision over 101 recall points from 0 to 1, using
the maximum precision at or above each recall point. This is a documented box-AP
implementation, not a claim of complete COCO API parity: no crowd/ignore flags,
area ranges or COCO maxDet sweeps are supported. AP for a class with no positive
regions is null and excluded from mAP; the denominator and scored classes are
exported. No predictions with positive GT gives AP=0. AP50:95 is null if only
IoU=0.5 is declared. Shared mAP averages defined AP only among approved classes.
Compare domains over the same declared class set for scientific transfer claims.

Operating TP/FP/FN use the frozen operating confidence and matching IoU.
Precision=TP/(TP+FP), recall=TP/(TP+FN), F1=2PR/(P+R), with zero for undefined
operating ratios. Aggregate counts are micro totals over scoring classes.
FP/image and FN/image divide by the full image inventory, including empty images.

Confidence exports and calibration use detections at the AP floor, matched at
the frozen matching IoU. Reliability bins are left-closed/right-open, except
the final bin includes 1. Confidence-vs-correctness accuracy is the matched
fraction per bin. Detection ECE=sum(n_bin/N * abs(mean_confidence-accuracy)).
Empty bins and an empty overall ECE are null. This is conditional on exported
detections, includes duplicate FPs, excludes FNs, and is not image-level or
joint detection calibration. TP/FP distributions retain individual confidences.
Reports provide per-class ECE; `reliability` also supports pooled analysis.

Failure records support all 21 requested categories, multiple reviewed tags,
image/object ID, reviewer and notes. Counts are tag counts, not mutually
exclusive object totals. Failure CSVs remain header-only until reviewed; the
category JSON is explicitly a schema template, not measured zero failures.

## Outputs and reproducibility

CSV interfaces: domain comparison, per-class transfer, FP/FN counts, confidence
summary, failure-category counts, individual confidence predictions, reliability
bins, and failure review. Each run contains one domain; combine separate reports
only with matched protocol/ontology settings. JSON retains per-IoU AP and missed
region IDs. The manifest binds the run; input evidence hashes the normalized
export. `COMPLETE` appears only after successful reporting; failures retain an
`INCOMPLETE` reservation. Existing experiment IDs cannot be reused, even with a
changed manifest. Stable run names use ID plus the first 16 canonical hash digits.

Robustness settings predeclare lighting, blur, JPEG and resolution severities.
Perspective is disabled pending reviewed geometry rules. No transforms are
executed here. Future execution must freeze implementation versions, coordinate
handling and transform order, use a fresh experiment identity, and avoid tuning
on holdout results.

Module layout follows the request, adding `reporting.py` for CSV interfaces and
`verify_generalization_infrastructure.py` for isolated test/audit evidence.
No existing training, split or M1 artifact is modified.

## Tests

The audit runner executes `tests/detection` and the existing metadata-only
`tests/data/test_gyu_m1_documentation.py`. It blocks real repository `data/raw`
opens, network connections and detector-runtime imports; temporary synthetic
fixtures remain allowed. It writes test logs, JUnit and repository-read audit
under a separate `generalization_infrastructure` evidence directory. No
pretraining reader command or full raw-data validation is run.

Core code uses Python standard library. Plot tests additionally use matplotlib;
existing regression tests require numpy, Pillow and PyYAML. The retained package
lock records the isolated test environment, not Chat 02's detector environment.
