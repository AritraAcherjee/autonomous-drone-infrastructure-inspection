# Chat 19 Stop-A evaluation framework

Current status: **STOP A = NOT COMPLETE**, `PREPARED_NOT_FROZEN`.
Chat 19 owns consolidation, registry/index contracts, plotting interfaces,
failure analysis, reproducibility packaging and Stop-A evidence packaging.
Chat 02 owns training, checkpoint selection/freeze and detector predictive
metrics. Chat 03 owns external authorization, methodology and class mappings.
Chat 20 owns final presentation deliverables. This release prepares interfaces
only and cannot finalize Stop A, even if callers edit all completion flags.

## Preparation and storage

With Python 3.11+ from the repository root:

```powershell
python scripts/prepare_stop_a.py
python -m unittest discover -s tests/evaluation -v
```

Initialization creates the requested `outputs/final_evaluation/stop_a` tree,
four empty JSON registries and four empty presentation templates. Repeated
calls preserve existing files, including failed experiments and raw evidence.
An existing protocol snapshot is deliberately not overwritten; use a new
output root for a revised protocol. No datasets, images or checkpoints are
opened by initialization. There are no runners, downloaders or network calls.
The existing `.gitignore` ignores `outputs/cache/`, not all outputs. This task
does not alter that policy or force-add generated files. Tests use disposable
temporary roots; generated scientific outputs must be reviewed separately.

The protocol uses JSON-form YAML, consistent with existing repository configs.
Verified GYU-DET counts: train 8,305; validation 1,040; test 1,053; supervised
images 10,398; annotations 48,392; classes 6. The held-out identity is
`GYU-DET`, `v3/baseline-v1`, `test`, with manifest
`data/processed/gyu_det_v3_baseline_v1/splits/test.txt`. Its hash remains null
until provided and verified by the owning workstream. Detector checkpoint,
Git SHA, seed and configuration remain null/PENDING. External authorization
is false and its status is BLOCKED_PENDING_CHAT03.

## Machine-readable contracts

`src/evaluation/framework.py:FIELDS` is the canonical field list. Initialized
`manifests/{experiment,evidence,metric,failure}.json` contains those exact
fields and an empty `records` array. Every record must contain every field;
unknown fields are rejected. Use JSON null for missing values. `synthetic`
is a required boolean on experiment/evidence records; `accepted` is a boolean.
An upstream adapter must explicitly normalize records and invoke validators;
writing a JSON file alone does not accept evidence.

Experiment statuses: PLANNED, BLOCKED, PENDING_INPUT, READY, RUNNING, COMPLETE,
ACCEPTED, REJECTED. Evidence acceptance statuses: PENDING, INCOMPLETE,
ACCEPTED, REJECTED. Metrics use the same acceptance statuses; an incomplete
numeric measurement is never a completed result. Workstreams are `Chat02`,
`Chat03`, `Chat19`. Each experiment describes exactly one evidence class;
separate runtime experiments from predictive ML experiments.

Evidence classes are exclusively SW (software/unit/integration), ML
(predictive performance), GEO (geometric accuracy), SIM (simulation/runtime).
196 ROS tests passed would be SW evidence only. It cannot populate mAP,
precision, recall, F1 or detection counts. Projection/depth validation is GEO;
latency/FPS are SIM. Neither proves detector accuracy. The metric taxonomy
is an explicit allowlist; extending it requires a reviewed code change.

`validate_experiment`, `validate_evidence`, `validate_metric` and
`validate_failure` raise ValueError for invalid records. Accepted evidence
requires complete matching experiment provenance, full Git SHA, applicable
checkpoint SHA-256, a reviewer note, preserved raw results, config and
environment files, command reference, timestamp and machine. Artifact paths
must resolve inside the caller's evidence root, including symlink resolution.
Artifact bytes must match the recorded SHA-256. Model files are not evidence
inputs and are rejected. Hash validation attests bytes, not scientific truth.

Accepted metric exports are JSON objects with a `metrics` array containing
the exact normalized metric records, including source_artifact. Values are
consumed, never calculated. An accepted record must occur in its hash-verified
source. Missing values remain null; bool, NaN, infinity and strings such as
N/A are not numeric values. Human-readable N/A may describe non-applicability
in notes only. `presentation_rows` revalidates sources, suppresses incomplete
values to null and rejects synthetic evidence. Failed/rejected records stay
in the registry and must be reported, never silently removed.

## Final-test integrity and external gate

No final-test tuning, estimated metrics, checkpoint selection or inference
is implemented. Accepted ML evidence requires a reviewed FROZEN protocol,
Chat 02 pretraining PASS, frozen checkpoint metadata and matching hash.
Chat 02 predictive records must identify the held-out test split. Chat 03
records cannot become READY/RUNNING/COMPLETE/ACCEPTED without explicit true
authorization plus its reference, benchmark/version/subset, mapping version,
matching Chat 02 checkpoint hash and confirmation that external results were
not used for tuning. Missing external evidence cannot produce an accepted
metric or completed comparison. This library does not execute external work.

## Input contracts

Chat 02 must supply pretraining-gate PASS evidence; frozen detector checkpoint
filename/version and SHA-256; Git SHA; seed; training config; detector/evaluation
config; environment/package record; held-out GYU-DET evaluation; mAP@0.5;
mAP@0.5:0.95 where produced; precision; recall; F1; per-class AP; confusion
matrix; PR data; training/validation curves; inference latency/FPS; preferably
raw per-image predictions. Chat 19 does not produce these artifacts.

Chat 03 must supply benchmark identity/version and provenance; exact subset;
class-mapping document/version; explicit authorization; frozen checkpoint hash
and confirmation it matches Chat 02; Git SHA; evaluation config and command;
external predictive metrics; compatible per-class metrics where valid; raw
predictions; logs; comparison; limitations; and explicit confirmation external
results were not used for tuning. A methodologically invalid comparison needs
an owner-reviewed non-applicability explanation, not invented metrics.

## Failure analysis and plotting

Failure outcomes: TP, FP, FN, CLASS_CONFUSION, LOW_CONFIDENCE_TP. Difficulty tags:
LOW_LIGHT, SMALL_DEFECT, OCCLUSION, TEXTURE, BACKGROUND_CONFUSION, EDGE_OF_FRAME,
MULTIPLE_DEFECTS, LOW_CONTRAST, AMBIGUOUS_LABEL, OTHER. Confidence and IoU may be
null. `hypothesized_cause` is a hypothesis, not a causal conclusion. Preserve
supporting evidence and analysis confidence; causality needs experimental
support. Presentation candidates need an image and supporting evidence.

`plots.plot_spec` is a renderer-neutral interface, not a scoring function.
It consumes an accepted, hash-verified JSON artifact with `kind`,
`synthetic: false`, and `data`. Supported kinds and payloads:

- `confusion_matrix`: labels and square matrix of nonnegative integer counts.
- `pr_curves`: series with label, x recall and y precision in [0,1].
- `training_validation_curves`: labelled series with equal-length x/y arrays.
- `domain_comparison`: series additionally identify in_domain/external domains;
  the Chat 03 gate applies. The owner must establish metric compatibility.
- `example_panel`: cases with TP/FP/FN outcome, image_path and evidence_id.
- `runtime`: labelled x/y series plus unit ms, s or FPS.

Interfaces return RENDER_INPUT_ONLY with source hashes. A later renderer must
index its output and preserve review provenance. There are no hard-coded
results, rendered sample figures or synthetic production outputs. Synthetic
fixtures exist only inside isolated unit tests and cannot be accepted.

## Definition of Done and Monday targets

Stop A requires M1 complete; pretraining gate PASS; trained baseline; frozen
checkpoint; checkpoint provenance; held-out test evaluation; external evaluation
where methodologically valid; completed failure analysis; consolidated metrics;
reproducibility evidence; and presentation-ready evidence. Only M1 is currently
complete. `stop_a_status` reports the pending requirements and always returns
NOT COMPLETE in this preparation release. A future reviewed finalization change
must verify the full package rather than trusting completion flags.

Monday's eventual package comprises one headline detector table, one confusion
matrix, one PR/metric visualization, one in-domain/external comparison, one
TP/FP/FN panel, one limitations/failure summary and one compact reproducibility/
evidence record. Templates are empty and pending. No final deck is redesigned.
Record workstream, experiment ID, Git SHA, dataset/version/split, checkpoint ID
and hash where applicable, config/version, command, seed where applicable,
timestamp, machine/environment, metric source, artifact path and status.
