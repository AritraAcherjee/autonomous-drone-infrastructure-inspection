"""Stable CSV interfaces and JSON evidence, including header-only review tables."""
import csv
import json
from .calibration import reliability
from .failures import category_counts
from .manifest import canonical


TABLES = {
    'domain_comparison': ['domain', 'experiment_id', 'images', 'scored_classes', 'classes_with_gt', 'mAP50', 'mAP50_95', 'precision', 'recall', 'F1', 'TP', 'FP', 'FN', 'FP_per_image', 'FN_per_image'],
    'per_class_transfer': ['domain', 'experiment_id', 'class_id', 'class_name', 'AP50', 'AP50_95', 'precision', 'recall', 'F1'],
    'fp_fn_counts': ['domain', 'experiment_id', 'class_id', 'TP', 'FP', 'FN', 'FP_per_image', 'FN_per_image'],
    'confidence_summary': ['domain', 'experiment_id', 'class_id', 'count', 'ECE'],
    'failure_category_counts': ['category', 'count'],
    'prediction_confidence': ['prediction_id', 'image_id', 'class_id', 'confidence', 'correct', 'matched_region_id', 'iou'],
    'reliability': ['class_id', 'lower', 'upper', 'count', 'mean_confidence', 'accuracy'],
    'failure_review': ['image_id', 'object_id', 'categories', 'reviewer', 'note'],
}


def write_tables(directory, tables):
    for name, fields in TABLES.items():
        with (directory / (name + '.csv')).open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
            writer.writeheader()
            for row in tables.get(name, []):
                writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def write_report(directory, m, result, n_bins=10):
    common = dict(domain=m['dataset']['identity'], experiment_id=m['experiment_id'])
    classes = [dict(common, **r) for r in result['per_class']]
    summaries, bins = [], []
    for class_id in result['summary']['scored_classes']:
        cal = reliability([r for r in result['confidence'] if r['class_id'] == class_id], n_bins)
        summaries.append(dict(common, class_id=class_id, count=cal['count'], ECE=cal['ECE']))
        bins.extend(dict(class_id=class_id, **r) for r in cal['bins'])
    write_tables(directory, dict(domain_comparison=[dict(common, **result['summary'])], per_class_transfer=classes,
        fp_fn_counts=classes, confidence_summary=summaries, reliability=bins,
        prediction_confidence=result['confidence']))
    # Failure categories are left unreviewed, not falsely reported as zero observed failures.
    (directory / 'failure_categories.json').write_bytes(canonical(category_counts([])) + b'\n')
    (directory / 'results.json').write_bytes(canonical(result) + b'\n')
    (directory / 'status.json').write_bytes(canonical({'status': 'COMPLETE'}) + b'\n')
