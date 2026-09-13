"""Independent class-wise greedy matching, stable confidence/ID ordering."""
from .schema import probability, require


def iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2]-a[0]) * (a[3]-a[1]) + (b[2]-b[0]) * (b[3]-b[1]) - intersection
    return intersection / union if union else 0.0


def match_class(predictions, regions, class_id, threshold=0.5, confidence=0.0):
    require(probability(threshold) and threshold > 0 and probability(confidence), 'Invalid matching thresholds')
    gt = sorted((r for r in regions if class_id in r['labels']), key=lambda r: r['id'])
    predictions = sorted((p for p in predictions if p['class_id'] == class_id and p['confidence'] >= confidence),
                         key=lambda p: (-p['confidence'], p['image_id'], p['id']))
    used, rows = set(), []
    for p in predictions:
        candidates = [(iou(p['box'], r['box']), r['id']) for r in gt
                      if r['image_id'] == p['image_id'] and r['id'] not in used]
        candidates.sort(key=lambda x: (-x[0], x[1]))
        best = candidates[0] if candidates else (0.0, None)
        correct = best[0] >= threshold
        if correct:
            used.add(best[1])
        rows.append(dict(prediction_id=p['id'], image_id=p['image_id'], class_id=class_id,
                         confidence=p['confidence'], correct=correct, matched_region_id=best[1] if correct else None,
                         iou=best[0]))
    return rows, [r['id'] for r in gt if r['id'] not in used], len(gt)
