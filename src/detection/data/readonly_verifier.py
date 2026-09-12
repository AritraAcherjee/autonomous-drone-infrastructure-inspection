"""Consume approved metadata without stock YOLODataset verification or caching."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from data.validators.gyu_baseline_v1 import EXPECTED_COUNTS, LIST_DIR, MANIFEST_DIR, YAML_PATH, resolve_label, resolve_list_entry, yaml_data
from data.validators.gyu_full_validation import validate_label
from detection.data.raw_guard import canonical, inside

CLASSES = ['Crack', 'Breakage', 'Honeycombing', 'Hole', 'Exposed Reinforcement', 'Seepage']


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def load_approved(root: Path) -> tuple[dict, list[dict]]:
    import yaml
    config = yaml.safe_load((root / YAML_PATH).read_text(encoding='utf-8'))
    if config != yaml_data():
        raise ValueError('Dataset YAML differs from approved paths or exact six-class mapping')
    records, seen_images, seen_labels, seen_hashes = [], set(), set(), set()
    excluded = {canonical(root / r['image_relative_path']) for r in read_csv(root / MANIFEST_DIR / 'excluded.csv')}
    orphans = {canonical(root / r['label_relative_path']) for r in read_csv(root / MANIFEST_DIR / 'excluded_orphan_labels.csv')}
    for split, count in EXPECTED_COUNTS.items():
        key = 'val' if split == 'valid' else split
        listing = (root / YAML_PATH).parent / config[key]
        if listing.resolve() != (root / LIST_DIR / f'{split}.txt').resolve():
            raise ValueError(f'Unapproved split list: {listing}')
        lines = listing.read_text(encoding='utf-8').splitlines()
        rows = read_csv(root / MANIFEST_DIR / f'{split}.csv')
        if len(lines) != count or len(rows) != count:
            raise ValueError(f'{split}: expected exactly {count} list and manifest rows')
        by_image = {canonical(root / r['image_relative_path']): r for r in rows}
        if len(by_image) != len(rows):
            raise ValueError(f'{split}: duplicate manifest image')
        for line in lines:
            image = resolve_list_entry(listing, line)
            image_key = canonical(image)
            row = by_image.get(image_key)
            if row is None or image_key in seen_images or image_key in excluded:
                raise ValueError(f'Duplicate, excluded or unapproved image: {image}')
            label = resolve_label(image)
            label_key = canonical(label)
            if (label_key != canonical(root / row['label_relative_path']) or label_key in orphans
                    or label_key in seen_labels or row['processed_split'] != split):
                raise ValueError(f'Invalid image-label association: {image}')
            if not inside(image, root / 'data/raw') or not inside(label, root / 'data/raw'):
                raise ValueError(f'Association escapes raw: {image}')
            if row['image_sha256'] in seen_hashes:
                raise ValueError(f'Duplicate source-content hash: {image}')
            seen_images.add(image_key)
            seen_labels.add(label_key)
            seen_hashes.add(row['image_sha256'])
            records.append(dict(row, split=split, image=image, label=label))
    return config, records


def decode(path: Path, reader, backend: str) -> dict:
    """Call the installed BaseDataset reader directly, without dataset mutation."""
    result = dict(decode_success=False, width=None, height=None, channels=None,
                  reader_backend=backend, error='')
    try:
        image = reader(str(path))
        if image is None or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) <= 0:
            raise ValueError('Reader returned no valid three-channel color image')
        result.update(decode_success=True, height=int(image.shape[0]), width=int(image.shape[1]), channels=int(image.shape[2]))
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    return result


def verify_label(record: dict) -> dict:
    # Existing M1 parser is read-only and retains <=1e-6 corner overshoots.
    checked = validate_label(record['label'], CLASSES)
    errors = [i for i in checked['issues'] if i['severity'] == 'error']
    if checked['annotation_count'] != int(record['annotation_count']):
        errors.append({'detail': 'Annotation count differs from approved manifest'})
    if checked['class_ids'] != json.loads(record['class_ids']):
        errors.append({'detail': 'Class IDs differ from approved manifest'})
    return dict(split=record['split'], image_path=record['image_relative_path'],
                label_path=record['label_relative_path'], success=not errors,
                annotations=checked['annotation_count'], class_ids=checked['class_ids'],
                warnings=[i for i in checked['issues'] if i['severity'] == 'warning'],
                errors=errors, label_sha256=checked['label_sha256'])
