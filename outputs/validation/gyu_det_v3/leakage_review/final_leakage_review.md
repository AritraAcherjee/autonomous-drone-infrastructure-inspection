# Final human leakage review: GYU-DET V3

All 17 cross-split candidates now have the user's human-review decisions.
Audit evidence and severities are preserved separately from human outcomes.

| Human outcome | Pairs |
|---|---:|
| CONFIRMED_EXACT_CROSS_SPLIT_LEAKAGE | 1 |
| HIGH_CONFIDENCE_NEAR_DUPLICATE_LEAKAGE | 1 |
| UNRESOLVED_POSSIBLE_SAME_SCENE | 1 |
| REJECT_LEAKAGE_CANDIDATE | 14 |

## Approved future processed-split constraints

| Group | Images | Handling |
|---|---|---|
| Exact-content group | train/9838.jpg; valid/11989.jpg | Must not span processed evaluation splits; group together or retain one representative |
| High-confidence same-scene group | train/11727.jpg; valid/11985.jpg | Same processed split or one representative |
| Conservative unresolved group | train/11334.jpg; test/12582.jpg | Group together unless stronger evidence disproves the relationship; not confirmed leakage |

These are three disjoint pairs containing six distinct images. No processed
split membership or representative has been selected, and no file has been removed.
The 14 rejected hypotheses require no grouping solely on this audit's evidence;
rejection does not require those images to be assigned different splits.

review_authorized=true means these human leakage-review decisions may inform
future processed split construction. It does not authorize raw modifications,
orphan repairs, deletion of raw duplicates, or immediate processed-data generation.
In particular, valid/11985.jpg remains unlabeled and UNCLASSIFIED; a same-scene
grouping does not transfer annotations or establish negative-image identity.
All previous orphan-review decisions and repair_authorized=false flags are intact.

## All pair decisions

| Image A | Image B | SHA equal | Hamming | Audit severity | Human outcome | Human notes | Processed-split action | Review authorized |
|---|---|---|---:|---|---|---|---|---|
| train/9838.jpg | valid/11989.jpg | true | 0 | exact_content_cross_split | CONFIRMED_EXACT_CROSS_SPLIT_LEAKAGE | SHA-256 equality establishes identical image content, and visual review confirms the images are identical. | Must not span processed model-evaluation splits. Keep one representative or group both into the same processed split during future processed split construction. | true |
| train/11727.jpg | valid/11985.jpg | false | 3 | very_strong_near_duplicate | HIGH_CONFIDENCE_NEAR_DUPLICATE_LEAKAGE | Very low perceptual distance, same dimensions, and visual review show highly similar framing, surface geometry, crack pattern, and capture appearance. Treat as the same-scene/same-capture family for leakage prevention. | Keep both in the same processed split or retain only one representative during future processed split construction. | true |
| train/11334.jpg | test/12582.jpg | false | 7 | probable_near_duplicate | UNRESOLVED_POSSIBLE_SAME_SCENE | Both are low-information concrete surfaces with notable visual similarity and similar capture appearance, but the available evidence is insufficient to confirm the same exact scene. | Conservatively group in one processed split unless stronger evidence later disproves the relationship. Do not call this confirmed leakage. | true |
| train/11727.jpg | test/12684.jpg | false | 9 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/9510.jpg | test/12684.jpg | false | 9 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/11441.jpg | test/12653.jpg | false | 10 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/10050.jpg | test/12463.jpg | false | 11 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/11888.jpg | test/12582.jpg | false | 11 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/4606.JPG | test/12493.jpg | false | 11 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| valid/12170.jpg | test/12463.jpg | false | 11 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/10050.jpg | valid/12170.jpg | false | 12 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/10727.jpg | test/12493.jpg | false | 12 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/3737.JPG | valid/12057.jpg | false | 12 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/4345.JPG | test/12684.jpg | false | 12 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/9794.jpg | test/12582.jpg | false | 12 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| train/9872.jpg | test/12582.jpg | false | 12 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |
| valid/11985.jpg | test/12684.jpg | false | 12 | weaker_candidate | REJECT_LEAKAGE_CANDIDATE | Visual review shows materially different scene geometry, structure, texture, framing, or defect patterns. Perceptual similarity alone is insufficient evidence of leakage. | No special grouping required solely from this audit. This is not an instruction to force the images into different processed splits. | true |

## Verification and remaining scope

All 17 expected pairs were matched exactly and each has review_authorized=true.
The original filenames, splits, SHA evidence, perceptual distances, audit
severities, geometry and PNG review sheets are unchanged. The raw manifest,
audit CSVs, and prior orphan-decision artifacts were hash-checked unchanged.
No commands wrote under data/raw/. Official raw splits remain unchanged.
No final processed dataset was created. M1 remains incomplete.
