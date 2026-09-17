"""Deterministic DamSegment v1 detection GT preparation.

This module never runs a detector and never modifies source data.
"""
import json
import math
from collections import Counter
from pathlib import Path

from .manifest import canonical, object_hash
from .schema import require, validate_records


EXPECTED_IMAGES = 1500
EXPECTED_REGIONS = 19710
EXPECTED_CLASS_COUNTS = Counter({
    0: 19229,
    1: 481,
})

SOURCE_TO_AEGIS = {
    0: 0,  # Crack -> Crack
    1: 1,  # Spalling -> Breakage
}


def _number(value):
    require(
        type(value) in (int, float),
        'Non-numeric DamSegment coordinate',
    )

    value = float(value)

    require(
        math.isfinite(value),
        'Non-finite DamSegment coordinate',
    )

    if value.is_integer():
        return int(value)

    return value


def build_prepared_inventory(root):
    root = Path(root)

    images_dir = root / 'Images'
    json_dir = root / 'Labels' / 'Pascal VOC'
    yolo_dir = root / 'Labels' / 'Yolo'

    image_paths = sorted(
        images_dir.glob('*.jpg'),
        key=lambda p: p.name.casefold(),
    )

    json_paths = {
        p.stem: p
        for p in json_dir.glob('*.json')
    }

    yolo_paths = {
        p.stem: p
        for p in yolo_dir.glob('*.txt')
    }

    stems = {p.stem for p in image_paths}

    require(
        len(image_paths) == EXPECTED_IMAGES,
        'Unexpected DamSegment image count',
    )

    require(
        stems == set(json_paths),
        'DamSegment image/JSON pairing differs',
    )

    require(
        stems == set(yolo_paths),
        'DamSegment image/YOLO pairing differs',
    )

    images = []
    regions = []
    class_counts = Counter()
    empty_images = []

    region_index = 0

    for image_path in image_paths:
        image_id = 'Images/' + image_path.name
        images.append(image_id)

        obj = json.loads(
            json_paths[image_path.stem].read_text(
                encoding='utf-8-sig',
            )
        )

        image = obj.get('image')

        require(
            isinstance(image, dict),
            'Missing DamSegment image metadata',
        )

        require(
            image.get('file_name') == image_path.name,
            'DamSegment filename disagreement',
        )

        require(
            image.get('width') == 640
            and image.get('height') == 640,
            'Unexpected DamSegment geometry',
        )

        annotations = obj.get('annotations')

        require(
            isinstance(annotations, list),
            'DamSegment annotations must be a list',
        )

        if not annotations:
            empty_images.append(image_id)

        for ann in annotations:
            require(
                isinstance(ann, dict),
                'DamSegment annotation must be an object',
            )

            source_class = ann.get('category_id')

            require(
                source_class in SOURCE_TO_AEGIS,
                'Unknown DamSegment source class',
            )

            bbox = ann.get('bbox')

            require(
                isinstance(bbox, list)
                and len(bbox) == 4,
                'Invalid DamSegment bbox',
            )

            x, y, w, h = map(_number, bbox)

            require(
                x >= 0
                and y >= 0
                and w > 0
                and h > 0
                and x + w <= 640
                and y + h <= 640,
                'Out-of-frame DamSegment bbox',
            )

            region_index += 1

            aegis_class = SOURCE_TO_AEGIS[
                source_class
            ]

            regions.append({
                'id': (
                    'damsegment-gt-'
                    f'{region_index:06d}'
                ),
                'image_id': image_id,
                'box': [
                    _number(x),
                    _number(y),
                    _number(x + w),
                    _number(y + h),
                ],
                'labels': [aegis_class],
            })

            class_counts[aegis_class] += 1

    validate_records(
        images,
        [],
        regions,
    )

    require(
        len(regions) == EXPECTED_REGIONS,
        'Unexpected DamSegment region count',
    )

    require(
        class_counts == EXPECTED_CLASS_COUNTS,
        'Unexpected DamSegment class counts',
    )

    # Independently re-count the YOLO side.
    yolo_counts = Counter()
    yolo_instances = 0

    for path in sorted(
        yolo_paths.values(),
        key=lambda p: p.name.casefold(),
    ):
        for raw in path.read_text(
            encoding='utf-8-sig',
        ).splitlines():
            raw = raw.strip()

            if not raw:
                continue

            parts = raw.split()

            require(
                len(parts) == 5,
                'Malformed DamSegment YOLO row',
            )

            source_class = int(float(parts[0]))

            require(
                source_class in SOURCE_TO_AEGIS,
                'Unknown DamSegment YOLO class',
            )

            yolo_counts[
                SOURCE_TO_AEGIS[source_class]
            ] += 1

            yolo_instances += 1

    require(
        yolo_instances == EXPECTED_REGIONS,
        'YOLO/JSON instance counts differ',
    )

    require(
        yolo_counts == EXPECTED_CLASS_COUNTS,
        'YOLO/JSON class counts differ',
    )

    payload = {
        'images': images,
        'regions': regions,
    }

    stats = {
        'image_count': len(images),
        'region_count': len(regions),
        'class_counts': dict(
            sorted(class_counts.items())
        ),
        'empty_image_count': len(empty_images),
        'empty_images': empty_images,
        'yolo_instance_count': yolo_instances,
        'yolo_class_counts': dict(
            sorted(yolo_counts.items())
        ),
        'object_sha256': object_hash(payload),
    }

    return payload, stats


def prepared_bytes(root):
    payload, stats = build_prepared_inventory(root)
    return canonical(payload) + b'\n', stats
