# CODEBRIM pre-access freeze

GEN-CODEBRIM-ZS-001 freezes configuration for DET-FINAL-v1 before CODEBRIM
acquisition. This task authorizes no scientific execution. The model is YOLO26s,
Ultralytics 8.4.145, best epoch 62. GYU held-out evaluation is already complete
with count 1; a rerun is not authorized.

The authoritative task provenance is recorded separately as training Git SHA,
freeze commit SHA and evaluation main SHA in
`configs/generalization/experiments/GEN-CODEBRIM-ZS-001.json`. The 02 frozen model
configuration and checkpoint remain unchanged. Exact file-byte hashes and the
existing 03 canonical-object hashes are both recorded with explicit names.
`source_hashes.json` binds the uncommitted evaluation implementation; it does not
claim that these changes belong to the base commit. No commit is authorized here.

## Frozen protocol and ontology

Use `configs/generalization/generalization_protocol.yaml` and the existing
`configs/generalization/ontology_crosswalk.yaml`. Approved shared classes are
Crack / Crack, Breakage / Spallation, and Exposed Reinforcement / ExposedBars.
Honeycombing, Hole and Seepage are excluded; Efflorescence and CorrosionStain
are external-only. Seepage -> Efflorescence is prohibited by validation.
The aggregate label is **shared-class CODEBRIM mAP**, not equivalent to six-class
GYU mAP. Multilabel regions remain single regions with multiple approved labels.

Frozen inference is imgsz=640, batch=8, CUDA:0, workers=0, rect=true, pad=0.5,
FP16=true, conf=0.001, iou=0.7, max_det=300, nms=false, augment=false,
agnostic_nms=false, single_cls=false, cache=false, compile=false, shuffle=false,
drop_last=false, end2end=true. FP16 corresponds to the recorded 02 quantize=16
runtime; do not infer evaluator precision from the training BF16 setting.

The confidence collection floor (0.001), fixed validation diagnostic confidence
(0.18618618618618618), evaluator IoU argument (0.7), AP IoUs (0.50:0.05:0.95),
P/R/F1 matching IoU (>=0.50), and confusion matching condition (IoU >0.45) have
separate meanings. Conventional NMS is bypassed for this end-to-end head.
The legacy `nms_iou` field stores the evaluator argument, with `nms_mode=none`.

The existing 03 class-wise greedy/101-point AP evaluator remains in place.
Its integer-count P/R/F1 diagnostics are not 02 interpolated-curve metrics.
Absent-GT classes have null AP and are omitted from the mean; report the scored
classes and number with GT. The frozen 02 confusion rule is recorded as a
reference; this task does not implement a new confusion-matrix evaluator.

## Serialization adapter

`src/detection/generalization/prediction_export.py` takes an iterable of
`(source_relative_identity, result)` pairs. Each already-produced result exposes
`orig_shape=(height,width)`, the exact six-class `names` mapping, and `boxes.xyxy`,
`boxes.cls`, `boxes.conf` as lists or tensor-like arrays. Coordinates must already
be in the original image frame, following 02's `scale_boxes` export convention.
The adapter does not call 02's validator: that runner performs validation and
metric computation, while its dataset is deliberately limited to development
records. No new loader, detector runner or evaluator is created.

`normalize_predictions` returns images (including empty images), image metadata,
normalized predictions, manifest/config hashes and checkpoint/model provenance.
It rejects malformed geometry, classes, confidence values and unsafe identities.
It sorts by identity, class, descending confidence and box coordinates, then
assigns stable IDs. It preserves duplicate boxes, all six predicted classes and
confidence values. Ontology filtering belongs to the existing approved layer.
`serialize_predictions(fragment, manifest)` returns deterministic JSON bytes;
the caller owns the authorized writer. `assemble_bundle` accepts separately
approved, already normalized regions and validates the existing evaluator's
bundle contract, including dataset hash. It performs no ontology remapping or
metric computation. It never opens `result.path`, `orig_img` or benchmark files.

Serialization verifies metadata claims; it cannot prove how a future caller ran
inference. A future separately authorized inference integration must preserve
02 preprocessing/batching/FP16 and supply original-coordinate results. A generic
standalone `YOLO.predict` call is not asserted to reproduce the frozen validator.

## Runtime and verification

Use only `outputs/cache/generalization/venv/Scripts/python.exe` (Python 3.12.14).
`requirements/generalization-inference.txt` reuses the detector's exact runtime
pins and recorded 02 transitive dependencies. Existing contourpy 1.4.0 and pip
25.0.1 remain unchanged. NumPy is changed from the earlier test-only environment's
2.5.3 to the detector's frozen 2.4.6. `generalization-test.txt` describes the
historical test-only environment and should not override this inference profile.
No venv was recreated. A Windows path-length failure was resolved using the
verified short-path alias of the same interpreter; no package version changed
to work around it. `environment.json` records every added/changed version.

Run `scripts/verify_codebrim_preaccess.py` with the dedicated interpreter.
It checks versions/CUDA/pip consistency, blocks network and repository raw or
held-out payload reads, and runs synthetic/metadata tests. No model is loaded.
Evidence lives under
`outputs/validation/defect_detection/generalization_infrastructure/codebrim_preaccess/`.
The tests cover provenance, checkpoint binding, all frozen settings and threshold
distinctions, ontology exclusions, exact aggregate labeling, deterministic
serialization, malformed input rejection, no adapter metric/payload operations,
acquisition flags, experiment overwrite protection and runtime provenance.

## Acquisition remains unexecuted

The canonical payload destination is `data/raw/codebrim/`, under the existing
`/data/raw/` ignore rule and existing detector isolation-test namespace.
`git check-ignore -v -- data/raw/codebrim/NOT_ACQUIRED.zip` matches that rule.
No directory or payload was created. The prepared manifest is
`data/manifests/codebrim_acquisition.json`; it uses only the local approved
registry and source/terms documentation for Zenodo record 2620293, version 1.0.
The local metadata does not specify an archive filename or checksum; those remain
null. Local checksum and download/extraction timestamps also remain null.
All accessed/downloaded/extracted/inference flags remain false.

Acquisition still requires separate Control Center authorization, exact archive
and checksum confirmation, and the recorded terms/permission requirements.
Later scoring additionally requires a real dataset identity/hash, leakage audit,
approved normalization, and a clean committed evaluation tree. The current
manifest deliberately stays `phase=pre_freeze, frozen=false` with
`preaccess_config_frozen=true`; the existing scientific gate rejects it.
`reserve` atomically refuses reuse of GEN-CODEBRIM-ZS-001 even if its manifest
changes. This task does not reserve or populate a scientific result directory.

No CODEBRIM-driven tuning, model selection, confidence/IoU/NMS optimization,
augmentation selection, checkpoint changes, training, fine-tuning, DET-IMPROVED
execution or GYU held-out rerun is authorized. Stop A remains NOT COMPLETE.

## Verified task result

Final verification: 212 tests and 133 subtests passed; four payload-dependent checks deselected. The initial run preserved 212 passes and two failures: one prevented held-out manifest read and one absent local GYU raw directory. No substitute data directories were created. New pre-access tests: 57; existing 03 tests: 30; detector regressions: 75; analysis regressions: 15; Stop A framework: 24; safe registry metadata: 11.

Ontology file SHA-256: `0e575df2e3f1488414b8b501e14ac1c8e85454b2396de592d68918e14d06ca04`.

Protocol file SHA-256: `5705e5d8e5bbbb5273d81d87e97cb787ffe4d28601a88df5274786e044bc8e3d`.

Python 3.12.14, Ultralytics 8.4.145, PyTorch 2.14.0+cu130, CUDA available, pip check PASS. Git whitespace and protected-path checks PASS. CODEBRIM pre-access gate READY; acquisition still unauthorized. No inference, training, scientific payload access, commit, push, PR or merge occurred.
