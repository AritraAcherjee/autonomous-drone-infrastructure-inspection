"""Versioned mappings; unmapped and unapproved semantics are never guessed."""
from .schema import CLASSES, nonempty, require


POLICIES = {
    'CODEBRIM': {
        'version': 'gyu-codebrim-v1-approved',
        'approved_targets': {
            0: 'Crack',
            1: 'Spallation',
            4: 'ExposedBars',
        },
        'external_only': {
            'Efflorescence',
            'CorrosionStain',
        },
        'aggregate_label': 'shared-class CODEBRIM mAP',
    },
    'DamSegment': {
        'version': 'gyu-damsegment-v1-approved',
        'approved_targets': {
            0: 'Crack',
            1: 'Spalling',
        },
        'external_only': set(),
        'aggregate_label': 'shared-class DamSegment mAP',
    },
}

# Backward compatibility for the already-frozen CODEBRIM crosswalk.
LEGACY_VERSION_DATASET = {
    'gyu-codebrim-v1-approved': 'CODEBRIM',
}

# Existing unit/synthetic infrastructure predates external_dataset.
# It is accepted only outside an explicitly identified external
# scientific-dataset context.
SYNTHETIC_TEST_VERSION_DATASET = {
    'synthetic-v1': 'CODEBRIM',
}


def crosswalk_dataset(c, expected_dataset=None):
    require(isinstance(c, dict), 'Crosswalk must be an object')
    require(nonempty(c.get('version')), 'Missing ontology version')

    version = c.get('version')
    dataset = c.get('external_dataset')

    if dataset is None:
        dataset = LEGACY_VERSION_DATASET.get(version)

        if dataset is None and expected_dataset is None:
            dataset = SYNTHETIC_TEST_VERSION_DATASET.get(version)

        require(
            dataset in POLICIES,
            'Unknown legacy ontology version',
        )

        return dataset

    require(
        dataset in POLICIES,
        'Unknown external ontology dataset',
    )

    policy = POLICIES[dataset]

    require(
        version == policy['version'],
        'Ontology version/dataset mismatch',
    )

    return dataset


def validate_crosswalk(c, expected_dataset=None):
    dataset = crosswalk_dataset(
        c,
        expected_dataset=expected_dataset,
    )
    policy = POLICIES[dataset]

    if expected_dataset is not None:
        require(
            dataset == expected_dataset,
            'Ontology dataset does not match experiment dataset',
        )

    require(
        c.get('gyu_classes') == {
            str(k): v for k, v in CLASSES.items()
        },
        'Unexpected GYU ontology',
    )

    rows = c.get('mappings', [])

    require(
        len(rows) == 6
        and {r.get('gyu_id') for r in rows} == set(CLASSES),
        'One mapping per GYU class required',
    )

    targets = []

    for row in rows:
        require(
            row.get('status') in (
                'candidate',
                'approved',
                'unmapped',
            ),
            'Invalid mapping status',
        )

        if row['status'] == 'unmapped':
            require(
                row.get('external_label') is None,
                'Unmapped class must not have target',
            )
        else:
            require(
                nonempty(row.get('external_label')),
                'Missing external label',
            )

            targets.append(row['external_label'])

        if row['status'] == 'approved':
            require(
                nonempty(row.get('approval')),
                'Approved mapping requires review reference',
            )

    require(
        len(set(targets)) == len(targets),
        'Ambiguous external target',
    )

    external_only = set(c.get('external_only', []))

    require(
        external_only == policy['external_only'],
        'External-only classes differ from approved policy',
    )

    require(
        not set(targets).intersection(external_only),
        'External-only labels cannot be mapping targets',
    )

    for row in rows:
        if row['status'] != 'unmapped':
            require(
                policy['approved_targets'].get(
                    row['gyu_id']
                ) == row['external_label'],
                'Unapproved semantic mapping',
            )

    aggregate = c.get('external_aggregate_label')

    # Frozen/new crosswalks require the explicit aggregate label.
    # Legacy synthetic CODEBRIM fixtures did not carry this field.
    if c.get('external_dataset') is not None or aggregate is not None:
        require(
            aggregate == policy['aggregate_label'],
            'External aggregate label differs from approved policy',
        )

    return c


def shared_classes(c):
    validate_crosswalk(c)

    return sorted(
        row['gyu_id']
        for row in c['mappings']
        if row['status'] == 'approved'
    )


def scored_classes(dataset_identity, c):
    """Choose scientific score classes without dataset-name fallthrough."""
    if dataset_identity == 'GYU-DET':
        return sorted(CLASSES)

    require(
        dataset_identity in POLICIES,
        'Unknown external scoring dataset',
    )

    validate_crosswalk(
        c,
        expected_dataset=dataset_identity,
    )

    classes = shared_classes(c)

    require(
        bool(classes),
        'No approved shared classes',
    )

    return classes


def map_region_labels(labels, c):
    """Return approved GYU IDs plus excluded labels; never duplicate a region."""
    validate_crosswalk(c)

    mapping = {
        row['external_label']: row['gyu_id']
        for row in c['mappings']
        if row['status'] == 'approved'
    }

    known = {
        row['external_label']
        for row in c['mappings']
        if row['external_label'] is not None
    } | set(c['external_only'])

    require(
        all(
            nonempty(label) and label in known
            for label in labels
        ),
        'Unknown external label',
    )

    return (
        sorted({
            mapping[label]
            for label in labels
            if label in mapping
        }),
        sorted(
            set(labels) - set(mapping)
        ),
    )
