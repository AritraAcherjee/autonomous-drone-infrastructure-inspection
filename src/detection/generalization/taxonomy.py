"""Versioned mappings; unmapped and unapproved semantics are never guessed."""
from .schema import CLASSES, nonempty, require


def validate_crosswalk(c):
    require(nonempty(c.get('version')), 'Missing ontology version')
    require(c.get('gyu_classes') == {str(k): v for k, v in CLASSES.items()}, 'Unexpected GYU ontology')
    rows = c.get('mappings', [])
    require(len(rows) == 6 and {r.get('gyu_id') for r in rows} == set(CLASSES), 'One mapping per GYU class required')
    targets = []
    for r in rows:
        require(r.get('status') in ('candidate', 'approved', 'unmapped'), 'Invalid mapping status')
        if r['status'] == 'unmapped':
            require(r.get('external_label') is None, 'Unmapped class must not have target')
        else:
            require(nonempty(r.get('external_label')), 'Missing external label')
            targets.append(r['external_label'])
        if r['status'] == 'approved':
            require(nonempty(r.get('approval')), 'Approved mapping requires review reference')
    require(len(set(targets)) == len(targets), 'Ambiguous external target')
    require(set(c.get('external_only', [])) == {'Efflorescence', 'Corrosion/stain'}, 'External-only classes must be explicit')
    require(not set(targets).intersection(c['external_only']), 'External-only labels cannot be mapping targets')
    return c


def shared_classes(c):
    validate_crosswalk(c)
    return sorted(r['gyu_id'] for r in c['mappings'] if r['status'] == 'approved')


def map_region_labels(labels, c):
    """Return approved GYU IDs plus excluded labels; never duplicate a region."""
    validate_crosswalk(c)
    mapping = {r['external_label']: r['gyu_id'] for r in c['mappings'] if r['status'] == 'approved'}
    known = {r['external_label'] for r in c['mappings']} | set(c['external_only'])
    require(all(nonempty(label) and label in known for label in labels), 'Unknown external label')
    return sorted({mapping[label] for label in labels if label in mapping}), sorted(set(labels) - set(mapping))
