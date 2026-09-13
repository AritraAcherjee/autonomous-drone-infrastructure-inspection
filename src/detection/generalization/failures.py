"""Reviewed multi-tag failure records; visual causes are never inferred."""
from enum import Enum
from .schema import nonempty, require


FailureCategory = Enum('FailureCategory', {v: v for v in '''FN_SMALL FN_DISTANT FN_LOW_CONFIDENCE FN_LOW_CONTRAST
FN_LIGHTING FN_BLUR FN_OCCLUSION FN_UNUSUAL_SURFACE FP_TEXTURE FP_CONSTRUCTION_JOINT FP_STAIN FP_SHADOW
FP_CABLE FP_EDGE FP_MARKING FP_BACKGROUND_OTHER ERR_LOCALIZATION ERR_CLASS_CONFUSION
ERR_DUPLICATE_DETECTION ERR_TAXONOMY_MISMATCH ERR_ANNOTATION_MISMATCH'''.split()}, type=str)


def failure_record(image_id, object_id, categories, reviewer, note=''):
    require(all(nonempty(v) for v in (image_id, object_id, reviewer)), 'Failure requires object and reviewer')
    require(categories and len(set(categories)) == len(categories), 'Unique nonempty categories required')
    return dict(image_id=image_id, object_id=object_id, categories=[FailureCategory(c).value for c in categories],
                reviewer=reviewer, note=note)


def category_counts(records):
    counts = {c.value: 0 for c in FailureCategory}
    for r in records:
        record = failure_record(**r)
        for c in record['categories']:
            counts[c] += 1
    return [dict(category=c, count=n) for c, n in counts.items()]
