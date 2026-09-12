# Final GYU-DET V3 orphan-label human-triage summary

Human triage is recorded for all 21 orphan labels. This completes the first human
triage pass, not the pairing investigation or Milestone M1. No mapping is confirmed,
no repair is authorized or applied, and no unlabeled image is classified as negative.
data/raw/ remains immutable. Earlier decisions have been preserved exactly.

## Outcome counts

| Outcome | Labels |
|---|---:|
| NO_VALID_MATCH_IN_REVIEWED_TOP5 | 10 |
| UNRESOLVED_HOLD | 4 |
| MANUAL_REVIEW_PLAUSIBLE | 5 |
| REJECTED_RANK1_PAIRING | 2 |
| CONFIRMED_MAPPING | 0 |
| Total | 21 |

The two REJECTED_RANK1_PAIRING cases are train/7972.txt -> 6977.JPG and
train/190.txt -> 5190.JPG. This separate summary category preserves their original
`rejected` decisions: they rejected the current rank-1 pairing, not all top-five
candidates or all possible images. It would be incorrect to silently convert them
to NO_VALID_MATCH_IN_REVIEWED_TOP5 or UNRESOLVED_HOLD.

NO_VALID_MATCH_IN_REVIEWED_TOP5 is limited to the reviewed shortlist; it is not
proof that no matching image exists anywhere in the dataset. Plausible preferences
are tentative human judgments, never confirmed mappings. All 21 decisions have
repair_authorized=false; the count with repair_authorized=true is zero.

## Tentative human-preferred candidates

| Label | Tentative candidate | Original candidate rank |
|---|---|---:|
| train/1554.txt | 1553.JPG | 1 |
| train/1959.txt | 1958.JPG | 1 |
| train/3763.txt | 3765.JPG | 1 |
| train/4923.txt | 4323.JPG | 3 |
| valid/9156.txt | 9154.JPG | 1 |

For train/4923.txt the selected preference is rank 3, not rank 1. The existing
human_triage_decisions.csv field reviewed_rank1_candidate remains 4963.JPG because
it describes the ranking, not a selection. Its tentative candidate field is 4323.JPG.
For train/664.txt, 624.JPG is discussed but not selected; the outcome is unresolved_hold.

## All label decisions

| Split | Label | Annotation count | Outcome | Tentative candidate | Repair authorized | Review notes |
|---|---|---:|---|---|---|---|
| train | 111.txt | 3 | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none | false | The breakage/reinforcement boxes do not convincingly align with visible defects in any of the five reviewed candidates. Two reinforcement boxes are tiny, and none of the candidates provides persuasive exposed-rebar alignment. No valid match among the reviewed top five only; this is not proof that no matching image exists elsewhere in the dataset. Repair authorized: false. |
| train | 112.txt | 23 | UNRESOLVED_HOLD | none | false | Rank-1 candidate appears visually plausible, but 23 annotations and structurally similar scenes can create false confidence. Hold unresolved; deeper manual inspection required. |
| train | 190.txt | 1 | REJECTED_RANK1_PAIRING | none | false | Reject current rank-1 pairing: reinforcement box placement near sky / non-structural region is not credible. Keep label unmatched. Other candidates have not been individually rejected. |
| train | 237.txt | 1 | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none | false | The single Reinforcement annotation does not convincingly correspond to exposed reinforcement in any of the five reviewed candidates. Several boxes land on relatively ordinary concrete or non-defect regions. This outcome is limited to the reviewed top five; it is not proof that no matching image exists anywhere in the dataset. Repair authorized: false. |
| train | 238.txt | 1 | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none | false | The single Reinforcement annotation does not align convincingly with exposed reinforcement in the five reviewed candidates. Candidates include concrete, rock/slope, pavement, and roadway imagery without a persuasive exposed-rebar match. This outcome is limited to the reviewed top five; it is not proof that no matching image exists anywhere in the dataset. Repair authorized: false. |
| train | 314.txt | 3 | UNRESOLVED_HOLD | none | false | This annotation contains two Breakage boxes and one large Seepage box. Some candidates, especially 3141.JPG and 2014.JPG, are structurally relevant bridge images, but the annotation placement is not convincing enough to select a candidate and not implausible enough to discard the label outright. Label-level unresolved hold; no candidate selected and no possible mapping rejected by this decision. Repair authorized: false. |
| train | 574.txt | 8 | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none | false | The eight annotations include Reinforcement, Comb, and Hole classes, but the reviewed candidates predominantly show roadway, markings, joints, vehicles, pavement, or ordinary barriers. The boxes do not convincingly correspond to those structural defect categories. This outcome concerns the reviewed top five only, not proof that no matching image exists anywhere in the dataset. Repair authorized: false. |
| train | 664.txt | 1 | UNRESOLVED_HOLD | none | false | The annotation is Hole. Candidate 624.JPG is structurally relevant and the box overlaps a bearing/gap region, but that visual appearance alone does not establish a true hole defect or a valid pairing. Evidence is insufficient to select or reject all possible mappings. Label-level unresolved hold; no candidate selected, including 624.JPG. No possible mapping is rejected by this decision. Repair authorized: false. |
| train | 728.txt | 1 | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none | false | The Comb/Honeycombing annotation does not convincingly align with honeycombed concrete in any of the five reviewed candidates. The box falls on image edges, timestamp regions, pavement, loose rocks, or other non-honeycombed surfaces. This outcome concerns the reviewed top five only, not proof that no matching image exists anywhere in the dataset. Repair authorized: false. |
| train | 1264.txt | 2 | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none | false | Both annotation rows are Reinforcement, but the five reviewed candidates primarily show pavement cracks or ordinary concrete surfaces without convincing exposed reinforcement. No valid match among the reviewed top five only; this is not proof that no matching image exists elsewhere in the dataset. Repair authorized: false. |
| train | 1458.txt | 1 | UNRESOLVED_HOLD | none | false | Rank-1 candidate is only weakly plausible from the sheet alone. Hold unresolved; do not pair or repair. |
| train | 1554.txt | 7 | MANUAL_REVIEW_PLAUSIBLE | 1553.JPG | false | Strongest candidate in this review batch. Numeric difference 1; visibly deteriorated bridge/bearing area. The seven mixed defect boxes fall in generally plausible structural regions, but the evidence is not strong enough to confirm the mapping. Tentative human preference only; not an accepted repair mapping. Repair authorized: false. |
| train | 1564.txt | 9 | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none | false | All nine annotation rows are Reinforcement, but the reviewed candidate images do not show convincing exposed reinforcement. Several candidates are pavement/crack surfaces and many boxes are extremely small. No valid match among the reviewed top five only; this is not proof that no matching image exists elsewhere in the dataset. Repair authorized: false. |
| train | 1800.txt | 4 | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none | false | The three Breakage and one Reinforcement annotations do not convincingly align with any of the five reviewed candidate images. Rank 1 places boxes over ground/vegetation, and the remaining candidates also fail to provide convincing structural-defect alignment. This outcome is limited to the reviewed top five; it is not proof that no matching image exists anywhere in the dataset. Repair authorized: false. |
| train | 1959.txt | 5 | MANUAL_REVIEW_PLAUSIBLE | 1958.JPG | false | Tentative human-preferred candidate appears plausible. Do not repair: 1458.txt may relate to a similar image family. Requires further manual review; not an accepted repair mapping. |
| train | 3763.txt | 7 | MANUAL_REVIEW_PLAUSIBLE | 3765.JPG | false | Numeric difference 2; relevant bridge bearing/joint region. Several crack and breakage boxes are structurally plausible, but visual alignment is not definitive enough to confirm the mapping. Tentative human preference only; not an accepted repair mapping. Repair authorized: false. |
| train | 4047.txt | 1 | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none | false | The single Comb/Honeycombing annotation does not convincingly align with honeycombed concrete in any reviewed candidate. Several candidate boxes lie on ground, pavement, background, or otherwise implausible regions. This outcome is limited to the reviewed top five; it is not proof that no matching image exists anywhere in the dataset. Repair authorized: false. |
| train | 4626.txt | 1 | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none | false | The single Breakage annotation does not convincingly align with structural breakage in any of the five reviewed candidates. The box repeatedly falls near dark image edges, floor regions, or otherwise non-defect areas. This outcome concerns the reviewed top five only, not proof that no matching image exists anywhere in the dataset. Repair authorized: false. |
| train | 4923.txt | 2 | MANUAL_REVIEW_PLAUSIBLE | 4323.JPG | false | Among the five reviewed candidates, 4323.JPG is the most visually plausible because it contains a visible crack-like feature in a region reasonably consistent with the two Crack annotations. Other candidates primarily align with road joints, painted surfaces, background, or ordinary pavement. Evidence is still insufficient for a confirmed repair. Tentative human preference for rank 3 only; not a confirmed mapping. Other candidate rows remain pending, not implicitly rejected. Repair authorized: false. |
| train | 7972.txt | 2 | REJECTED_RANK1_PAIRING | none | false | Reject current rank-1 pairing: breakage boxes fall in sky / non-defect areas. Keep label unmatched. Other candidates have not been individually rejected. |
| valid | 9156.txt | 1 | MANUAL_REVIEW_PLAUSIBLE | 9154.JPG | false | Strongest candidate among the six reviewed sheets; tentative human-preferred likely match. Still not algorithmically certain and not an accepted repair mapping. |

## Recording and validation

The final five decisions added 17 candidate-row updates: all five rows for each
of the three no-valid-top-five outcomes, rank 3 for the plausible 4923 preference,
and rank 1 as the label-level hold marker for 664, consistent with earlier holds.
Other index rows remain unchanged. All previous 16 decision rows were retained
byte-for-byte in human_triage_decisions.csv; their index rows were also preserved.

There are 105 candidate rows: 50 no_valid_match_in_reviewed_top5, 4 unresolved_hold,
5 manual_review_plausible, 2 rejected, and 44 pending. Pending candidate rows on
reviewed labels do not mean their labels lack human triage and do not override
label-level outcomes. All 21 label keys match the original unmatched-label inventory.
Existing review PNG hashes are unchanged. No dataset files were written.

The raw audit still has 712 images without labels and 21 orphan labels. The
712 - 21 = 691 relationship remains suggestive but unproven. No repaired dataset
or accepted repair mapping has been created. M1 remains incomplete.
