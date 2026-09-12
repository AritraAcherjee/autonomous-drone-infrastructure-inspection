# CODEBRIM protected external holdout policy

Decision date: 2026-09-11. Selected source: [original Zenodo record, version 1.0](https://zenodo.org/records/2620293); [dataset terms](https://zenodo.org/records/2620293/files/license.md?download=1).

CODEBRIM is the selected external structural-defect generalization benchmark, subject to its non-commercial research/education terms. Acquisition is deferred to Chat 03 external evaluation after the detector baseline is frozen. This selection is not a claim that external evaluation has already been run or its payload validated.

- CODEBRIM must not be included in GYU-DET baseline training, preprocessing-statistic fitting, validation, early stopping or model selection.
- Do not use CODEBRIM images, labels, predictions or scores to tune baseline hyperparameters before the baseline is frozen. Freeze the trained model, checkpoint hash, preprocessing, thresholds and evaluation protocol before external evaluation; freezing a dataset manifest alone is insufficient.
- Preserve CODEBRIM for external/domain-shift evaluation. Record source version, checksums, accepted terms and any required institutional permission when acquired; retain a separate namespace and manifest, never append it to GYU-DET lists.
- Define and review the taxonomy crosswalk and metric before examining model outputs. Crack and exposed-bar concepts overlap; spallation versus Breakage needs explicit agreement. Efflorescence/corrosion cannot silently become Seepage; Comb/Hole have no established equivalents. Multi-label crop targets are not equivalent to single-class detector targets. Report only justified mapped classes, excluded classes and annotation limitations.
- Prefer original full-resolution images and box annotations for a detection evaluation; classification crops are a separate benchmark task. Do not treat duplicated balanced training crops as independent test images.
- Run an overlap/leakage audit against GYU-DET before claiming independent generalization. Any discovered overlap must be disclosed and excluded from the external score without changing the approved GYU baseline.
- Any future fine-tuning experiment using CODEBRIM must be explicitly separated from the initial external-generalization result, with a new experiment identity and independent held-out evaluation. Once exposed to tuning, that data cannot support a fresh untouched-holdout claim.
- Dataset and modified-dataset redistribution are prohibited by the custom terms; public deliverables should contain provenance, protocols and permitted aggregate results, not images or data-bearing derivatives.

Technical justification: the [original paper](https://arxiv.org/html/1904.08486v1) documents concrete bridge defects, contextual images and multi-target regions. This makes a useful domain-shift test, but not a six-class drop-in replacement for GYU-DET. No baseline training change is authorized.
