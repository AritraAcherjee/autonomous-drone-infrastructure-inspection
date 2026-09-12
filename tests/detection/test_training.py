"""Offline regression tests for baseline controls and installed EXIF integration."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from detection.training.config import load_config, load_development_data, run_directory, select_records, validate_config
from detection.training.provenance import configure_runtime, development_access, git_provenance, write_json
configure_runtime(ROOT)
from detection.training.exif import require_pass, stock_load
from detection.training.trainer import checkpoint, require_tests, training_arguments, trainer_class
from detection.data.raw_guard import compare, snapshot, sha256


def setUpModule():
    """Contain Ultralytics' global PIL.Image.open patch within this test module."""
    global ReadOnlyDetectionDataset, _original_pillow_open
    from PIL import Image
    _original_pillow_open = Image.open
    from detection.training.dataset import ReadOnlyDetectionDataset


def tearDownModule():
    from PIL import Image
    Image.open = _original_pillow_open


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config(ROOT/'configs/detection/det_baseline.yaml', ROOT)

    def test_full_baseline_explicit(self):
        self.assertEqual(self.config['training']['epochs'], 100)
        self.assertEqual(self.config['training']['batch'], 4)
        self.assertEqual(self.config['training']['seed'], 42)
        self.assertEqual(self.config['model']['checkpoint'], 'yolo26s.pt')
        self.assertNotIn('smoke', self.config)

    def test_required_fields(self):
        for section, key in (('model', 'checkpoint'), ('training', 'seed'), ('augmentation', 'mosaic'), ('reproducibility', 'git')):
            value = deepcopy(self.config)
            del value[section][key]
            with self.subTest(section=section), self.assertRaisesRegex(ValueError, section):
                validate_config(value, ROOT)

    def test_unknown_field_rejected(self):
        self.config['training']['surprise'] = True
        with self.assertRaises(ValueError):
            validate_config(self.config, ROOT)

    def test_no_test_training_or_codebrim(self):
        for key, value in (('train_split', 'test'), ('validation_split', 'test'), ('yaml', 'configs/data/codebrim.yaml'), ('test_policy', 'allowed')):
            config = deepcopy(self.config)
            config['data'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'prohibited'):
                validate_config(config, ROOT)

    def test_no_test_validation(self):
        self.config['validation']['split'] = 'test'
        with self.assertRaisesRegex(ValueError, 'test'):
            validate_config(self.config, ROOT)

    def test_controlled_output_root(self):
        self.assertEqual(run_directory(self.config, ROOT), (ROOT/'outputs/training/defect_detection/DET-BASELINE').resolve())
        self.config['output']['project'] = 'runs/detect'
        with self.assertRaisesRegex(ValueError, 'controlled'):
            validate_config(self.config, ROOT)

    def test_raw_output_rejected(self):
        for path in ('data/raw/training', 'outputs/../data/raw/training'):
            self.config['output']['project'] = path
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'raw'):
                validate_config(self.config, ROOT)

    def test_run_name_traversal(self):
        self.config['output']['name'] = '../escaped'
        with self.assertRaises(ValueError):
            validate_config(self.config, ROOT)

    def test_invalid_checkpoint_without_network(self):
        for value in ('missing.pt', 'yolo26x.pt', 'https://example.com/weights.pt'):
            self.config['model']['checkpoint'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'checkpoint'):
                validate_config(self.config, ROOT)

    def test_missing_local_checkpoint_no_download(self):
        with tempfile.TemporaryDirectory() as d, patch('urllib.request.urlopen', side_effect=AssertionError('network')):
            with self.assertRaisesRegex(FileNotFoundError, 'checkpoint missing'):
                checkpoint(self.config, Path(d), acquire=False)

    def test_missing_dataset_config(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(FileNotFoundError, 'configuration missing'):
            load_development_data(Path(d))

    def test_unapproved_yaml_path(self):
        with self.assertRaisesRegex(ValueError, 'Unapproved'):
            load_development_data(ROOT, 'configs/data/gyu_det_v3_baseline.yaml')

    def test_changed_class_ids_rejected(self):
        from data.validators.gyu_baseline_v1 import yaml_data
        altered = yaml_data()
        altered['names']['0'] = 'Seepage'
        with patch('yaml.safe_load', return_value=altered), self.assertRaisesRegex(ValueError, 'class mapping'):
            load_development_data(ROOT)

    def test_smoke_overlay_does_not_mutate_baseline(self):
        before = sha256(ROOT/'configs/detection/det_baseline.yaml')
        smoke = load_config(ROOT/'configs/detection/det_baseline_smoke.yaml', ROOT)
        self.assertEqual(smoke['training']['epochs'], 1)
        self.assertEqual(smoke['training']['batch'], self.config['training']['batch'])
        self.assertEqual(smoke['augmentation']['close_mosaic'], 0)
        self.assertEqual(smoke['smoke']['train_images'], 128)
        self.assertEqual(before, sha256(ROOT/'configs/detection/det_baseline.yaml'))

    def test_seed_selection_reproducible_and_order_independent(self):
        smoke = load_config(ROOT/'configs/detection/det_baseline_smoke.yaml', ROOT)
        rows = {s: [dict(image_relative_path=f'{s}/{i}.jpg') for i in range(300)] for s in ('train', 'valid')}
        selected = select_records(rows, smoke)
        self.assertEqual(selected, select_records({s: list(reversed(v)) for s, v in rows.items()}, smoke))
        self.assertEqual([len(selected[s]) for s in ('train', 'valid')], [128, 32])
        smoke['training']['seed'] = 43
        self.assertNotEqual(selected, select_records(rows, smoke))

    def test_batch_cache_worker_policies(self):
        for key, value in (('batch', 16), ('cache', 'disk'), ('cache', True), ('workers', 2), ('deterministic', False), ('amp', True), ('resume', True)):
            config = deepcopy(self.config)
            config['training'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_config(config, ROOT)

    def test_missing_config(self):
        with self.assertRaises(FileNotFoundError):
            load_config(ROOT/'nonexistent_training_config.yaml', ROOT)

    def test_native_arguments_recorded(self):
        args = training_arguments(self.config, ROOT, Path('yolo26s.pt'), Path('development.yaml'))
        self.assertEqual(args['split'], 'val')
        self.assertFalse(args['cache'])
        self.assertEqual(args['amp'], 'bf16')
        self.assertEqual(args['lr0'], .01)
        from ultralytics.cfg import get_cfg
        self.assertEqual(get_cfg(overrides=args).batch, 4)


class ProvenanceTests(unittest.TestCase):
    def test_git_environment_and_seed_serialization(self):
        import importlib.metadata
        import platform
        config = load_config(ROOT/'configs/detection/det_baseline.yaml', ROOT)
        payload = dict(git=git_provenance(ROOT), python=platform.python_version(),
                       ultralytics=importlib.metadata.version('ultralytics'), seed=config['training']['seed'], path=ROOT)
        self.assertRegex(payload['git']['sha'], r'^[0-9a-f]{40}$')
        self.assertIsInstance(payload['git']['dirty'], bool)
        self.assertEqual(payload['ultralytics'], '8.4.145')
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'evidence.json'
            write_json(path, payload, Path(d))
            self.assertEqual(json.loads(path.read_text())['seed'], 42)

    def test_nonfinite_json_refused(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            write_json(Path(d)/'bad.json', {'loss': float('nan')}, Path(d))

    def test_json_raw_path_rejected(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(ValueError, 'raw'):
            write_json(Path(d)/'data/raw/evidence.json', {}, Path(d))

    def test_stale_or_missing_geometry_refused(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(ValueError, 'GEOMETRY'):
            require_pass(Path(d))

    def test_missing_test_evidence_refused(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(ValueError, 'before'):
            require_tests(Path(d))

    def test_read_guard_blocks_test_and_other_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for relative in ('data/raw/gyu_det/v3/extracted/test/test/images/a.jpg', 'data/raw/codebrim/a.jpg'):
                path = root/relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
                with development_access(root), self.assertRaises(PermissionError):
                    path.read_bytes()

    def test_guard_blocks_raw_writes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root/'data/raw/gyu_det/v3/extracted/train/train/images/a.jpg'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'fixture')
            with development_access(root), self.assertRaises(ValueError):
                path.write_bytes(b'changed')
            self.assertEqual(path.read_bytes(), b'fixture')


class ExifIntegrationTests(unittest.TestCase):
    def test_all_six_class_ids_survive_project_dataset_and_batch(self):
        """Catch ID permutations, class merging, and changes to approved name order."""
        import numpy as np
        import torch
        from PIL import Image
        from ultralytics.cfg import get_cfg
        from detection.data.readonly_verifier import CLASSES
        expected = ['Crack', 'Breakage', 'Honeycombing', 'Hole', 'Exposed Reinforcement', 'Seepage']
        self.assertEqual(CLASSES, expected)
        config = load_config(ROOT/'configs/detection/det_baseline.yaml', ROOT)
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            image, label = folder/'classes.jpg', folder/'classes.txt'
            Image.new('RGB', (640, 640), (100, 120, 140)).save(image)
            order = [5, 0, 4, 1, 3, 2]
            label.write_text(''.join(f'{c} {0.15+0.13*i} 0.5 0.08 0.2\n' for i, c in enumerate(order)))
            row = dict(image=image, label=label, split='train', annotation_count='6',
                       class_ids='[0, 1, 2, 3, 4, 5]', image_relative_path='classes.jpg',
                       label_relative_path='classes.txt')
            cls = trainer_class()
            trainer = cls.__new__(cls)  # Exercise dataset construction without starting training.
            trainer.args = get_cfg(overrides=training_arguments(config, ROOT, Path('unused.pt'), folder/'data.yaml'))
            trainer.data = dict(train='train-list', val='valid-list', nc=6, channels=3,
                                names=dict(enumerate(CLASSES)))
            trainer.records = {'train': [row], 'valid': [dict(row, split='valid')]}
            trainer.model = SimpleNamespace(stride=torch.tensor([32]))
            train = trainer.build_dataset('train-list', mode='train', batch=4)
            valid = trainer.build_dataset('valid-list', mode='val', batch=4)
            np.testing.assert_array_equal(train.labels[0]['cls'].reshape(-1), order)
            np.testing.assert_array_equal(train.get_image_and_label(0)['cls'].reshape(-1), order)
            batch = valid.collate_fn([valid[0]])
            np.testing.assert_array_equal(batch['cls'].numpy().reshape(-1), order)
            self.assertEqual(train.data['names'], dict(enumerate(expected)))
            self.assertEqual(valid.data['names'], dict(enumerate(expected)))

    def test_cls_remap_is_forwarded_to_pretrained_name_binding(self):
        """The flag binds target model names without permuting the data mapping."""
        from ultralytics.cfg import get_cfg
        config = load_config(ROOT/'configs/detection/det_baseline.yaml', ROOT)
        args = get_cfg(overrides=training_arguments(config, ROOT, Path('unused.pt'), Path('unused.yaml')))
        self.assertIs(args.cls_remap, True)
        expected = dict(enumerate(['Crack', 'Breakage', 'Honeycombing', 'Hole', 'Exposed Reinforcement', 'Seepage']))
        cls = trainer_class()
        trainer = cls.__new__(cls)
        trainer.args, trainer.data = args, {'names': deepcopy(expected)}
        model = SimpleNamespace(names={0: 'person'})
        self.assertIs(trainer.set_model_names_for_load(model), model)
        self.assertEqual(model.names, expected)
        self.assertEqual(trainer.data['names'], expected)

    def fixture(self, folder, orientation):
        import numpy as np
        from PIL import Image
        root = Path(folder)
        path = root/'data/raw/gyu_det/v3/extracted/train/train/images/fixture.jpg'
        path.parent.mkdir(parents=True, exist_ok=True)
        pixels = np.zeros((80, 120, 3), dtype=np.uint8)
        pixels[10:35, 60:100] = (255, 80, 20)
        image = Image.fromarray(pixels)
        exif = Image.Exif(); exif[274] = orientation
        image.save(path, exif=exif)
        label = path.parent.parent/'labels/fixture.txt'
        label.parent.mkdir(parents=True, exist_ok=True)
        # Labels intentionally in oriented display coordinates, like reviewed GYU anchors.
        x, y, w, h = 80/120, 22.5/80, 40/120, 25/80
        box = (1-y, x, h, w) if orientation == 6 else (y, 1-x, h, w) if orientation == 8 else (x, y, w, h)
        label.write_text('0 '+' '.join(map(str, box))+'\n')
        return dict(image=path, label=label, split='train', annotation_count='1', class_ids='[0]',
                    image_relative_path=str(path.relative_to(root)), label_relative_path=str(label.relative_to(root)))

    def dataset(self, record, augment=False):
        from ultralytics.cfg import get_cfg
        hyp = get_cfg(overrides={'imgsz': 128, 'mosaic': 0., 'degrees': 0., 'translate': 0., 'scale': 0.,
            'fliplr': 0., 'flipud': 0., 'hsv_h': 0., 'hsv_s': 0., 'hsv_v': 0., 'bgr': 0.})
        return ReadOnlyDetectionDataset(records=[record], img_path='unused.txt', imgsz=128, batch_size=1,
            augment=augment, hyp=hyp, rect=False, cache=False, task='detect',
            data={'nc': 6, 'names': {i: str(i) for i in range(6)}, 'channels': 3})

    def test_exif_6_8_pixels_match_stock_and_boxes_unchanged(self):
        import cv2
        import numpy as np
        from ultralytics.data.base import imread
        from ultralytics.data.utils import verify_image_label
        for orientation in (1, 6, 8):
            with self.subTest(orientation=orientation), tempfile.TemporaryDirectory() as d:
                record = self.fixture(d, orientation)
                with development_access(Path(d)):
                    dataset = self.dataset(record)
                    pixels, original, _ = dataset.load_image(0)
                    stock, stock_hw, _ = stock_load(record['image'], 128)
                    np.testing.assert_array_equal(pixels, stock)
                    self.assertEqual(original, stock_hw)
                    before = np.loadtxt(record['label'], ndmin=2, dtype=np.float32)
                    stock_labels = verify_image_label((str(record['image']), str(record['label']), '', False, 6, 0, 0, False))[1]
                    np.testing.assert_array_equal(stock_labels, before)
                    raw_item = dataset.get_image_and_label(0)
                    np.testing.assert_array_equal(raw_item['instances'].bboxes, before[:, 1:])
                    self.assertTrue(raw_item['instances'].normalized)
                    # The bright asymmetric region remains centered in the source box on consumed pixels.
                    oriented = imread(str(record['image']))
                    yy, xx = np.where(oriented[:, :, 2] > 180)
                    actual_center = np.array([xx.mean()/oriented.shape[1], yy.mean()/oriented.shape[0]])
                    np.testing.assert_allclose(actual_center, before[0, 1:3], atol=.02)

    def test_no_raw_cache_repair_or_label_rewrite(self):
        with tempfile.TemporaryDirectory() as d:
            row = self.fixture(d, 6)
            raw = Path(d)/'data/raw'
            before = snapshot(raw, {row['image'], row['label']})
            with development_access(Path(d)), patch('ultralytics.data.utils.check_image', side_effect=AssertionError('repair path')):
                dataset = self.dataset(row, augment=True)
                item = dataset[0]
                self.assertEqual(item['img'].shape, (3, 128, 128))
            self.assertEqual(compare(before, snapshot(raw, {row['image'], row['label']}))['status'], 'PASS')
            self.assertEqual(list(raw.rglob('*.cache')), [])
            self.assertEqual(list(raw.rglob('*.npy')), [])

    def test_preexisting_raw_npy_never_loaded_or_removed(self):
        with tempfile.TemporaryDirectory() as d:
            row = self.fixture(d, 8)
            cache = row['image'].with_suffix('.npy')
            cache.write_bytes(b'invalid sentinel; must not be read')
            with patch('numpy.load', side_effect=AssertionError('npy read')):
                dataset = self.dataset(row)
                dataset.load_image(0)
            self.assertEqual(cache.read_bytes(), b'invalid sentinel; must not be read')

    def test_cache_methods_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            dataset = self.dataset(self.fixture(d, 1))
            for method in (dataset.cache_labels, dataset.cache_images):
                with self.assertRaises(RuntimeError):
                    method()

    def test_dataset_rejects_test_records(self):
        with self.assertRaisesRegex(ValueError, 'development'):
            ReadOnlyDetectionDataset(records=[{'split': 'test'}])

    def test_trainer_does_not_fall_back_to_test(self):
        cls = trainer_class()
        state = SimpleNamespace(development_data={'train': 'train.txt', 'val': 'valid.txt', 'nc': 6})
        self.assertNotIn('test', cls.get_dataset(state))
        for mode in ('test', 'validation'):
            with self.assertRaises(ValueError):
                cls.build_dataset(SimpleNamespace(data={}), 'test.txt', mode=mode)

    def test_no_silent_batch_reduction(self):
        cls = trainer_class()
        state = SimpleNamespace(args=SimpleNamespace(batch=2), evidence={'requested_batch': 4})
        with self.assertRaisesRegex(RuntimeError, 'auto-reduction'):
            cls._build_train_pipeline(state)


if __name__ == '__main__':
    unittest.main()
