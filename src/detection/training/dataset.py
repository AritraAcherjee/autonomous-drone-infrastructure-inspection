"""Ultralytics dataset integration with read-only verification and no disk caches."""
from __future__ import annotations

from copy import copy
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from ultralytics.data.dataset import YOLODataset
from ultralytics.data.base import imread
from ultralytics.data.augment import Albumentations

from detection.data.readonly_verifier import verify_label


def oriented_shape(path: Path) -> tuple[int, int]:
    """Read the primary image header without verification, repair, or source saves."""
    with Image.open(path) as image:
        w, h = image.size
        if image.getexif().get(274) in (6, 8):
            w, h = h, w
    return h, w


class ReadOnlyDetectionDataset(YOLODataset):
    """Keep source boxes unchanged in their reviewed EXIF-oriented coordinate frame.

    Only the in-memory mosaic buffer is used. No stock verification/cache scan,
    source repair, .npy reads or writes, or directory enumeration is performed.
    """

    def __init__(self, *, records: list[dict], **kwargs):
        if not records or any(r['split'] not in ('train', 'valid') for r in records):
            raise ValueError('Dataset requires approved development records')
        if kwargs.get('cache') not in (False, None) or kwargs.get('fraction', 1.0) != 1.0:
            raise ValueError('Disk/RAM caches and implicit fraction selection prohibited')
        self.records = records
        super().__init__(**kwargs)

    def get_img_files(self, img_path) -> list[str]:
        """Use exact approved records; do not discover images or sample a split."""
        return [str(r['image']) for r in self.records]

    def get_labels(self) -> list[dict]:
        """Reuse M1's read-only label checks while retaining every original box."""
        result = []
        for row in self.records:
            checked = verify_label(row)
            if not checked['success']:
                raise ValueError(f'Invalid approved label: {row["label"]}: {checked["errors"]}')
            values = np.loadtxt(row['label'], dtype=np.float32, ndmin=2)
            result.append(dict(im_file=str(row['image']), shape=oriented_shape(row['image']),
                               cls=values[:, :1], bboxes=values[:, 1:5], segments=[], keypoints=None,
                               normalized=True, bbox_format='xywh'))
        return result

    def cache_labels(self, *args, **kwargs):
        raise RuntimeError('Stock label caching/repair is prohibited')

    def cache_images(self, *args, **kwargs):
        raise RuntimeError('Disk and full-dataset RAM image caches are prohibited')

    def build_transforms(self, hyp=None):
        """Retain installed detection transforms; disable optional implicit Albumentations."""
        result = super().build_transforms(hyp)
        def disable(transform):
            if isinstance(transform, Albumentations):
                transform.p = 0.0
                transform.transform = None
            for child in getattr(transform, 'transforms', []):
                disable(child)
        disable(result)
        return result

    def load_image(self, i: int, rect_mode: bool = True, resize_short: bool = False):
        """Decode exactly as installed BaseDataset, never consulting raw-adjacent .npy.

        Resize and the rolling mosaic buffer follow 8.4.145 BaseDataset.load_image.
        Pixels and labels are modified in memory only by normal training transforms.
        """
        if self.ims[i] is not None:
            return self.ims[i], self.im_hw0[i], self.im_hw[i]
        image = imread(self.im_files[i], flags=self.cv2_flag)
        if image is None:
            raise FileNotFoundError(f'Cannot decode image: {self.im_files[i]}')
        h0, w0 = image.shape[:2]
        if rect_mode:
            ratio = self.imgsz/(min(h0, w0) if resize_short else max(h0, w0))
            if ratio != 1:
                w, h = math.ceil(w0*ratio), math.ceil(h0*ratio)
                if not resize_short:
                    w, h = min(w, self.imgsz), min(h, self.imgsz)
                image = cv2.resize(image, (w, h), interpolation=cv2.INTER_LINEAR)
        elif (h0, w0) != (self.imgsz, self.imgsz):
            image = cv2.resize(image, (self.imgsz, self.imgsz), interpolation=cv2.INTER_LINEAR)
        if image.ndim == 2:
            image = image[..., None]
        if self.augment:
            self.ims[i], self.im_hw0[i], self.im_hw[i] = image, (h0, w0), image.shape[:2]
            self.buffer.append(i)
            if 1 < len(self.buffer) >= self.max_buffer_length:
                j = self.buffer.pop(0)
                self.ims[j] = self.im_hw0[j] = self.im_hw[j] = None
        return image, (h0, w0), image.shape[:2]
