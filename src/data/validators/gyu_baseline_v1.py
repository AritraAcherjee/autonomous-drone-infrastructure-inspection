"""Finalize approved baseline-v1 metadata and portable lists, without materializing samples."""
from __future__ import annotations

import importlib.util
import json
import os
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from data.validators.gyu_baseline_split import (CLASSES, DISPLAY, MANIFEST_FIELDS, SPLITS,
    assert_leakage_safe, csv_write, hash_file, load_inputs, split_statistics)
from data.validators.gyu_orphan_review import read_csv

MANIFEST_DIR = Path('data/manifests/gyu_det_v3_baseline_v1')
LIST_DIR = Path('data/processed/gyu_det_v3_baseline_v1/splits')
YAML_PATH = Path('configs/data/gyu_det_v3_baseline_v1.yaml')
DOC_PATH = Path('docs/data/gyu_det_v3_baseline_v1.md')
EXPECTED_COUNTS = {'train': 8305, 'valid': 1040, 'test': 1053}
CONFLICTS = {('train', n) for n in ('4476.JPG', '4631.JPG', '3852.JPG', '4263.JPG', '139.JPG', '183.JPG')} | {
    ('valid', n) for n in ('9228.jpg', '9229.jpg', '9219.jpg', '9220.jpg')}
REDUNDANT = {('train', '11150.jpg'), ('train', '9838.jpg')}
CONSERVATIVE = {('train', '11334.jpg')}
POLICY_VERSION = 'human-approved-baseline-v1-policy-1'
APPROVED_CONFLICT_REASON = 'APPROVED_BASELINE_V1_CONFLICT_GROUP_EXCLUSION'


def identity(row: dict[str, Any]) -> tuple[str, str]:
    return row['raw_split'], PurePosixPath(row['image_relative_path']).name


def image_list_entry(image_relative_path: str) -> str:
    path = PurePosixPath(image_relative_path)
    if path.is_absolute() or '..' in path.parts or path.parts[:2] != ('data', 'raw'):
        raise ValueError('Image must have a repository-relative raw path')
    # The list lives at data/processed/<spec>/splits: ../../../ returns to data/.
    return './../../../' + '/'.join(path.parts[1:])


def resolve_list_entry(list_file: Path, line: str) -> Path:
    if not line.startswith('./') or '\\' in line:
        raise ValueError('Expected portable list-local ./ path with forward slashes')
    return (list_file.parent / line[2:]).resolve()


def resolve_label(image: Path) -> Path:
    """Equivalent to Ultralytics img2label_paths: last /images/ -> /labels/, suffix -> .txt."""
    parts = list(image.parts)
    try:
        index = max(i for i, part in enumerate(parts[:-1]) if part == 'images')
    except ValueError as exc:
        raise ValueError('No images directory segment') from exc
    parts[index] = 'labels'
    return Path(*parts).with_suffix('.txt')


def yaml_data() -> dict[str, Any]:
    # JSON syntax is valid YAML 1.2; this avoids adding a YAML dependency to finalization.
    return {'train': '../../'+(LIST_DIR/'train.txt').as_posix(),
            'val': '../../'+(LIST_DIR/'valid.txt').as_posix(),
            'test': '../../'+(LIST_DIR/'test.txt').as_posix(),
            'nc': 6, 'names': {str(i): n for i, n in enumerate(DISPLAY)}}


def validate_approved(rows: list[dict[str, Any]], orphan_paths: set[str],
                      expected_counts: dict[str, int] = EXPECTED_COUNTS) -> dict[str, bool]:
    included = [r for r in rows if r['proposed_included']]
    if {s: sum(r['processed_split'] == s for r in included) for s in SPLITS} != expected_counts:
        raise ValueError('Approved split counts differ; stop for human review')
    if len(included) != sum(expected_counts.values()):
        raise ValueError('Total included count differs')
    if any(identity(r) in CONFLICTS | REDUNDANT | CONSERVATIVE for r in included):
        raise ValueError('An approved exclusion was included')
    checks = assert_leakage_safe(rows, orphan_paths)
    checks.update(no_conflicting_duplicates=True, approved_counts=True)
    return checks


def prepared_rows(repository: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]], set[str], dict[str, str]]:
    audit = repository/'outputs/validation/gyu_det_v3'
    proposal = audit/'baseline_split'
    summary = json.loads((proposal/'proposal_summary.json').read_text(encoding='utf-8'))
    for relative, digest in summary['input_sha256'].items():
        if hash_file(repository/relative) != digest:
            raise ValueError(f'Approved proposal input changed: {relative}')
    records, _, _, boxes, orphan_paths = load_inputs(repository, audit, repository/'outputs/eda/gyu_det_v3')
    previous = read_csv(proposal/'baseline_eligibility.csv')
    by_path = {r['image_relative_path']: r for r in previous}
    if len(by_path) != len(previous) or set(by_path) != set(records):
        raise ValueError('Proposal/raw inventory mismatch')
    manifests = [r for name in (*SPLITS, 'excluded') for r in read_csv(proposal/(name+'_manifest.csv'))]
    if len(manifests) != len(records) or {r['image_relative_path'] for r in manifests} != set(records):
        raise ValueError('Dry-run manifests are not a partition of raw images')
    rows = []
    for old in sorted(manifests, key=lambda r: r['image_relative_path']):
        p = old['image_relative_path']
        raw = records[p]
        eligibility = by_path[p]
        for field in ('raw_split', 'label_relative_path', 'image_sha256', 'class_ids'):
            if old[field] != raw[field]:
                raise ValueError(f'Approved row differs from validated raw manifest: {p}/{field}')
        if old['annotation_count'] != (str(raw['annotation_count']) if raw['annotation_count'] is not None else ''):
            raise ValueError('Annotation count mismatch')
        if old['processed_split'] != eligibility['processed_split'] or old['exclusion_reason'] != eligibility['exclusion_reason']:
            raise ValueError('Dry-run manifest/eligibility disagreement')
        if old['leakage_group_id'] != eligibility['leakage_group_id']:
            raise ValueError('Leakage group mismatch')
        reason = old['exclusion_reason']
        ident = identity(old)
        if ident in CONFLICTS:
            if reason != 'ANNOTATION_CONFLICT_HUMAN_REVIEW_REQUIRED':
                raise ValueError('Conflict exclusion differs from approval')
            reason = APPROVED_CONFLICT_REASON
        elif ident in REDUNDANT:
            if reason != 'EQUIVALENT_EXACT_DUPLICATE_REDUNDANT':
                raise ValueError('Equivalent duplicate exclusion differs from approval')
        elif ident in CONSERVATIVE:
            if reason != 'APPROVED_LEAKAGE_GROUP_OTHER_SPLIT_RETAINED':
                raise ValueError('Conservative exclusion differs from approval')
        elif not raw['baseline_eligible']:
            if reason != 'UNLABELED_UNCLASSIFIED':
                raise ValueError('Unexpected eligibility exclusion')
        elif reason:
            raise ValueError('An unapproved exclusion was found')
        rows.append(dict(raw, **{k: v for k, v in old.items() if k not in raw},
                         proposed_included=bool(old['processed_split']),
                         exact_duplicate_group_id=old['duplicate_group_id']))
        rows[-1]['exclusion_reason'] = reason
    if len(rows) != 11123 or sum(r['baseline_eligible'] for r in rows) != 10411 or len(orphan_paths) != 21:
        raise ValueError('Approved starting inventory counts changed')
    excluded = Counter(r['exclusion_reason'] for r in rows if not r['proposed_included'])
    if excluded != Counter({APPROVED_CONFLICT_REASON: 10, 'EQUIVALENT_EXACT_DUPLICATE_REDUNDANT': 2,
                            'APPROVED_LEAKAGE_GROUP_OTHER_SPLIT_RETAINED': 1, 'UNLABELED_UNCLASSIFIED': 712}):
        raise ValueError('Approved exclusion totals changed')
    # Independently enforce the approved human edges, not just group IDs supplied in a CSV.
    lookup = {identity(r): r for r in rows}
    for edge in read_csv(audit/'leakage_review/human_leakage_decisions.csv'):
        if edge['human_outcome'] == 'REJECT_LEAKAGE_CANDIDATE':
            continue
        a, b = [lookup[(edge['split_'+side], edge['image_'+side])] for side in ('a', 'b')]
        if a['proposed_included'] and b['proposed_included'] and a['processed_split'] != b['processed_split']:
            raise ValueError('Approved human leakage edge crosses final splits')
    hashes = dict(summary['input_sha256'])
    for p in proposal.glob('*'):
        if p.is_file():
            hashes[p.relative_to(repository).as_posix()] = hash_file(p)
    return rows, boxes, orphan_paths, hashes


def verify_lists(repository: Path, rows: list[dict[str, Any]], lists: dict[str, str]) -> int:
    verified = 0
    for split in SPLITS:
        members = [r for r in rows if r['proposed_included'] and r['processed_split'] == split]
        entries = lists[split].splitlines()
        if len(entries) != len(members) or len(set(entries)) != len(entries):
            raise ValueError('List count or uniqueness mismatch')
        for row, line in zip(members, entries):
            image = resolve_list_entry(repository/LIST_DIR/(split+'.txt'), line)
            expected_image = (repository/row['image_relative_path']).resolve()
            expected_label = (repository/row['label_relative_path']).resolve()
            if image != expected_image or resolve_label(image) != expected_label:
                raise ValueError('YOLO image/label resolution differs from manifest')
            if not image.is_file() or not expected_label.is_file():
                raise ValueError('Included image or label is missing')
            # Exact case spelling as well as path identity matters for portability to Linux.
            if expected_label.name != image.stem+'.txt':
                raise ValueError('Label filename would not resolve portably')
            verified += 1
    for key, split in [('train', 'train'), ('val', 'valid'), ('test', 'test')]:
        actual = ((repository/YAML_PATH).parent/yaml_data()[key]).resolve()
        if actual != (repository/LIST_DIR/(split+'.txt')).resolve():
            raise ValueError('YAML/list path mismatch')
    return verified


def documentation() -> str:
    return '''# Approved GYU-DET baseline-v1 split specification

Baseline-v1 is a detector-training dataset specification, not a modification of the source dataset. It contains manifests and image-reference lists only. No images or labels are copied, linked, rewritten or repaired. M1 remains incomplete; no model has been trained.

## Approved inventory and exclusions

Raw GYU-DET v3 contains 11,123 images and 10,432 label files: 10,411 exact pairs, 712 unlabeled/unclassified images and 21 orphan labels. Baseline-v1 retains 10,398 supervised samples: train 8,305; valid 1,040; test 1,053, with 48,392 annotations. Every included image preserves its original split.

The 725 excluded raw images comprise 712 UNCLASSIFIED images, ten members of five conflicting-annotation exact-duplicate groups, two redundant equivalent duplicates and one image excluded for the conservative scene constraint. All 21 orphan labels are excluded separately; confirmed mappings remain zero. No negative identities are inferred from the published 691 total or from absent labels.

The human approves excluding both members of each conflict group for baseline-v1: train 4476.JPG/4631.JPG, 3852.JPG/4263.JPG, 139.JPG/183.JPG; valid 9228.jpg/9229.jpg, 9219.jpg/9220.jpg. These groups are resolved for baseline-v1 by exclusion, not annotation adjudication. No annotation is selected as better, merged or transferred. The original duplicate_annotation_consistency.csv under outputs/validation/gyu_det_v3/baseline_split remains unchanged for future study. The finalized exclusion reason explicitly records the approval; the dry-run evidence remains historical.

Equivalent duplicates retain train/10245.jpg and valid/11989.jpg; train/11150.jpg and train/9838.jpg are excluded. The conservative unresolved group retains test/12582.jpg and excludes train/11334.jpg; it is still not confirmed leakage. train/11727.jpg is retained, while valid/11985.jpg remains excluded/unclassified. Approved scene groups and SHA-identical content cannot cross retained splits. No labels are transferred. Rejected perceptual candidates introduce no grouping constraints.

## Warning and class policy

Readable primary images with MPO auxiliary-frame warnings remain eligible. The prior full validation reported 565 such raw-image warnings. Boundary overshoots <=1e-6 remain rounding warnings and are not clipped. The raw class IDs remain unchanged:

| ID | Source name | Presentation name |
|---:|---|---|
| 0 | Crack | Crack |
| 1 | Breakage | Breakage |
| 2 | Comb | Honeycombing |
| 3 | Hole | Hole |
| 4 | Reinforcement | Exposed Reinforcement |
| 5 | Seepage | Seepage |

## Portable reader paths

List entries use forward slashes and start with ./../../../raw/, relative to data/processed/gyu_det_v3_baseline_v1/splits/. This list-local representation remains valid after relocating the whole repository. Each resolves into the original raw images directory. The sibling labels path replaces the last images directory segment with labels and uses the exact image stem plus .txt. All 10,398 associations are asserted against the validated manifest, including case-preserved filenames.

The YAML uses JSON syntax, a valid YAML subset, and deliberately omits path. Its train/val/test entries are relative to the YAML directory. Pass an ABSOLUTE YAML filename to the planned Ultralytics workflow (e.g. str(Path('configs/data/gyu_det_v3_baseline_v1.yaml').resolve()) from the repository). This avoids dependence on global dataset-directory settings. Numeric IDs are retained through the names mapping. No download directive or model reference is present.

Reader semantics were checked against official [list loading](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/data/base.py) and [label/path resolution](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/data/utils.py). The equivalent assertions do not claim that the actual Ultralytics dataset decoder has run. Its installed/not-installed smoke-test result is recorded in manifest_metadata.json. Image hashes and box statistics are reused from validated artifacts; all paired label hashes are checked read-only before finalization.

## Reproduction and remaining training prerequisites

Run from the existing repository:

```powershell
python scripts/data/finalize_gyu_baseline_v1.py
python scripts/data/finalize_gyu_baseline_v1.py --check-reproducibility
python -m unittest discover -s tests/data -v
```

The reproducibility check writes metadata-only trees in two clean temporary directories and compares every byte. VERSION.json records source/final manifest hashes, the policy version, class mapping, exclusions and leakage constraints. No timestamps or machine-specific absolute paths enter the reproducible specification.

The conflict exclusions no longer block baseline-v1 approval. Before actual detector training, validate the selected installed reader, particularly MPO primary decoding, and ensure its cache/verification behavior cannot write into data/raw. Standard training-reader verification can create label caches or attempt image repair; a read-only raw mount or an explicitly controlled reader/cache policy is required for that later workflow. This task does not run that workflow, download weights or install Ultralytics. Source-image hashes are reused rather than re-reading the full image dataset. Unclassified-image and orphan limitations remain documented; those samples stay outside this supervised baseline. All prior human decisions and raw files remain immutable.
'''


def emit(repository: Path, destination: Path, rows: list[dict[str, Any]], boxes: list[dict[str, str]],
         orphan_paths: set[str], hashes: dict[str, str], smoke: dict[str, Any]) -> list[Path]:
    checks = validate_approved(rows, orphan_paths)
    lists = {s: ''.join(image_list_entry(r['image_relative_path'])+'\n' for r in rows
                       if r['proposed_included'] and r['processed_split'] == s) for s in SPLITS}
    checks['label_resolution_count'] = verify_lists(repository, rows, lists)
    outputs: list[Path] = []

    def write(relative: Path, content: str) -> None:
        path = destination/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='\n')
        outputs.append(relative)

    def table(relative: Path, records: list[dict[str, Any]], fields: list[str] | None = None) -> None:
        path = destination/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        csv_write(path, records, fields)
        outputs.append(relative)

    for split in (*SPLITS, 'excluded'):
        selected = [r for r in rows if (not r['proposed_included'] if split == 'excluded' else
                                       r['proposed_included'] and r['processed_split'] == split)]
        table(MANIFEST_DIR/(split+'.csv'), [{k: r[k] for k in MANIFEST_FIELDS} for r in selected], MANIFEST_FIELDS)
    table(MANIFEST_DIR/'excluded_orphan_labels.csv', [dict(label_relative_path=p, exclusion_reason='ORPHAN_LABEL_NO_CONFIRMED_MAPPING') for p in sorted(orphan_paths)])
    statistics = split_statistics(rows, boxes)
    table(MANIFEST_DIR/'split_statistics.csv', [{k: v for k, v in r.items() if k != 'view'} for r in statistics['split_statistics'] if r['view'] == 'DRY_RUN_PROPOSED'])
    table(MANIFEST_DIR/'class_statistics.csv', [{k: v for k, v in r.items() if k != 'view'} for r in statistics['split_class_distribution'] if r['view'] == 'DRY_RUN_PROPOSED'])
    for split, text in lists.items():
        write(LIST_DIR/(split+'.txt'), text)
    write(YAML_PATH, json.dumps(yaml_data(), indent=2)+'\n')
    write(DOC_PATH, documentation())
    exclusions = dict(sorted(Counter(r['exclusion_reason'] for r in rows if not r['proposed_included']).items()))
    version = dict(dataset='GYU-DET', source_version='v3', processed_specification_version='baseline-v1',
        creation_policy_version=POLICY_VERSION, source_manifest_sha256=hashes['data/manifests/gyu_det_v3_raw_manifest.csv'],
        manifest_sha256={s: hash_file(destination/MANIFEST_DIR/(s+'.csv')) for s in SPLITS},
        class_mapping=[dict(id=i, raw_source_name=n, canonical_display_name=DISPLAY[i]) for i, n in enumerate(CLASSES)],
        exclusions_summary=exclusions, orphan_labels_excluded=21,
        leakage_constraints_summary={'exact': 'retain valid/11989.jpg; exclude train/9838.jpg',
            'high_confidence': 'retain train/11727.jpg; valid/11985.jpg stays unlabeled/excluded',
            'conservative_unresolved': 'retain test/12582.jpg; exclude train/11334.jpg; not confirmed leakage'},
        approved_conflict_exclusions=[f'{s}/{n}' for s, n in sorted(CONFLICTS)])
    write(MANIFEST_DIR/'VERSION.json', json.dumps(version, indent=2, sort_keys=True)+'\n')
    metadata = dict(status='APPROVED_BASELINE_V1_SPECIFICATION', human_conflict_policy_authorized=True,
        conflict_groups_resolved_for_baseline_v1_only=True, raw_samples_materialized=False, training_performed=False, m1_complete=False,
        image_counts=EXPECTED_COUNTS, supervised_images=10398, annotation_instances=sum(r['annotation_count'] for r in rows if r['proposed_included']),
        assertions=checks, smoke_test=smoke, input_sha256=hashes,
        source_sha256={p.name: hash_file(p) for p in (Path(__file__), repository/'scripts/data/finalize_gyu_baseline_v1.py')},
        artifact_sha256={p.as_posix(): hash_file(destination/p) for p in outputs},
        outputs=[p.as_posix() for p in outputs]+[(MANIFEST_DIR/'manifest_metadata.json').as_posix()])
    write(MANIFEST_DIR/'manifest_metadata.json', json.dumps(metadata, indent=2, sort_keys=True)+'\n')
    return outputs


def finalize(repository: Path, check_reproducibility: bool = False) -> dict[str, Any]:
    import tempfile
    repository = repository.resolve()
    rows, boxes, orphan_paths, hashes = prepared_rows(repository)
    validate_approved(rows, orphan_paths)
    smoke: dict[str, Any] = {'status': 'skipped', 'reason': 'Ultralytics is not installed; not installed for this task. Equivalent path/label assertions cover all 10398 included images.'}
    if importlib.util.find_spec('ultralytics') is not None:
        # Exercise actual list loading/label mapping only: no dataset verification, caching, transforms, weights or training.
        from types import SimpleNamespace
        from ultralytics.data.base import BaseDataset
        from ultralytics.data.utils import img2label_paths
        with tempfile.TemporaryDirectory() as folder:
            for split in SPLITS:
                members = [r for r in rows if r['proposed_included'] and r['processed_split'] == split]
                path = Path(folder)/(split+'.txt')
                path.write_text(''.join(str((repository/r['image_relative_path']).resolve())+'\n' for r in members), encoding='utf-8')
                images = BaseDataset.get_img_files(SimpleNamespace(fraction=1.0, prefix='baseline-v1 smoke: '), str(path))
                expected = {str((repository/r['label_relative_path']).resolve()) for r in members}
                if set(img2label_paths(images)) != expected:
                    raise ValueError('Installed Ultralytics label-resolution smoke test failed')
        smoke = {'status': 'passed', 'scope': 'Installed BaseDataset list loading and img2label_paths only; no decoding, verification cache, augmentation or training.'}
    if check_reproducibility:
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            paths = emit(repository, Path(one), rows, boxes, orphan_paths, hashes, smoke)
            other = emit(repository, Path(two), rows, boxes, orphan_paths, hashes, smoke)
            if paths != other or any((Path(one)/p).read_bytes() != (Path(two)/p).read_bytes() for p in paths):
                raise ValueError('Clean-output reproducibility failure')
    else:
        emit(repository, repository, rows, boxes, orphan_paths, hashes, smoke)
    for relative, expected in hashes.items():
        if hash_file(repository/relative) != expected:
            raise ValueError(f'Protected input changed during finalization: {relative}')
    return dict(image_counts=EXPECTED_COUNTS, supervised_images=10398,
        annotations=sum(r['annotation_count'] for r in rows if r['proposed_included']),
        excluded=dict(sorted(Counter(r['exclusion_reason'] for r in rows if not r['proposed_included']).items())),
        orphan_labels_excluded=len(orphan_paths), smoke_test=smoke,
        clean_reproducibility='passed' if check_reproducibility else 'not requested', input_artifacts_unchanged=True)
