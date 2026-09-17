# DamSegment v1 external-generalization pre-access package

Experiment: `GEN-DAMSEGMENT-ZS-001`

Dataset: DamSegment v1, Damage Detection subset.

DOI: `10.17632/z5z6gtt5t4.1`

License: CC BY 4.0.

The authoritative downloaded outer archive SHA-256 is
`f195ba0730f12a68e6e7b1d685b555fe2872b870a0686ffa3a5c397200fd63e6`.

The extracted Damage Detection sub-archive SHA-256 is
`2423567183c584568efd45a2f4521c5d5f3f65106f2d2ff1311ed99b7adba1a9`.

The detection payload contains 1,500 640x640 JPG images, 1,500 YOLO
annotation files, and 1,500 Pascal-VOC-style JSON annotation files.
YOLO and JSON annotations agree on 19,710 total regions.

Payload review established:

- source class ID 0 = Crack
- source class ID 1 = Spalling
- DamSegment Crack -> Aegis Crack
- DamSegment Spalling -> Aegis Breakage

The semantic class-ID binding is based on authoritative two-class dataset
semantics, exact YOLO/JSON numeric agreement, and payload-level human visual
review. The source archive does not provide a separate class-name table.

The approved quantitative shared-class scope is therefore Aegis classes
`[0, 1]` only. Honeycombing, Hole, Exposed Reinforcement, and Seepage are
excluded from the DamSegment aggregate. The aggregate must be reported as
`shared-class DamSegment mAP`, never as six-class GYU mAP.

The Task63B-R2 leakage audit compared all 1,500 DamSegment images against
all 10,398 approved GYU baseline-v1 image identities. Exact comparison used
SHA-256 for train/valid/test. The locked GYU test was represented only by its
approved non-raw manifest hashes. Perceptual comparison used the existing
AegisInspect difference hash with Hamming review radius <= 8 and Git-bound
historical GYU fingerprints.

Result:

- exact SHA overlap: 0
- perceptual near-duplicate candidates: 0
- leakage gate: PASS_NO_CANDIDATES
- locked GYU raw test accessed: false

DET-FINAL-v1 remains frozen at checkpoint SHA-256
`4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3`.

This pre-access package does not authorize or perform detector inference,
scientific AP/mAP calculation, threshold selection, model selection,
augmentation selection, DET-IMPROVED execution, or a GYU held-out rerun.

`dataset.sha256` is bound to the approved deterministic normalized
image/region inventory SHA-256
`a75a29496ba8bb76f49db5a36b64a9920911b5e4c420f634a4390deb418e14df`.
This prepared-data binding does not authorize scientific execution.
Scientific execution requires a separate 00 Control Center authorization and
a clean committed evaluation tree.


## Prepared normalized inventory

The deterministic prepared 03 `images + regions` object contains:

- 1,500 image identities;
- 19,710 GT regions;
- Aegis class 0 Crack: 19,229 regions;
- Aegis class 1 Breakage from source Spalling: 481 regions;
- three images with zero GT regions.

Canonical normalized inventory SHA-256:

`a75a29496ba8bb76f49db5a36b64a9920911b5e4c420f634a4390deb418e14df`

Exact canonical JSON artifact file SHA-256:

`dabc0bb394127d7dc5d90b8441bdb64f91e7b6606c07994e300b4a6aeb124f70`

The tracked deterministic builder is
`scripts/prepare_damsegment_generalization.py`.

The external benchmark is not used for training, threshold tuning,
augmentation selection, or model selection, and it is not a replacement
for the locked GYU held-out test.

## Scientific execution preparation transition

On 2026-09-17, 00 Control Center authorized transition from the historical
pre-access state to a committed **portable scientific contract**. Git history
retains the original pre-access state.

The committed portable contract is frozen and authorized but deliberately
omits runtime-only bindings. It keeps `heldout_evaluation_count = 0`.

After the scientific-preparation commit is created and pushed, the committed
`derive_damsegment_runtime_manifest.py` path derives a separate runtime
manifest that binds the exact clean current Git HEAD and verified absolute
DET-FINAL-v1 checkpoint locator. The runtime manifest is generated under the
ignored scientific runtime-output tree and is not a tracked source mutation.

Only the derived runtime manifest may be supplied to `frozen_gate()` and the
scientific scorer. The strict `evaluation_git_sha == git rev-parse HEAD`
requirement remains unchanged.

The committed `run_damsegment_inference.py` bridge owns only frozen model
inference plus normalized prediction export. Scientific AP/mAP remains owned
by `scripts/evaluate_generalization.py`.

This preparation does not itself execute DET-FINAL-v1 on DamSegment and does
not consume the external benchmark.

### Frozen inference-setting runtime bindings

Ultralytics 8.4.145 does not expose every historical frozen field as a
`predict()` keyword, so the committed runner makes those semantics explicit:

- `workers = 0`: images are decoded serially by the runner in the main process;
- `batch = 8`: the runner forms explicit deterministic batches of eight;
- `shuffle = false`: batches follow the frozen prepared-inventory order;
- `drop_last = false`: the final partial batch is always executed;
- `cache = false`: only the current batch is retained;
- `pad = 0.5`: source images are required to be exactly 640x640, so at
  `imgsz = 640` no letterbox pixels are required and the padding value is
  operationally inert;
- `FP16 = true`: Ultralytics 8.4.145 maps the legacy half-precision control to
  `quantize = 16`, which configures `AutoBackend(fp16=True)`;
- `end2end = true`: `nms = false` is passed explicitly and the loaded YOLO26
  head is independently required to report `end2end=True`.

These are bindings of the already-frozen scientific protocol, not new tuning
parameters.
