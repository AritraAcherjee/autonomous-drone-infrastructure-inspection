"""101-point interpolated AP; class-wise counts at frozen operating point."""
from .matching import match_class
from .schema import AP_IOUS, CLASSES, require, validate_records


def average_precision(rows, n_gt):
    if n_gt == 0:
        return None
    tp = 0
    curve = []
    for rank, row in enumerate(rows, 1):
        tp += int(row['correct'])
        curve.append((tp / n_gt, tp / rank))
    return sum(max((p for r, p in curve if r >= k/100), default=0.0) for k in range(101)) / 101


def counts(tp, fp, fn, n_images):
    require(type(n_images) is int and n_images > 0, 'Image denominator must be positive')
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return dict(TP=tp, FP=fp, FN=fn, precision=precision, recall=recall,
                F1=2*precision*recall/(precision+recall) if precision+recall else 0.0,
                FP_per_image=fp/n_images, FN_per_image=fn/n_images)


def mean_defined(values):
    values = [v for v in values if v is not None]
    return sum(values)/len(values) if values else None


def evaluate(images, predictions, regions, classes, *, ap_floor, operating_confidence, matching_iou, ap_ious):
    validate_records(images, predictions, regions)
    require(classes and len(set(classes)) == len(classes) and set(classes) <= set(CLASSES), 'Invalid scoring classes')
    require(ap_ious in ([0.5], AP_IOUS), 'Unsupported AP IoUs')
    require(0 <= ap_floor <= operating_confidence <= 1, 'Invalid confidence policy')
    per_class, confidence_rows, missed = [], [], []
    for c in sorted(classes):
        aps = {}
        for threshold in ap_ious:
            rows, _, n_gt = match_class(predictions, regions, c, threshold, ap_floor)
            aps[str(threshold)] = average_precision(rows, n_gt)
        rows, fn, _ = match_class(predictions, regions, c, matching_iou, operating_confidence)
        tp = sum(r['correct'] for r in rows)
        per_class.append(dict(class_id=c, class_name=CLASSES[c], AP50=aps['0.5'],
                              AP50_95=mean_defined(aps.values()) if ap_ious == AP_IOUS else None,
                              ap_by_iou=aps, **counts(tp, len(rows)-tp, len(fn), len(images))))
        confidence_rows.extend(match_class(predictions, regions, c, matching_iou, ap_floor)[0])
        missed.extend(dict(region_id=r, class_id=c) for r in fn)
    total = counts(*(sum(r[k] for r in per_class) for k in ('TP', 'FP', 'FN')), len(images))
    total.update(mAP50=mean_defined(r['AP50'] for r in per_class),
                 mAP50_95=mean_defined(r['AP50_95'] for r in per_class), images=len(images),
                 scored_classes=sorted(classes), classes_with_gt=sum(r['AP50'] is not None for r in per_class))
    return dict(summary=total, per_class=per_class, confidence=confidence_rows, missed=missed)
