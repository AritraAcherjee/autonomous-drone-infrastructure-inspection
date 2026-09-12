# Preliminary visual triage notes

These observations come from inspecting the generated contact sheet and the
full-size rank-1 panel for train/112.txt. They are not an exhaustive review of all
105 candidates, accepted mappings, or reviewer decisions. At initial generation all index rows were pending. The recorded human decisions
below supersede that initial state for six rank-1 rows.

- train/7972.txt on rank-1 train/6977.JPG places its two Breakage boxes over sky
  and the skyline. This is a conspicuous alignment/category concern.
- train/190.txt on rank-1 train/5190.JPG places a tiny Reinforcement box near the
  sky edge of a roadway scene. Inspect the full image before any decision.
- train/1458.txt and train/1959.txt both rank train/1958.JPG first. Independent
  filename rankings can propose the same image for different orphan labels;
  there is no inferred one-to-one repair mapping.
- train/112.txt contains 23 annotation rows, many with tiny reinforcement boxes.
  Full sheets provide numbered class callouts, but reduced-size panels cannot
  establish whether these small defects align. Inspect source pixels read-only.
- train/1264.txt and train/1564.txt also include candidates where box dimensions
  are below 10 source pixels. See validation.json for per-candidate warnings.

All 21 files pass normalized-field YOLO validation. This does not establish that
any file belongs to any displayed image. No repair or negative classification has
been performed. The 712 - 21 = 691 relationship remains an unproven hypothesis.

Validation performed: all 20 data tests passed (9 new visual-review tests and
11 prior pairing tests). The real run produced 21 sheets, 105 candidate rows,
and no rendering failures. All eligible numeric neighbors within +/-2 were
already among the selected top five. Raw file paths, sizes, and modification
times were unchanged across generation.

## First human triage batch (preserved)

These are the user's decisions based on six review sheets, superseding preliminary
observations for those cases. They authorize recording review outcomes only.

| Label | Outcome | Reviewed rank-1 candidate | Tentative human preference |
|---|---|---|---|
| train/7972.txt | Confirmed reject of current pairing; keep unmatched | 6977.JPG | none |
| train/190.txt | Confirmed reject of current pairing; keep unmatched | 5190.JPG | none |
| train/1458.txt | Unresolved hold; weak visual plausibility | 1958.JPG | none |
| train/112.txt | Unresolved hold; deeper inspection of 23 annotations | 1912.JPG | none |
| train/1959.txt | Manual-review plausible; similar image-family concern with 1458.txt | 1958.JPG | 1958.JPG (tentative) |
| valid/9156.txt | Manual-review plausible / likely match; strongest of six reviewed | 9154.JPG | 9154.JPG (tentative) |

The rejected 7972 overlay places Breakage boxes in sky / non-defect areas; the
rejected 190 overlay places Reinforcement near sky / a non-structural region.
Neither rejection establishes that every other candidate is wrong. The 112 hold
reflects potential false confidence from structurally similar scenes. The 1959
preference does not resolve its relationship to the 1458 image family.

At the end of the first batch, only the six reviewed rank-1 rows had been updated. `rejected` applies
to that candidate pairing; `unresolved_hold` records an unresolved review;
`manual_review_plausible` records tentative human preference, not final acceptance.
At that point, only the two plausible rows had `reviewer_selected_candidate` populated. The
remaining 99 candidate rows were pending and unchanged; their pending state does
not override a label-level hold. `human_triage_decisions.csv` records all six
label-level outcomes and explicitly sets repair_authorized=false.

No mapping is accepted for repair. All 21 annotations remain unmatched in the raw
dataset. No files under data/raw/ were changed; no remaining image was classified
as negative. The original pairing counts and the unproven 712 - 21 = 691 hypothesis
are unchanged. M1 remains incomplete.

## Second human triage batch (preserved)

The five additional decisions below are user-supplied human review outcomes.
The first six decisions are preserved without change. Status strings use the
existing lowercase convention in CSVs.

| Label | Human outcome | Tentative selected candidate |
|---|---|---|
| train/111.txt | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none |
| train/1264.txt | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none |
| train/1554.txt | MANUAL_REVIEW_PLAUSIBLE | 1553.JPG |
| train/1564.txt | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none |
| train/3763.txt | MANUAL_REVIEW_PLAUSIBLE | 3765.JPG |

NO_VALID_MATCH_IN_REVIEWED_TOP5 applies only to the five displayed candidates.
It is not proof that no matching image exists anywhere in the dataset. For each
of these three labels, all five reviewed index rows carry that scoped status.
For the two plausible labels, only the preferred rank-1 row is marked plausible;
other rows stay pending and are not implicitly rejected. Reasons are retained
verbatim in substance below and in both CSVs.

At the end of the second batch: 11 labels with recorded human decisions: 2 rejected rank-1
pairings, 2 unresolved holds, 3 labels with no valid match in reviewed top five,
and 4 manual-review-plausible preferences. All 11 have repair_authorized=false.
At the end of that batch the index contained 105 candidate rows: 82 pending, 15 no_valid_match_in_reviewed_top5,
2 rejected, 2 unresolved_hold, and 4 manual_review_plausible. Pending rows on
previously reviewed labels do not override their label-level decisions.

No repair mapping is accepted. Raw data is unchanged, no unlabeled images are
classified as negatives, and M1 remains incomplete.

- **train/111.txt**: The breakage/reinforcement boxes do not convincingly align with visible defects in any of the five reviewed candidates. Two reinforcement boxes are tiny, and none of the candidates provides persuasive exposed-rebar alignment.

- **train/1264.txt**: Both annotation rows are Reinforcement, but the five reviewed candidates primarily show pavement cracks or ordinary concrete surfaces without convincing exposed reinforcement.

- **train/1554.txt**: Strongest candidate in this review batch. Numeric difference 1; visibly deteriorated bridge/bearing area. The seven mixed defect boxes fall in generally plausible structural regions, but the evidence is not strong enough to confirm the mapping.

- **train/1564.txt**: All nine annotation rows are Reinforcement, but the reviewed candidate images do not show convincing exposed reinforcement. Several candidates are pavement/crack surfaces and many boxes are extremely small.

- **train/3763.txt**: Numeric difference 2; relevant bridge bearing/joint region. Several crack and breakage boxes are structurally plausible, but visual alignment is not definitive enough to confirm the mapping.

## Third human triage batch (preserved)

These five outcomes are human decisions supplied by the user. All 11 previous
decisions and their existing index rows remain unchanged. No selected candidate
is recorded for this batch, and repair_authorized=false for every decision.

| Label | Human outcome | Selected candidate |
|---|---|---|
| train/1800.txt | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none |
| train/237.txt | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none |
| train/238.txt | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none |
| train/314.txt | UNRESOLVED_HOLD | none |
| train/4047.txt | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none |

The four NO_VALID_MATCH_IN_REVIEWED_TOP5 outcomes apply only to the reviewed
five candidates, not to all images in the dataset. All five index rows for each
of those four labels record the scoped outcome. For train/314.txt the rank-1
row records unresolved_hold, consistent with the earlier holds; its other rows
remain pending. The label-level hold is recorded in human_triage_decisions.csv.
In particular, neither 3141.JPG nor 2014.JPG is selected or rejected by this hold.

At the end of the third batch: 16 human decisions: 2 rejected rank-1 pairings, 3 unresolved
holds, 7 labels with no valid match in reviewed top five, and 4 manual-review
plausible preferences. All 16 retain repair_authorized=false. At that point five labels remained
unreviewed: train/4626.txt, train/4923.txt, train/574.txt, train/664.txt, train/728.txt.

At the end of that batch, index totals (105 candidate rows): 61 pending, 35
no_valid_match_in_reviewed_top5, 2 rejected, 3 unresolved_hold, and 4
manual_review_plausible. Pending rows belonging to reviewed labels do not override
their label-level outcomes. At that point the final five labels' 25 candidate rows were pending.

No repair mapping is accepted. Raw data and existing PNGs are unchanged; no
unlabeled images have been classified as negatives. M1 remains incomplete.

- **train/1800.txt**: The three Breakage and one Reinforcement annotations do not convincingly align with any of the five reviewed candidate images. Rank 1 places boxes over ground/vegetation, and the remaining candidates also fail to provide convincing structural-defect alignment.

- **train/237.txt**: The single Reinforcement annotation does not convincingly correspond to exposed reinforcement in any of the five reviewed candidates. Several boxes land on relatively ordinary concrete or non-defect regions.

- **train/238.txt**: The single Reinforcement annotation does not align convincingly with exposed reinforcement in the five reviewed candidates. Candidates include concrete, rock/slope, pavement, and roadway imagery without a persuasive exposed-rebar match.

- **train/314.txt**: This annotation contains two Breakage boxes and one large Seepage box. Some candidates, especially 3141.JPG and 2014.JPG, are structurally relevant bridge images, but the annotation placement is not convincing enough to select a candidate and not implausible enough to discard the label outright.

- **train/4047.txt**: The single Comb/Honeycombing annotation does not convincingly align with honeycombed concrete in any reviewed candidate. Several candidate boxes lie on ground, pavement, background, or otherwise implausible regions.

## Final human triage batch and current summary

Human triage is now recorded for all 21 orphan labels. The previous 16 decisions
are preserved exactly. No repairs are authorized or applied.

| Label | Outcome | Tentative candidate |
|---|---|---|
| train/4626.txt | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none |
| train/4923.txt | MANUAL_REVIEW_PLAUSIBLE | 4323.JPG (rank 3) |
| train/574.txt | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none |
| train/664.txt | UNRESOLVED_HOLD | none |
| train/728.txt | NO_VALID_MATCH_IN_REVIEWED_TOP5 | none |

Final label totals: 10 no-valid-match-in-reviewed-top-five, 4 unresolved holds,
5 manual-review-plausible preferences, and 2 rejected rank-1 pairings. Confirmed
mappings: 0. repair_authorized=true: 0. All 21 retain repair_authorized=false.
The two earlier rank-1 rejections are not reclassified as rejecting all top five.
No-valid-top-five outcomes do not prove that no match exists elsewhere.

For 4923, only the preferred rank-3 index row is marked plausible. For 664, the
rank-1 row marks the label-level hold; 624.JPG is not selected or rejected. Current
index totals: 50 no_valid_match_in_reviewed_top5, 4 unresolved_hold, 5
manual_review_plausible, 2 rejected, 44 pending. Pending candidate rows do not
override label-level review outcomes. No labels remain without human triage.

See final_triage_summary.csv and final_triage_summary.md for all 21 annotations,
counts, outcomes, tentative candidates, authorization flags, and review notes.
Raw data and PNGs are unchanged. No negatives are classified. M1 remains incomplete.

- **train/4626.txt**: The single Breakage annotation does not convincingly align with structural breakage in any of the five reviewed candidates. The box repeatedly falls near dark image edges, floor regions, or otherwise non-defect areas.

- **train/4923.txt**: Among the five reviewed candidates, 4323.JPG is the most visually plausible because it contains a visible crack-like feature in a region reasonably consistent with the two Crack annotations. Other candidates primarily align with road joints, painted surfaces, background, or ordinary pavement. Evidence is still insufficient for a confirmed repair.

- **train/574.txt**: The eight annotations include Reinforcement, Comb, and Hole classes, but the reviewed candidates predominantly show roadway, markings, joints, vehicles, pavement, or ordinary barriers. The boxes do not convincingly correspond to those structural defect categories.

- **train/664.txt**: The annotation is Hole. Candidate 624.JPG is structurally relevant and the box overlaps a bearing/gap region, but that visual appearance alone does not establish a true hole defect or a valid pairing. Evidence is insufficient to select or reject all possible mappings.

- **train/728.txt**: The Comb/Honeycombing annotation does not convincingly align with honeycombed concrete in any of the five reviewed candidates. The box falls on image edges, timestamp regions, pavement, loose rocks, or other non-honeycombed surfaces.
