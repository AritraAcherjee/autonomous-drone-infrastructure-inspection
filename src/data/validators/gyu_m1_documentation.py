"""Read-only consistency checks for approved GYU-DET artifacts and M1 documentation."""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from data.validators.gyu_baseline_split import hash_file
from data.validators.gyu_baseline_v1 import (CONFLICTS, CONSERVATIVE, REDUNDANT, EXPECTED_COUNTS,
    DISPLAY, LIST_DIR, YAML_PATH, resolve_list_entry, resolve_label)
from data.validators.gyu_orphan_review import read_csv

MD5 = {'classes.txt': 'F078630BF0D0614B07C9DC990DA40801', 'test.zip': '522A80C18CAA4A0030D7FFC9DDFA98B2',
       'train.zip': 'A8AAD1CC02E86C4857B8315EE9F1606E', 'valid.zip': 'D8EBE9C38D9D4D05DD9CFFB50A692086'}
REQUIRED = ('dataset dataset_version official_repository dataset_doi paper_doi dataset_license paper_license '
    'source_archive_files source_archive_md5 raw_local_root raw_image_count raw_label_count exact_pair_count '
    'unlabeled_image_count orphan_label_count source_classes annotation_format raw_split_names '
    'baseline_specification_version source_manifest_sha256 baseline_train_manifest_sha256 '
    'baseline_valid_manifest_sha256 baseline_test_manifest_sha256 raw_data_modified').split()


def validate_provenance(data: dict[str, Any]) -> None:
    if set(REQUIRED)-data.keys():
        raise ValueError('Missing provenance fields')
    if data['source_archive_md5'] != MD5:
        raise ValueError('Source acquisition MD5 values differ from verified V3 values')
    if data['dataset_license'] != 'CC BY-NC-SA 4.0' or data['paper_license'] != 'CC BY-NC-ND 4.0':
        raise ValueError('Dataset/article license mismatch')
    if data['raw_data_modified'] is not False:
        raise ValueError('raw_data_modified must be false')


def check_approved(repository: Path) -> dict[str, Any]:
    root = repository.resolve()
    directory = root/'data/manifests/gyu_det_v3_baseline_v1'
    version = json.loads((directory/'VERSION.json').read_text(encoding='utf-8'))
    metadata = json.loads((directory/'manifest_metadata.json').read_text(encoding='utf-8'))
    for relative, expected in metadata['artifact_sha256'].items():
        if hash_file(root/relative) != expected:
            raise ValueError(f'Approved artifact hash mismatch: {relative}; STOP, do not regenerate')
    if hash_file(root/'data/manifests/gyu_det_v3_raw_manifest.csv') != version['source_manifest_sha256']:
        raise ValueError('Source manifest hash mismatch')
    raw = {r['image_relative_path']: r for r in read_csv(root/'data/manifests/gyu_det_v3_raw_manifest.csv')}
    orphans = {r['label_relative_path'] for r in read_csv(directory/'excluded_orphan_labels.csv')}
    counts, all_rows, labels_checked = {}, [], 0
    for split, expected in EXPECTED_COUNTS.items():
        path = directory/(split+'.csv')
        if hash_file(path) != version['manifest_sha256'][split]:
            raise ValueError(f'VERSION manifest hash mismatch: {split}')
        rows = read_csv(path)
        if len(rows) != expected:
            raise ValueError(f'Count mismatch: {split}')
        counts[split] = len(rows)
        entries = (root/LIST_DIR/(split+'.txt')).read_text(encoding='utf-8').splitlines()
        if len(entries) != len(rows) or len(set(entries)) != len(entries):
            raise ValueError('List count/uniqueness mismatch')
        for r, entry in zip(rows, entries):
            source = raw[r['image_relative_path']]
            if source['pairing_status'] != 'exact_pair' or r['label_relative_path'] in orphans:
                raise ValueError('Unlabeled or orphan annotation included')
            for field in ('label_relative_path', 'image_sha256', 'annotation_count', 'class_ids'):
                if r[field] != source[field]:
                    raise ValueError(f'Included row/source mismatch: {field}')
            if r['processed_split'] != split or r['raw_split'] != source['split'] or r['raw_split'] != split:
                raise ValueError('Approved split mismatch')
            image = resolve_list_entry(root/LIST_DIR/(split+'.txt'), entry)
            if image != (root/r['image_relative_path']).resolve() or not image.is_file():
                raise ValueError('Image list resolution failure')
            label = resolve_label(image)
            if label != (root/r['label_relative_path']).resolve() or not label.is_file():
                raise ValueError('Label resolution failure')
            labels_checked += 1
        all_rows.extend(rows)
    identities = {(r['raw_split'], Path(r['image_relative_path']).name) for r in all_rows}
    if identities & (CONFLICTS | REDUNDANT | CONSERVATIVE):
        raise ValueError('Approved excluded image included')
    for field in ('image_sha256', 'leakage_group_id'):
        groups: dict[str, set[str]] = defaultdict(set)
        for r in all_rows:
            if r[field]:
                groups[r[field]].add(r['processed_split'])
        if any(len(s) > 1 for s in groups.values()):
            raise ValueError(f'Cross-split leakage: {field}')
    lookup = {(r['raw_split'], Path(r['image_relative_path']).name): r for r in all_rows}
    for edge in read_csv(root/'outputs/validation/gyu_det_v3/leakage_review/human_leakage_decisions.csv'):
        if edge['human_outcome'] == 'REJECT_LEAKAGE_CANDIDATE':
            continue
        a, b = [lookup.get((edge['split_'+side], edge['image_'+side])) for side in ('a', 'b')]
        if a and b and a['processed_split'] != b['processed_split']:
            raise ValueError('Approved human constraint crosses splits')
    excluded = read_csv(directory/'excluded.csv')
    if len(excluded) != 725 or len(orphans) != 21 or len(raw) != 11123:
        raise ValueError('Raw/excluded count mismatch')
    if {r['image_relative_path'] for r in all_rows+excluded} != set(raw) or len(all_rows+excluded) != len(raw):
        raise ValueError('Manifest partition mismatch')
    config = json.loads((root/YAML_PATH).read_text(encoding='utf-8'))
    if config['nc'] != 6 or config['names'] != {str(i): n for i, n in enumerate(DISPLAY)}:
        raise ValueError('YAML class mapping mismatch')
    annotations = sum(int(r['annotation_count']) for r in all_rows)
    if len(all_rows) != 10398 or annotations != 48392:
        raise ValueError('Final totals mismatch')
    return dict(status='PASS', image_counts=counts, total_supervised_images=10398, annotations=annotations,
        label_paths_verified=labels_checked, excluded_raw_images=len(excluded), orphan_labels_excluded=len(orphans),
        manifest_sha256=version['manifest_sha256'], source_manifest_sha256=version['source_manifest_sha256'],
        leakage_assertions='PASS', approved_artifact_hashes='PASS', approved_artifacts_modified=False)


def check_documentation(root: Path) -> None:
    provenance = json.loads((root/'data/manifests/gyu_det_v3_source_provenance.json').read_text(encoding='utf-8'))
    validate_provenance(provenance)
    version = json.loads((root/'data/manifests/gyu_det_v3_baseline_v1/VERSION.json').read_text(encoding='utf-8'))
    if provenance['source_manifest_sha256'] != version['source_manifest_sha256']:
        raise ValueError('Provenance source hash mismatch')
    for split in EXPECTED_COUNTS:
        if provenance[f'baseline_{split}_manifest_sha256'] != version['manifest_sha256'][split]:
            raise ValueError('Provenance baseline hash mismatch')
    for r in read_csv(root/'outputs/validation/gyu_det_v3/M1_EVIDENCE_INDEX.csv'):
        if not (root/r['repository_relative_path']).exists():
            raise ValueError(f'Evidence path missing: {r["repository_relative_path"]}')
