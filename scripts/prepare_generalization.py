"""Create only draft metadata and empty output interfaces; no payload inputs."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from detection.generalization.manifest import canonical, environment, object_hash, read_json, reserve
from detection.generalization.reporting import write_tables
from detection.generalization.taxonomy import validate_crosswalk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment-id', required=True)
    args = parser.parse_args()
    configs = ROOT / 'configs/generalization'
    ontology = validate_crosswalk(read_json(configs / 'ontology_crosswalk.yaml'))
    protocol = read_json(configs / 'generalization_protocol.yaml')
    m = dict(schema_version=1, experiment_id=args.experiment_id, phase='pre_freeze', frozen=False,
             ontology_version=ontology['version'], ontology_sha256=object_hash(ontology),
             protocol_sha256=object_hash(protocol), environment=environment())
    for key in ('architecture', 'architecture_version', 'checkpoint_path', 'checkpoint_sha256', 'training_git_sha',
                'evaluation_git_sha', 'training_config', 'resolved_inference_config', 'dataset', 'image_size',
                'ap_confidence_floor', 'operating_confidence', 'matching_iou', 'ap_ious', 'nms_iou', 'nms_mode',
                'max_detections', 'seed', 'class_mapping', 'validation_evidence', 'freeze_approval'):
        m[key] = None
    out = reserve(ROOT / 'outputs/validation/defect_detection/generalization', m)
    write_tables(out, {})
    for name in ('generalization_protocol.yaml', 'ontology_crosswalk.yaml', 'perturbations.yaml'):
        (out / name).write_bytes(canonical(read_json(configs / name)) + b'\n')
    (out / 'status.json').write_bytes(canonical({'status': 'PREPARED_ONLY', 'scientific_evaluation': False}) + b'\n')
    print(out)


if __name__ == '__main__':
    main()
