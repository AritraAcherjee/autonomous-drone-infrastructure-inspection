"""Detection-level ECE, conditional on exported detections at AP floor."""
from .schema import probability, require


def reliability(rows, n_bins=10):
    require(type(n_bins) is int and n_bins > 0, 'Positive bin count required')
    bins = [[] for _ in range(n_bins)]
    for r in rows:
        require(probability(r.get('confidence')) and type(r.get('correct')) is bool, 'Invalid calibration row')
        bins[min(int(r['confidence']*n_bins), n_bins-1)].append(r)
    result = []
    for index, group in enumerate(bins):
        result.append(dict(lower=index/n_bins, upper=(index+1)/n_bins, count=len(group),
                           mean_confidence=sum(r['confidence'] for r in group)/len(group) if group else None,
                           accuracy=sum(r['correct'] for r in group)/len(group) if group else None))
    ece = sum(r['count'] * abs(r['mean_confidence']-r['accuracy']) for r in result if r['count']) / len(rows) if rows else None
    return dict(bins=result, ECE=ece, count=len(rows),
                TP_confidences=[r['confidence'] for r in rows if r['correct']],
                FP_confidences=[r['confidence'] for r in rows if not r['correct']])
