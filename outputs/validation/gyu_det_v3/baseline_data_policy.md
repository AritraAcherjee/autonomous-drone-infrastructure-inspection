# GYU-DET V3 provisional baseline eligibility policy

This policy is for analysis only. It does not approve final splits, a processed
training export, or training. M1 remains incomplete.

- The 10,411 exact image-label pairs are candidate baseline supervised samples,
  subject to leakage review and an eventual approved training-reader policy.
- All 21 orphan annotations are excluded from baseline eligibility until mappings
  are explicitly confirmed. Tentative human preferences are not repairs.
- All 712 images without labels remain UNCLASSIFIED, not negative. The published
  691 negatives must not be inferred by subtraction.
- Auxiliary MPO-frame failures are warning-only under this provisional policy
  because all primary images decoded in the full Pillow validation. They become
  a reader-compatibility concern if the eventual training reader cannot read the
  primary image. No MPO image is modified or excluded by this audit.
- Derived boundary overshoots <=1e-6 normalized units are rounding warnings;
  raw labels are not clipped, rewritten, or corrected.
- This policy does not overwrite the earlier strict full-validation flags.
- Raw files, official split membership, all 21 human decisions, and repair
  authorization remain unchanged. No final training data has been approved.

## Approved human leakage-handling policy for future processed splits

Human review of all 17 cross-split candidates is complete. The review decisions
are authorized for use in future processed split construction; this does not
authorize modifying raw data or generating the processed dataset now.

- Exact cross-split duplicate groups must not span processed train/validation/test.
  Keep one representative or keep all retained group members in the same split.
- High-confidence near-duplicate/same-scene groups must remain within one
  processed split, or retain one representative.
- Unresolved possible-same-scene groups should be conservatively grouped in one
  split unless stronger evidence later disproves the relationship. These are
  not confirmed leakage findings.
- Rejected perceptual candidates require no special grouping solely from this
  audit. They do not impose a must-be-separated constraint.
- Raw official splits remain unchanged. Processed splits will be generated
  separately and reproducibly after explicit approval.

Specific groups:

1. Exact: train/9838.jpg with valid/11989.jpg.
2. High-confidence: train/11727.jpg with valid/11985.jpg.
3. Conservative unresolved: train/11334.jpg with test/12582.jpg.

See leakage_review/human_leakage_decisions.csv and
leakage_review/final_leakage_review.md for all 17 decisions and their reasons.
All have review_authorized=true, which is a leakage-review authorization only.
It does not change any orphan repair authorization. Unlabeled samples remain
UNCLASSIFIED; grouping does not transfer annotations or identify negatives.
No processed dataset or final split assignment has been created. M1 remains incomplete.
