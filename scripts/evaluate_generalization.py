"""Post-freeze scorer for normalized exports; never loads images or runs inference."""
import argparse
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from detection.generalization.manifest import canonical, frozen_gate, read_json, read_json_with_hash, reserve, validate_bundle
from detection.generalization.metrics import evaluate
from detection.generalization.reporting import write_report
from detection.generalization.schema import require
from detection.generalization.taxonomy import scored_classes, validate_crosswalk


def run(manifest_path, bundle_path, ontology_path, protocol_path):
    m = read_json(manifest_path)
    # Gate metadata before even considering a scoring-payload read.
    from detection.generalization.schema import validate_manifest
    validate_manifest(m, scientific=True)
    ontology = read_json(ontology_path)
    expected_ontology_dataset = None if m['dataset']['identity'] == 'GYU-DET' else m['dataset']['identity']
    ontology = validate_crosswalk(ontology, expected_dataset=expected_ontology_dataset)
    protocol = read_json(protocol_path)
    require(protocol.get('status') == 'frozen', 'Protocol is not frozen')
    for key in ('ap_ious', 'ap_confidence_floor', 'operating_confidence', 'matching_iou', 'nms_iou', 'nms_mode', 'max_detections'):
        require(protocol.get(key) == m[key], 'Protocol disagrees: ' + key)
    frozen_gate(m, ROOT, ontology, protocol)
    classes = scored_classes(m['dataset']['identity'], ontology)
    out = reserve(ROOT / 'outputs/validation/defect_detection/generalization', m)
    bundle, export_sha256 = read_json_with_hash(bundle_path)
    validate_bundle(bundle, m)
    (out / 'input_evidence.json').write_bytes(canonical({'export_sha256': export_sha256,
        'ontology_sha256': m['ontology_sha256'], 'protocol_sha256': m['protocol_sha256']}) + b'\n')
    predictions = bundle['predictions']
    require(all(n <= m['max_detections'] for n in Counter(p['image_id'] for p in predictions).values()), 'Export exceeds max detections')
    require(all(p['confidence'] >= m['ap_confidence_floor'] for p in predictions), 'Export contains predictions below AP floor')
    result = evaluate(bundle['images'], predictions, bundle['regions'], classes,
                      ap_floor=m['ap_confidence_floor'], operating_confidence=m['operating_confidence'],
                      matching_iou=m['matching_iou'], ap_ious=m['ap_ious'])
    write_report(out, m, result, protocol['calibration_bins'])
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--predictions', required=True, help='Normalized inventory, regions and predictions JSON export')
    parser.add_argument('--ontology', required=True)
    parser.add_argument('--protocol', required=True)
    args = parser.parse_args()
    print(run(args.manifest, args.predictions, args.ontology, args.protocol))


if __name__ == '__main__':
    main()
