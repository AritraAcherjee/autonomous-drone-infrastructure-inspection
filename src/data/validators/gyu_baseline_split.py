"""Dry-run split proposals from validated artifacts. Never materializes samples."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Any

from data.validators.gyu_orphan_review import parse_yolo, read_csv

SPLITS = ('train', 'valid', 'test')
PRIORITY = {'test': 0, 'valid': 1, 'train': 2}
CLASSES = ['Crack', 'Breakage', 'Comb', 'Hole', 'Reinforcement', 'Seepage']
DISPLAY = ['Crack', 'Breakage', 'Honeycombing', 'Hole', 'Exposed Reinforcement', 'Seepage']
APPROVED = {'CONFIRMED_EXACT_CROSS_SPLIT_LEAKAGE', 'HIGH_CONFIDENCE_NEAR_DUPLICATE_LEAKAGE',
            'UNRESOLVED_POSSIBLE_SAME_SCENE'}
MANIFEST_FIELDS = ('processed_split raw_split image_relative_path label_relative_path image_sha256 '
                   'annotation_count class_ids duplicate_group_id leakage_group_id inclusion_reason exclusion_reason').split()


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_write(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def normalized_rows(text: str) -> tuple[tuple[Decimal, ...], ...]:
    """Exact decimal comparison: whitespace/numeric spelling ignored; no rounding tolerance."""
    if text.strip():
        parse_yolo(text, CLASSES)  # Reuse the validated field/class/bounds parser.
    return tuple(tuple(Decimal(token) for token in line.split()) for line in text.splitlines() if line.strip())


def annotation_consistency(texts: list[str | None]) -> str:
    available = [normalized_rows(text) for text in texts if text is not None]
    if not available:
        return 'NO_LABELS'
    if len(available) == 1 and len(texts) > 1:
        return 'ONLY_ONE_LABELED_COPY'
    if all(rows == available[0] for rows in available):
        return 'IDENTICAL_ANNOTATIONS'
    if all(sorted(rows) == sorted(available[0]) for rows in available):
        return 'REORDERED_EQUIVALENT_ANNOTATIONS'
    return 'CONFLICTING_ANNOTATIONS'


def canonical_annotations(rows: tuple[tuple[Decimal, ...], ...]) -> list[list[str]]:
    def number(value: Decimal) -> str:
        if value == 0:
            return '0'
        text = format(value, 'f')
        return text.rstrip('0').rstrip('.') if '.' in text else text
    return [[number(value) for value in row] for row in sorted(rows)]


def representative(members: list[str], records: dict[str, dict[str, Any]]) -> str:
    """Evaluation first; same split uses casefolded relative path, then original path."""
    return min(members, key=lambda p: (PRIORITY[records[p]['raw_split']], p.casefold(), p))


def connected_groups(paths: list[str], edges: list[tuple[str, str]]) -> dict[str, str]:
    parents = {p: p for p in paths}

    def find(p: str) -> str:
        while parents[p] != p:
            parents[p] = parents[parents[p]]
            p = parents[p]
        return p

    for a, b in sorted(edges):
        ra, rb = find(a), find(b)
        parents[max(ra, rb)] = min(ra, rb)
    grouped: dict[str, list[str]] = defaultdict(list)
    for p in sorted(paths):
        grouped[find(p)].append(p)
    result = {}
    for members in grouped.values():
        if len(members) > 1:
            gid = 'LG_' + hashlib.sha256('\n'.join(members).encode()).hexdigest()[:16]
            result.update({p: gid for p in members})
    return result


def proposal(records: dict[str, dict[str, Any]], exact_groups: dict[str, list[str]],
             label_text: dict[str, str | None], decisions: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build exclusions in memory; preserve original split for every retained row."""
    records = {p: dict(r) for p, r in sorted(records.items())}
    lookup = {(r['raw_split'], Path(p).name): p for p, r in records.items()}
    if len(lookup) != len(records):
        raise ValueError('Ambiguous raw image identity')
    edges, approved_pairs = [], []
    outcomes: dict[str, set[str]] = defaultdict(set)
    for decision in decisions:
        if decision['human_outcome'] == 'REJECT_LEAKAGE_CANDIDATE':
            continue
        if decision['human_outcome'] not in APPROVED or decision['review_authorized'].lower() != 'true':
            raise ValueError('Unknown or unauthorized leakage decision')
        a = lookup[(decision['split_a'], decision['image_a'])]
        b = lookup[(decision['split_b'], decision['image_b'])]
        edges.append((a, b))
        approved_pairs.append((a, b, decision['human_outcome']))
        outcomes[a].add(decision['human_outcome'])
        outcomes[b].add(decision['human_outcome'])
    for members in exact_groups.values():
        edges.extend((members[0], p) for p in members[1:])
    groups = connected_groups(list(records), edges)
    for p, row in records.items():
        row.update(image_relative_path=p, leakage_group_id=groups.get(p, ''), exact_duplicate_group_id='',
                   human_leakage_outcome=';'.join(sorted(outcomes[p])), proposed_included=row['baseline_eligible'],
                   inclusion_reason='EXACT_PAIR_SOURCE_SPLIT_PRESERVED' if row['baseline_eligible'] else '',
                   processed_split=row['raw_split'] if row['baseline_eligible'] else '')
    checks = []

    def exclude(p: str, reason: str) -> None:
        records[p].update(proposed_included=False, processed_split='', exclusion_reason=reason, inclusion_reason='')

    for gid, members in sorted(exact_groups.items()):
        members = sorted(members)
        for p in members:
            records[p]['exact_duplicate_group_id'] = gid
        texts = [label_text[p] for p in members]
        outcome = annotation_consistency(texts)
        normalized = [normalized_rows(t) if t is not None else None for t in texts]
        available = [r for r in normalized if r is not None]
        canonical = [hashlib.sha256(json.dumps(canonical_annotations(r), separators=(',', ':')).encode()).hexdigest()
                     if r is not None else '' for r in normalized]
        eligible = [p for p in members if records[p]['baseline_eligible']]
        chosen = ''
        conflict = outcome == 'CONFLICTING_ANNOTATIONS'
        if conflict:
            for p in eligible:
                exclude(p, 'ANNOTATION_CONFLICT_HUMAN_REVIEW_REQUIRED')
        elif eligible:
            chosen = representative(eligible, records)
            records[chosen]['inclusion_reason'] = 'EXACT_DUPLICATE_REPRESENTATIVE'
            for p in eligible:
                if p != chosen:
                    exclude(p, 'EQUIVALENT_EXACT_DUPLICATE_REDUNDANT')
        checks.append(dict(exact_duplicate_group_id=gid, members=json.dumps(members),
            annotation_availability=json.dumps([t is not None for t in texts]),
            annotation_row_counts=json.dumps([len(r) if r is not None else None for r in normalized]),
            class_ids=json.dumps([sorted({int(v[0]) for v in r}) if r is not None else None for r in normalized]),
            row_counts_equal=len({len(r) for r in available}) == 1 if len(available) > 1 else '',
            class_multisets_equal=all(sorted(v[0] for v in r) == sorted(v[0] for v in available[0]) for r in available) if len(available) > 1 else '',
            normalized_box_multisets_equal=all(sorted(v[1:] for v in r) == sorted(v[1:] for v in available[0]) for r in available) if len(available) > 1 else '',
            normalized_sorted_label_sha256=json.dumps(canonical), annotation_consistency=outcome,
            normalized_sorted_annotations=json.dumps([canonical_annotations(r) if r is not None else None for r in normalized]),
            representative_image=chosen, blocker=conflict,
            handling='Hold all eligible members; no representative selected; human review required.' if conflict else
                     'Retain deterministic eligible representative; no label transfer.'))
    # Full connected components, including paths through ineligible members, enforce transitive constraints.
    components: dict[str, list[str]] = defaultdict(list)
    for p, gid in groups.items():
        if records[p]['proposed_included']:
            components[gid].append(p)
    for members in components.values():
        target = records[representative(members, records)]['raw_split']
        for p in members:
            if records[p]['raw_split'] != target:
                exclude(p, 'APPROVED_LEAKAGE_GROUP_OTHER_SPLIT_RETAINED')
    handling = []
    for a, b, outcome in approved_pairs:
        ra, rb = records[a], records[b]
        initial = {r['raw_split'] for r in (ra, rb) if r['baseline_eligible']}
        final = {r['processed_split'] for r in (ra, rb) if r['proposed_included']}
        handling.append(dict(image_a=a, image_b=b, human_outcome=outcome, leakage_group_id=groups[a],
            a_baseline_eligible=ra['baseline_eligible'], b_baseline_eligible=rb['baseline_eligible'],
            a_valid_exact_pair=ra['pairing_status'] == 'exact_pair' and ra['baseline_eligible'],
            b_valid_exact_pair=rb['pairing_status'] == 'exact_pair' and rb['baseline_eligible'],
            conflict_after_eligibility_filtering=len(initial) > 1, a_proposed_split=ra['processed_split'],
            b_proposed_split=rb['processed_split'], a_exclusion_reason=ra['exclusion_reason'],
            b_exclusion_reason=rb['exclusion_reason'], conflict_after_proposal=len(final) > 1,
            proposed_handling='Preserve eligible source split; exclude ineligible or conflicting-split members as listed. No label transfer.'))
    return list(records.values()), checks, handling


def assert_leakage_safe(rows: list[dict[str, Any]], orphan_label_paths: set[str]) -> dict[str, bool]:
    included = [r for r in rows if r['proposed_included']]
    for key in ('image_sha256', 'leakage_group_id'):
        splits: dict[str, set[str]] = defaultdict(set)
        for row in included:
            if row[key]:
                splits[row[key]].add(row['processed_split'])
        if any(len(v) > 1 for v in splits.values()):
            raise ValueError(f'Leakage assertion failed: {key} crosses processed splits')
    for row in included:
        if not row['baseline_eligible'] or row['pairing_status'] != 'exact_pair' or not row['label_relative_path']:
            raise ValueError('Inclusion assertion failed: non-exact or unlabeled sample')
        if row['label_relative_path'] in orphan_label_paths:
            raise ValueError('Inclusion assertion failed: orphan annotation')
        if row['processed_split'] != row['raw_split'] or row['processed_split'] not in SPLITS:
            raise ValueError('Source split was changed')
    return dict(no_cross_split_sha256=True, no_cross_split_approved_group=True,
                no_cross_split_conservative_group=True, no_orphan_annotations=True,
                no_unlabeled_images=True, included_exact_pairs_only=True, retained_source_splits_unchanged=True)


def split_statistics(rows: list[dict[str, Any]], box_rows: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    by_image: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for box in box_rows:
        by_image[(box['split'], box['image_filename'])].append(box)
    statistics, classes, annotation_stats, removals = [], [], [], []
    for split in SPLITS:
        raw = [r for r in rows if r['raw_split'] == split]
        selected = [r for r in raw if r['proposed_included']]
        for reason, count in sorted(Counter(r['exclusion_reason'] for r in raw if not r['proposed_included']).items()):
            removals.append(dict(raw_split=split, exclusion_reason=reason, images=count))
        for view, members in [('RAW_OFFICIAL_EXACT_PAIRS', [r for r in raw if r['pairing_status'] == 'exact_pair']),
                              ('DRY_RUN_PROPOSED', selected)]:
            boxes = [b for r in members for b in by_image[(split, Path(r['image_relative_path']).name)]]
            counts = [r['annotation_count'] for r in members]
            cc = Counter(int(b['class_id']) for b in boxes)
            resolutions = Counter(f"{r['width']}x{r['height']}" for r in members)
            statistics.append(dict(view=view, split=split, raw_official_images=len(raw), images=len(members),
                annotations=len(boxes), multi_class_percent=100*sum(len(json.loads(r['class_ids'])) > 1 for r in members)/len(members) if members else 0,
                median_annotations_per_image=median(counts) if counts else None,
                median_relative_box_area=median(float(b['relative_image_area']) for b in boxes) if boxes else None,
                major_source_resolutions=json.dumps(sorted(resolutions.items(), key=lambda v: (-v[1], v[0]))[:5]),
                images_excluded_from_raw=len(raw)-len(selected) if view == 'DRY_RUN_PROPOSED' else 0))
            for cid, name in enumerate(CLASSES):
                classes.append(dict(view=view, split=split, class_id=cid, raw_class_name=name,
                    presentation_class_name=DISPLAY[cid], instances=cc[cid],
                    images_containing_class=sum(cid in json.loads(r['class_ids']) for r in members)))
            annotation_stats.append(dict(view=view, split=split, images=len(members), annotation_instances=len(boxes),
                mean_annotations_per_image=sum(counts)/len(counts) if counts else None,
                median_annotations_per_image=median(counts) if counts else None,
                min_annotations_per_image=min(counts) if counts else None, max_annotations_per_image=max(counts) if counts else None,
                median_relative_box_area=median(float(b['relative_image_area']) for b in boxes) if boxes else None))
    return dict(split_statistics=statistics, split_class_distribution=classes,
                split_annotation_statistics=annotation_stats, exclusion_summary=removals)


def load_inputs(repository: Path, audit: Path, eda: Path) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, str | None], list[dict[str, str]], set[str]]:
    manifest_path = repository/'data/manifests/gyu_det_v3_raw_manifest.csv'
    manifest = read_csv(manifest_path)
    images = {(r['split'], r['image_filename']): r for r in read_csv(audit/'full_validation/image_validation.csv')}
    labels = {r['label_relative_path']: r for r in read_csv(audit/'full_validation/label_validation.csv')}
    orphan_paths = {p for p, r in labels.items() if r['pairing_status'] == 'orphan_label'}
    triage = read_csv(audit/'orphan_review/final_triage_summary.csv')
    if {(r['split'], r['label_filename']) for r in triage} != {(labels[p]['split'], labels[p]['label_filename']) for p in orphan_paths}:
        raise ValueError('Orphan triage inventory mismatch')
    if any(r['repair_authorized'].lower() == 'true' for r in triage):
        raise ValueError('Orphan policy changed; review this proposal implementation before continuing')
    authoritative = repository/'data/raw/gyu_det/v3/archives/classes.txt'
    if authoritative.read_text(encoding='utf-8-sig').splitlines() != CLASSES:
        raise ValueError('Raw class ordering changed')
    summary = json.loads((eda/'eda_summary.json').read_text(encoding='utf-8'))
    for relative, expected in summary['input_sha256'].items():
        if hash_file(repository/relative) != expected:
            raise ValueError(f'EDA provenance is stale: {relative}')
    box_rows = read_csv(eda/'box_measurements.csv')
    counts: Counter = Counter()
    ids: dict[tuple[str, str], set[int]] = defaultdict(set)
    rounding: Counter = Counter()
    for b in box_rows:
        key = (b['split'], b['image_filename'])
        counts[key] += 1
        ids[key].add(int(b['class_id']))
        if float(b['boundary_excess']) > 1e-6:
            raise ValueError('Unexpected non-rounding boundary violation')
        rounding[key] += b['rounding_warning'].lower() == 'true'
    records, texts = {}, {}
    sha_groups: dict[str, list[str]] = defaultdict(list)
    raw_root = (repository/'data/raw').resolve()
    for image in manifest:
        key = (image['split'], image['image_filename'])
        if image['split'] not in SPLITS or image['image_relative_path'] in records:
            raise ValueError('Invalid or duplicate manifest image')
        validated = images[key]
        for field in ('image_sha256', 'width', 'height', 'pairing_status'):
            if image[field] != validated[field]:
                raise ValueError(f'Manifest/validation mismatch: {key}/{field}')
        path = (repository/image['image_relative_path']).resolve()
        if raw_root not in path.parents or not path.is_file():
            raise ValueError(f'Missing or unsafe image path: {path}')
        exact = image['pairing_status'] == 'exact_pair'
        if not exact and image['pairing_status'] != 'image_without_label':
            raise ValueError('Unsupported pairing state')
        label = labels[image['label_relative_path']] if exact else None
        image_fatal = any(issue['severity'] == 'error' and issue['issue_code'] != 'auxiliary_frame_decode_failure'
                          for issue in json.loads(validated['issues']))
        eligible = (exact and label['validation_status'] != 'invalid'
                    and validated['primary_decode_success'].lower() == 'true' and not image_fatal)
        reason = '' if eligible else 'UNLABELED_UNCLASSIFIED' if not exact else 'VALIDATION_ERROR'
        if exact:
            if label['image_filename'] != image['image_filename'] or label['split'] != image['split'] or label['pairing_status'] != 'exact_pair':
                raise ValueError('Label-to-image inventory mismatch')
            label_path = (repository/image['label_relative_path']).resolve()
            if raw_root not in label_path.parents or not label_path.is_file():
                raise ValueError('Missing or unsafe exact label path')
            content = label_path.read_bytes()
            if hashlib.sha256(content).hexdigest() != label['label_sha256']:
                raise ValueError(f'Label bytes changed since validation: {label_path}')
            texts[image['image_relative_path']] = content.decode('utf-8-sig')
            if counts[key] != int(image['annotation_count']) or counts[key] != int(label['annotation_count']) or ids[key] != set(json.loads(image['class_ids'])):
                raise ValueError('EDA/manifest annotation inventory mismatch')
        else:
            if counts[key]:
                raise ValueError('EDA unexpectedly associates annotations with unlabeled image')
            texts[image['image_relative_path']] = None
        records[image['image_relative_path']] = dict(raw_split=image['split'], pairing_status=image['pairing_status'],
            baseline_eligible=eligible, exclusion_reason=reason, label_relative_path=image['label_relative_path'] if exact else '',
            image_sha256=image['image_sha256'], annotation_count=int(image['annotation_count']) if exact else None,
            class_ids=image['class_ids'] if exact else '[]', width=int(image['width']), height=int(image['height']),
            mpo_warning=validated['primary_decode_success'].lower() == 'true' and validated['decoder_failure_stage'].startswith('auxiliary_frame'),
            boundary_rounding_warning_count=rounding[key])
        sha_groups[image['image_sha256']].append(image['image_relative_path'])
    if len(records) != len(images) or sum(counts.values()) != summary['exact_pair_annotation_instances']:
        raise ValueError('Image or annotation coverage mismatch')
    groups: dict[str, list[str]] = defaultdict(list)
    for r in read_csv(audit/'leakage_audit/exact_duplicate_groups.csv'):
        if r['relative_path'] not in records or records[r['relative_path']]['image_sha256'] != r['sha256']:
            raise ValueError('Exact-duplicate audit differs from manifest')
        groups['EXACT_'+r['group_id']].append(r['relative_path'])
    if sorted(sorted(g) for g in groups.values()) != sorted(sorted(g) for g in sha_groups.values() if len(g) > 1):
        raise ValueError('Exact-duplicate audit does not cover all SHA groups')
    return records, dict(groups), texts, box_rows, orphan_paths


def policy_text(summary: dict[str, Any], consistency: list[dict[str, Any]], handling: list[dict[str, Any]]) -> str:
    lines = ['# GYU-DET V3 dry-run baseline split proposal', '',
        '**DRY RUN ONLY. No sample files or processed dataset are created. M1 remains incomplete.**', '',
        '## Eligibility versus proposed inclusion', '',
        'baseline_eligible means valid exact-pair eligibility BEFORE duplicate and leakage handling. proposed_included is the final dry-run decision. '
        'An eligible image can therefore have an exclusion_reason. Unlabeled images remain UNCLASSIFIED, never negative. '
        'Orphan labels are excluded independently in excluded_orphan_labels.csv; they are not extra raw-image rows. '
        'No label transfer or orphan repair is permitted. Readable MPO primary images and <=1e-6 boundary-rounding warnings remain eligible. '
        'This does not certify compatibility with the eventual training reader.', '',
        '## Exact duplicate consistency and representative policy', '',
        'All exact SHA-256 groups from the existing audit are reconciled with the complete manifest. Label hashes are verified against full validation. '
        'Fields are validated with the existing YOLO parser, then compared as exact decimal values. Whitespace, decimal spelling and row order '
        'do not cause false conflicts; rows form a multiset, so repeated rows retain multiplicity. No coordinate tolerance, rounding or clipping is applied. '
        'IDENTICAL_ANNOTATIONS means the normalized rows match in order; REORDERED_EQUIVALENT_ANNOTATIONS means they match only after sorting. '
        'Availability, row counts, class multiplicities, box values and normalized content fingerprints are reported separately.', '',
        'A conflicting group is blocked: all its eligible members are held out of the proposal, with no automatic representative. '
        'This is a reversible manifest exclusion pending human review, not a judgment that any member is invalid. '
        'For equivalent or one-labeled-copy groups, retain an eligible representative, prioritizing test, then valid, then train. '
        'The valid/test tie rule protects test isolation and is a proposal policy, not a new human leakage outcome. '
        'Within a split use lexicographic casefolded raw relative path, with the original path as a tie-breaker. '
        'This is string order, not numeric filename order. Redundant copies are excluded to avoid evaluation inflation or training overweighting.', '',
        f"Equivalent groups: {summary['equivalent_duplicate_groups']}; conflicting groups: {summary['conflicting_duplicate_groups']}.", '',
        '| Group | Consistency | Proposed representative | Human review required |', '|---|---|---|---|']
    lines += [f"| {r['exact_duplicate_group_id']} | {r['annotation_consistency']} | {r['representative_image'] or 'none'} | {r['blocker']} |" for r in consistency]
    lines += ['', '## Leakage handling', '',
        'All retained members preserve their raw split. No global random resplit is used. Exact duplicate edges and approved high-confidence '
        'or conservative unresolved edges form connected components, including paths through currently ineligible members. '
        'If eligible retained members span splits, choose test, then valid, then train and exclude members from the other splits. '
        'This keeps evaluation-side samples and sacrifices redundant/conflicting-split training coverage. No files are moved. '
        'Rejected perceptual candidates impose no grouping constraint. Original human outcomes are preserved; unresolved is not confirmed leakage.', '']
    for row in handling:
        lines += [f"- {row['image_a']} ↔ {row['image_b']}: {row['human_outcome']}. "
                  f"Pre-handling eligible: {row['a_baseline_eligible']}/{row['b_baseline_eligible']}; proposed splits: "
                  f"{row['a_proposed_split'] or 'excluded'} / {row['b_proposed_split'] or 'excluded'}. "
                  f"Exclusion reasons: {row['a_exclusion_reason'] or 'none'} / {row['b_exclusion_reason'] or 'none'}."]
    lines += ['', '## Dry-run counts and exclusions', '',
        f"Pre-handling eligible exact pairs: {summary['baseline_eligible_before_handling']:,}. "
        f"Proposed counts: {json.dumps(summary['proposed_images_by_split'], sort_keys=True)}.", '',
        'Exclusion totals (raw images only):', '']
    lines += [f'- {reason}: {count}.' for reason, count in summary['excluded_by_reason'].items()]
    lines += ['', 'Raw-official comparisons in split_statistics.csv and related tables use exact-pair supervision as the class/box denominator; '
        'raw_official_images also exposes all image counts. exclusion_summary.csv gives exact counts excluded from each original split and why. '
        'Source dimensions and all per-box measurements are reused from validated metadata and EDA. No images are decoded. '
        'The exact dataset identities and pending negative status prevent interpreting the supplied 691 negative total as identified negatives.', '',
        '## Raw and presentation class names', '', '| ID | Raw source | Proposed AegisInspect display name |', '|---:|---|---|']
    lines += [f'| {cid} | {raw} | {display} |' for cid, (raw, display) in enumerate(zip(CLASSES, DISPLAY))]
    lines += ['', 'IDs remain unchanged. No classes are merged and no labels are rewritten.', '',
        '## Assertions, reproducibility and approval boundary', '',
        'Run `python scripts/data/propose_gyu_baseline_split.py` from the repository. No random seed is needed: '
        'all choices and serialization orders are deterministic. Input/source SHA-256 values are recorded in proposal_summary.json. '
        'Image byte hashes are reused from validation; existing raw images are checked for existence but not rehashed. '
        'All exact-pair label bytes are hash-checked read-only. The routine fails if a leakage or inclusion assertion fails. '
        'Annotation-conflict groups are reported as blockers even when the held-out proposal passes leakage assertions.', '',
        'The YAML references reserved FUTURE list files under data/processed/gyu_det_v3_baseline. These files are not created or claimed to exist. '
        'The config is a proposal, not approval to train. Human review of blocked groups and explicit approval of any later materialization are still required. '
        'Official raw split membership, every prior human decision, and data/raw remain unchanged. No files are copied, linked, moved, renamed, deleted or repaired.', '']
    return '\n'.join(lines)


def run_proposal(repository: Path, output: Path | None = None, config: Path | None = None) -> dict[str, Any]:
    repository = repository.resolve()
    audit = repository/'outputs/validation/gyu_det_v3'
    eda = repository/'outputs/eda/gyu_det_v3'
    output = (output or audit/'baseline_split').resolve()
    config = (config or repository/'configs/data/gyu_det_v3_baseline.yaml').resolve()
    if output != audit/'baseline_split' or config != repository/'configs/data/gyu_det_v3_baseline.yaml':
        raise ValueError('Only designated dry-run output/config paths are allowed')
    inputs = [repository/'data/manifests/gyu_det_v3_raw_manifest.csv', repository/'data/raw/gyu_det/v3/archives/classes.txt',
        audit/'full_validation/image_validation.csv', audit/'full_validation/label_validation.csv',
        audit/'full_validation/validation.json', audit/'orphan_review/final_triage_summary.csv',
        audit/'leakage_review/human_leakage_decisions.csv', audit/'leakage_audit/exact_duplicate_groups.csv',
        audit/'baseline_data_policy.md', eda/'eda_summary.json', eda/'box_measurements.csv']
    hashes = {p.relative_to(repository).as_posix(): hash_file(p) for p in inputs}
    records, groups, texts, boxes, orphan_paths = load_inputs(repository, audit, eda)
    decisions = read_csv(audit/'leakage_review/human_leakage_decisions.csv')
    rows, consistency, handling = proposal(records, groups, texts, decisions)
    assertions = assert_leakage_safe(rows, orphan_paths)
    included = [r for r in rows if r['proposed_included']]
    excluded = [r for r in rows if not r['proposed_included']]
    statistics = split_statistics(rows, boxes)
    summary = dict(status='DRY_RUN_WITH_GROUP_BLOCKERS' if any(r['blocker'] for r in consistency) else 'DRY_RUN_READY_FOR_REVIEW',
        raw_images=len(rows), baseline_eligible_before_handling=sum(r['baseline_eligible'] for r in rows),
        equivalent_duplicate_groups=sum(r['annotation_consistency'] in ('IDENTICAL_ANNOTATIONS', 'REORDERED_EQUIVALENT_ANNOTATIONS') for r in consistency),
        conflicting_duplicate_groups=sum(r['blocker'] for r in consistency), orphan_labels_excluded=len(orphan_paths),
        proposed_images_by_split={s: sum(r['processed_split'] == s for r in included) for s in SPLITS},
        excluded_images=len(excluded), excluded_by_reason=dict(sorted(Counter(r['exclusion_reason'] for r in excluded).items())),
        assertions=assertions, source_sha256={p.name: hash_file(p) for p in (Path(__file__), repository/'scripts/data/propose_gyu_baseline_split.py')},
        input_sha256=hashes, materialized=False, m1_complete=False)
    if hashes != {p.relative_to(repository).as_posix(): hash_file(p) for p in inputs}:
        raise ValueError('An input artifact changed during proposal generation')
    summary['input_artifacts_unchanged'] = True
    output.mkdir(parents=True, exist_ok=True)
    config.parent.mkdir(parents=True, exist_ok=True)
    csv_write(output/'duplicate_annotation_consistency.csv', consistency)
    csv_write(output/'baseline_eligibility.csv', rows)
    csv_write(output/'same_scene_group_handling.csv', handling)
    for split in (*SPLITS, 'excluded'):
        source = excluded if split == 'excluded' else [r for r in included if r['processed_split'] == split]
        converted = []
        for row in source:
            copy = dict(row, duplicate_group_id=row['exact_duplicate_group_id'])
            converted.append({f: copy[f] for f in MANIFEST_FIELDS})
        csv_write(output/(split+'_manifest.csv'), converted, MANIFEST_FIELDS)
    orphan_rows = [dict(label_relative_path=p, exclusion_reason='ORPHAN_LABEL_NO_CONFIRMED_MAPPING') for p in sorted(orphan_paths)]
    csv_write(output/'excluded_orphan_labels.csv', orphan_rows, ['label_relative_path', 'exclusion_reason'])
    for name, table in statistics.items():
        csv_write(output/(name+'.csv'), table, ['raw_split', 'exclusion_reason', 'images'] if name == 'exclusion_summary' else None)
    csv_write(output/'class_name_mapping.csv', [dict(class_id=c, raw_source_name=raw, proposed_presentation_name=DISPLAY[c]) for c, raw in enumerate(CLASSES)])
    (output/'baseline_split_policy.md').write_text(policy_text(summary, consistency, handling), encoding='utf-8')
    config.write_text('# DRY RUN ONLY: future dataset/list paths below DO NOT exist yet.\n'
        '# This proposal does not authorize materialization or model training.\n'
        '# Resolve path relative to repository root when future materialization is approved.\n'
        '# Standard YOLO dataset loaders do not enforce the aegisinspect metadata flags.\n'
        'path: data/processed/gyu_det_v3_baseline\ntrain: train.txt\nval: valid.txt\ntest: test.txt\nnc: 6\nnames:\n'+
        ''.join(f'  {c}: {json.dumps(name)}\n' for c, name in enumerate(DISPLAY))+
        'aegisinspect:\n  proposal_only: true\n  materialized: false\n  training_authorized: false\n'
        '  raw_class_ids_unchanged: true\n  source_class_names:\n'+
        ''.join(f'    {c}: {json.dumps(name)}\n' for c, name in enumerate(CLASSES)), encoding='utf-8')
    names = sorted(p.name for p in output.glob('*') if p.is_file() and p.name not in ('proposal_summary.json', 'output_inventory.csv'))
    summary['generated_paths'] = [str(output/p) for p in names+['proposal_summary.json', 'output_inventory.csv']]+[str(config)]
    (output/'proposal_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    csv_write(output/'output_inventory.csv', [dict(path=p) for p in summary['generated_paths']])
    return summary
