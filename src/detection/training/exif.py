"""Read-only EXIF compatibility evidence; no model or final-test data is loaded."""
from __future__ import annotations

from collections import Counter
import csv
import importlib.metadata
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image, ImageDraw

from detection.data.raw_guard import compare, sha256, snapshot
from detection.data.readonly_verifier import read_csv
from detection.training.config import load_development_data
from detection.training.provenance import configure_runtime, development_access, write_json

GEOMETRY_DIR = Path('outputs/validation/defect_detection/exif_alignment')
# Reviewed comparisons of stored/source, oriented/source, oriented/rotated boxes.
# These are spatial anchors, not adjudication of dataset annotation quality.
REVIEWED = {
    'train/10052.jpg': 'EXIF 6: unchanged vertical reinforcement boxes align with exposed rods; rotated boxes miss them.',
    'train/10117.jpg': 'EXIF 8: unchanged narrow lower reinforcement box follows the dangling rod; rotated box misses it.',
    'train/10029.jpg': 'EXIF 6: unchanged breakage box encloses the right dark damaged patch.',
    'train/10129.jpg': 'EXIF 8: unchanged small breakage box encloses the lower-right spalled patch.',
    'valid/8902.JPG': 'EXIF 6: unchanged boxes enclose both exposed/spalled vertical regions.',
    'valid/8582.JPG': 'EXIF 6: unchanged crack box follows the fine marked crack.',
    'valid/12047.jpg': 'EXIF 8: unchanged long crack box follows the marked horizontal crack.',
    'valid/8845.JPG': 'EXIF 8: unchanged two breakage boxes cover the small lower spalls.',
}


def source_identity() -> dict:
    """Fingerprint the installed loader and project adapter supporting the review."""
    from ultralytics.data import base, dataset, utils, augment
    from ultralytics.utils import patches
    from detection.training import dataset as adapter
    return {m.__name__: sha256(Path(m.__file__)) for m in (base, dataset, utils, augment, patches, adapter)}


def stock_load(image: Path, imgsz: int):
    """Call actual installed BaseDataset.load_image without running its mutating constructor."""
    from ultralytics.data.base import BaseDataset
    # A sentinel outside raw ensures the stock implementation cannot load a raw .npy.
    class AbsentCache:
        def exists(self):
            return False
    state = SimpleNamespace(ims=[None], im_files=[str(image)], npy_files=[AbsentCache()],
                            cv2_flag=cv2.IMREAD_COLOR, imgsz=imgsz, augment=False)
    return BaseDataset.load_image(state, 0)


def draw_comparison(path: Path, labels: np.ndarray, stored: np.ndarray, oriented: np.ndarray, orientation: int) -> None:
    """Write a diagnostic overlay outside raw; never save decoded images back to source."""
    rotated = labels.copy()
    x, y, w, h = labels[:, 1:].T
    rotated[:, 1:] = np.stack((1-y, x, h, w) if orientation == 6 else (y, 1-x, h, w), axis=1)
    canvas = Image.new('RGB', (1500, 740), 'white')
    for i, (pixels, boxes, caption) in enumerate(((stored, labels, 'Stored pixels / source boxes'),
            (oriented, labels, 'Loader pixels / source boxes'), (oriented, rotated, 'Loader pixels / rotated boxes'))):
        panel = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))
        panel.thumbnail((490, 650))
        draw = ImageDraw.Draw(panel)
        W, H = panel.size
        for cls, x, y, w, h in boxes:
            draw.rectangle(((x-w/2)*W, (y-h/2)*H, (x+w/2)*W, (y+h/2)*H), outline='red', width=3)
            draw.text(((x-w/2)*W+2, (y-h/2)*H+2), str(int(cls)), fill='yellow', stroke_width=1, stroke_fill='black')
        canvas.paste(panel, (i*500, 60))
        ImageDraw.Draw(canvas).text((i*500+5, 10), f'{path.stem} EXIF {orientation}\n{caption}', fill='black')
    canvas.save(path)


def run(root: Path) -> dict:
    """Check every affected development image and persist evidence before any training."""
    configure_runtime(root)
    from ultralytics.data.base import imread
    from detection.training.dataset import ReadOnlyDetectionDataset
    if importlib.metadata.version('ultralytics') != '8.4.145':
        raise ValueError('EXIF integration must be re-reviewed for a different Ultralytics version')
    out = root/GEOMETRY_DIR
    out.mkdir(parents=True, exist_ok=True)
    report = dict(status='FAIL', training_executed=False, weights_downloaded=False,
                  test_accessed=False, source_identity=source_identity(), reviewed_anchors=REVIEWED)
    write_json(out/'geometry.json', report, root)
    with development_access(root):
        _, splits = load_development_data(root)
        approved = {r['image_relative_path']: r for rows in splits.values() for r in rows}
        evidence = [r for r in read_csv(root/'outputs/validation/defect_detection/pretraining_gate/reader_geometry_differences.csv')
                    if r['split'] in ('train', 'valid')]
        if Counter((r['split'], r['exif_orientation']) for r in evidence) != Counter({('train', '6'): 286, ('train', '8'): 239, ('valid', '6'): 33, ('valid', '8'): 36}):
            raise ValueError('Affected development population differs from pretraining evidence')
        hashed = {approved[r['image_path']][k] for r in evidence for k in ('image', 'label')}
        before = snapshot(root/'data/raw', hashed)
        write_json(out/'raw_before.json', before, root)
        results = []
        try:
            for i, row in enumerate(evidence, 1):
                record = approved[row['image_path']]
                path = record['image']
                orientation = int(row['exif_orientation'])
                with Image.open(path) as image:
                    actual = image.getexif().get(274)
                stored = imread(str(path), flags=cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
                oriented = imread(str(path))
                expected = cv2.rotate(stored, cv2.ROTATE_90_CLOCKWISE if orientation == 6 else cv2.ROTATE_90_COUNTERCLOCKWISE)
                stock, stock_hw, _ = stock_load(path, 640)
                state = SimpleNamespace(ims=[None], im_files=[str(path)], cv2_flag=cv2.IMREAD_COLOR,
                                        imgsz=640, augment=False)
                adapted, adapted_hw, _ = ReadOnlyDetectionDataset.load_image(state, 0)
                result = dict(image=row['image_path'], split=row['split'], orientation=actual,
                    decoded_hw=list(oriented.shape[:2]), rotation_exact=np.array_equal(expected, oriented),
                    adapter_equals_stock=np.array_equal(stock, adapted) and stock_hw == adapted_hw,
                    source_sha256=sha256(path), label_sha256=sha256(record['label']))
                result['pass'] = bool(actual == orientation and result['rotation_exact'] and result['adapter_equals_stock']
                                      and result['source_sha256'] == record['image_sha256'])
                results.append(result)
                anchor = f'{row["split"]}/{path.name}'
                if anchor in REVIEWED:
                    draw_comparison(out/f'{row["split"]}_{path.stem}.png', np.loadtxt(record['label'], ndmin=2), stored, oriented, orientation)
                if i % 50 == 0 or i == len(evidence):
                    print(f'EXIF development geometry: {i}/{len(evidence)}', flush=True)
            report.update(checked=len(results), passed=sum(r['pass'] for r in results), rows=results,
                          label_coordinate_convention='EXIF-oriented display coordinates, supported by representative spatial anchors',
                          runtime_box_rotation_required=False,
                          limits='Machine checks cover decoder/adapter geometry for 594 development images. Spatial semantics are assessed on eight representative anchors; this is not a full annotation-quality audit. The 54 test cases were not opened.')
        finally:
            after = snapshot(root/'data/raw', hashed)
            report['raw_immutability'] = compare(before, after)
            write_json(out/'raw_after.json', after, root)
            report['status'] = 'PASS' if len(results) == 594 and all(r['pass'] for r in results) and report['raw_immutability']['status'] == 'PASS' else 'FAIL'
            write_json(out/'geometry.json', report, root)
    return report


def require_pass(root: Path) -> dict:
    """Fail closed on absent/stale geometry evidence before checkpoint acquisition."""
    import json
    path = root/GEOMETRY_DIR/'geometry.json'
    if not path.is_file():
        raise ValueError('EXIF TRAINING GEOMETRY not established; run scripts/verify_detector_exif.py')
    report = json.loads(path.read_text(encoding='utf-8'))
    if (report.get('status') != 'PASS' or report.get('passed') != 594 or report.get('test_accessed') is not False
            or report.get('source_identity') != source_identity()):
        raise ValueError('EXIF TRAINING GEOMETRY = FAIL or stale; smoke training prohibited')
    return report
