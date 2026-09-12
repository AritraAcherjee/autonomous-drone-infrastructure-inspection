"""Deterministic EDA of the validated GYU inventory; never writes raw data."""
from __future__ import annotations

import csv
import hashlib
import json
import platform
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from data.validators.gyu_orphan_review import Box, box_pixels, parse_yolo, read_csv

SPLITS = ('train', 'valid', 'test')
BASELINE = 'PROVISIONAL_BASELINE_ELIGIBLE'
RAW = 'RAW_VALIDATED_INVENTORY'
SIZE_BINS = ('tiny', 'small', 'medium', 'large')
COUNT_BINS = ('0_explicit_empty_label', '1', '2-5', '6-10', '11-20', '>20')
METRICS = ('normalized_width', 'normalized_height', 'normalized_area', 'pixel_width',
           'pixel_height', 'pixel_area', 'aspect_ratio', 'relative_image_area')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f'Cannot infer empty CSV schema: {path}')
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return dict(count=0, mean=None, min=None, p01=None, p05=None, p25=None,
                    median=None, p75=None, p95=None, p99=None, max=None)
    a = np.asarray(values, dtype=float)
    result: dict[str, Any] = dict(count=len(a), mean=float(a.mean()), min=float(a.min()))
    result.update({name: float(np.percentile(a, percentile)) for name, percentile in
                   [('p01', 1), ('p05', 5), ('p25', 25), ('median', 50), ('p75', 75), ('p95', 95), ('p99', 99)]})
    result['max'] = float(a.max())
    return result


def annotation_bin(count: int) -> str:
    if count < 0:
        raise ValueError('Annotation counts must be nonnegative')
    return (COUNT_BINS[0] if count == 0 else '1' if count == 1 else '2-5' if count <= 5
            else '6-10' if count <= 10 else '11-20' if count <= 20 else '>20')


def box_metrics(box: Box, width: int, height: int) -> dict[str, Any]:
    area = box.width * box.height
    corners = box_pixels(box, (1, 1))
    excess = max(0., -corners[0], -corners[1], corners[2] - 1, corners[3] - 1)
    return dict(normalized_width=box.width, normalized_height=box.height,
                normalized_area=area, pixel_width=box.width * width,
                pixel_height=box.height * height, pixel_area=area * width * height,
                aspect_ratio=box.width * width / (box.height * height), relative_image_area=area,
                normalized_aspect_ratio=box.width / box.height,
                size_category='tiny' if area < .001 else 'small' if area < .01 else 'medium' if area < .1 else 'large',
                near_border=min(corners[0], corners[1], 1-corners[2], 1-corners[3]) <= .01,
                boundary_excess=excess, rounding_warning=0 < excess <= 1e-6,
                extreme_aspect_ratio=(box.width * width / (box.height * height) < .1 or
                                      box.width * width / (box.height * height) > 10))


def baseline_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [sample for sample in samples if sample['pairing_status'] == 'exact_pair']


def cooccurrence(samples: list[dict[str, Any]], count: int) -> list[list[int]]:
    matrix = [[0] * count for _ in range(count)]
    for sample in baseline_samples(samples):
        for a in sample['classes']:
            for b in sample['classes']:
                matrix[a][b] += 1
    return matrix


def load_inventory(repository: Path, manifest: Path, validation: Path,
                   classes_path: Path) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    classes = [line.strip() for line in classes_path.read_text(encoding='utf-8-sig').splitlines()]
    if classes != ['Crack', 'Breakage', 'Comb', 'Hole', 'Reinforcement', 'Seepage']:
        raise ValueError('Authoritative raw class ordering changed')
    images = read_csv(manifest)
    labels = read_csv(validation / 'label_validation.csv')
    verified_images = read_csv(validation / 'image_validation.csv')
    image_keys = {(r['split'], r['image_filename']): r for r in verified_images}
    if len(image_keys) != len(images) or len({(r['split'], r['image_filename']) for r in images}) != len(images):
        raise ValueError('Image inventory is not one-to-one')
    parsed = {}
    orphan_rows = []
    raw = (repository / 'data/raw').resolve()
    for label in labels:
        key = (label['split'], label['label_filename'])
        if key in parsed or label['validation_status'] == 'invalid':
            raise ValueError(f'Duplicate or invalid label: {key}')
        path = (repository / label['label_relative_path']).resolve()
        if raw not in path.parents:
            raise ValueError(f'Label path outside raw inventory: {path}')
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != label['label_sha256']:
            raise ValueError(f'Label changed since validation: {key}')
        text = content.decode('utf-8-sig')
        boxes = parse_yolo(text, classes) if text.strip() else []
        if len(boxes) != int(label['annotation_count']):
            raise ValueError(f'Annotation count differs from validation: {key}')
        parsed[key] = boxes
        if label['pairing_status'] == 'orphan_label':
            orphan_rows.extend(dict(split=key[0], label_filename=key[1], class_id=b.class_id) for b in boxes)
    samples, box_rows, used = [], [], set()
    for image in images:
        split, name = image['split'], image['image_filename']
        check = image_keys[(split, name)]
        if split not in SPLITS or check['primary_decode_success'].lower() != 'true':
            raise ValueError(f'Unvalidated primary image: {split}/{name}')
        for field in ('width', 'height', 'image_sha256', 'pairing_status'):
            if check[field] != image[field]:
                raise ValueError(f'Manifest/validation mismatch: {split}/{name}: {field}')
        width, height = int(image['width']), int(image['height'])
        if width <= 0 or height <= 0:
            raise ValueError('Invalid cached dimensions')
        exact = image['pairing_status'] == 'exact_pair'
        if image['pairing_status'] not in ('exact_pair', 'image_without_label'):
            raise ValueError(f'Unsupported pairing status: {image["pairing_status"]}')
        key = (split, image['label_filename'])
        boxes = parsed[key] if exact else []
        if exact:
            if key in used or len(boxes) != int(image['annotation_count']):
                raise ValueError(f'Exact pair is ambiguous or count changed: {key}')
            used.add(key)
        sample = dict(split=split, image_filename=name, pairing_status=image['pairing_status'],
                      width=width, height=height, megapixels=width*height/1e6,
                      image_aspect_ratio=width/height,
                      orientation='landscape' if width > height else 'portrait' if width < height else 'square',
                      annotation_count=len(boxes) if exact else None,
                      classes=sorted({b.class_id for b in boxes}))
        samples.append(sample)
        for row_number, box in enumerate(boxes, 1):
            box_rows.append(dict(split=split, image_filename=name, label_filename=image['label_filename'],
                                 annotation_index=row_number, class_id=box.class_id, class_name=classes[box.class_id],
                                 **box_metrics(box, width, height)))
    expected = {(r['split'], r['label_filename']) for r in labels if r['pairing_status'] == 'exact_pair'}
    if used != expected or any(r['pairing_status'] not in ('exact_pair', 'orphan_label') for r in labels):
        raise ValueError('Exact-pair label coverage differs from manifest')
    return classes, samples, box_rows, orphan_rows


def tables(classes: list[str], samples: list[dict[str, Any]], boxes: list[dict[str, Any]],
           orphans: list[dict[str, Any]], orphan_counts: Counter) -> dict[str, list[dict[str, Any]]]:
    """All supervised denominators use exact pairs; raw view retains orphan instances separately."""
    result: dict[str, list[dict[str, Any]]] = {}
    paired = baseline_samples(samples)
    overview, class_rows, split_rows, annotation_counts, comparisons = [], [], [], [], []
    for split in ('all', *SPLITS):
        select = lambda rows: [r for r in rows if split == 'all' or r['split'] == split]
        ss, pp, bb, oo = map(select, (samples, paired, boxes, orphans))
        for view in (RAW, BASELINE):
            overview.append(dict(view=view, split=split, total_images=len(ss) if view == RAW else len(pp),
                exact_supervised_pairs=len(pp), unlabeled_images=len(ss)-len(pp) if view == RAW else 0,
                orphan_labels=sum(orphan_counts.values()) if split == 'all' and view == RAW else orphan_counts[split] if view == RAW else 0,
                exact_pair_annotation_instances=len(bb), orphan_annotation_instances=len(oo) if view == RAW else 0,
                annotation_instances=len(bb)+(len(oo) if view == RAW else 0),
                one_class_images=sum(len(s['classes']) == 1 for s in pp),
                multi_class_images=sum(len(s['classes']) > 1 for s in pp),
                **{'annotations_per_exact_pair_'+k: v for k, v in stats([s['annotation_count'] for s in pp]).items()}))
        class_counter = Counter(b['class_id'] for b in bb)
        positives = [v for v in class_counter.values() if v]
        for cid, name in enumerate(classes):
            images = sum(cid in s['classes'] for s in pp)
            row = dict(split=split, class_id=cid, class_name=name,
                exact_pair_annotation_instances=class_counter[cid],
                orphan_annotation_instances=sum(o['class_id'] == cid for o in oo),
                total_raw_annotation_instances=class_counter[cid]+sum(o['class_id'] == cid for o in oo),
                exact_pair_images_containing_class=images,
                percent_exact_pair_images=100*images/len(pp) if pp else 0,
                instance_share_percent=100*class_counter[cid]/len(bb) if bb else 0,
                majority_to_class_instance_ratio=max(positives)/class_counter[cid] if class_counter[cid] else None,
                class_to_minority_instance_ratio=class_counter[cid]/min(positives) if positives else None)
            (class_rows if split == 'all' else split_rows).append(row)
        counts = Counter(annotation_bin(s['annotation_count']) for s in pp)
        annotation_counts.extend(dict(split=split, annotation_bin=b, exact_pair_images=counts[b],
                                     percent=100*counts[b]/len(pp) if pp else 0) for b in COUNT_BINS)
        if split != 'all':
            comparisons.append(dict(split=split, raw_images=len(ss), exact_pairs=len(pp), unlabeled_images=len(ss)-len(pp),
                annotation_instances=len(bb), annotation_density_mean=len(bb)/len(pp) if pp else None,
                annotation_density_median=stats([s['annotation_count'] for s in pp])['median'],
                median_normalized_box_area=stats([b['normalized_area'] for b in bb])['median'],
                median_megapixels=stats([s['megapixels'] for s in ss])['median'],
                multi_class_percent=100*sum(len(s['classes']) > 1 for s in pp)/len(pp) if pp else 0,
                **{n+'_instance_share_percent': 100*class_counter[c]/len(bb) if bb else 0 for c, n in enumerate(classes)}))
    result.update(dataset_overview=overview, class_distribution=class_rows,
                  class_distribution_by_split=split_rows, annotation_count_distribution=annotation_counts,
                  split_comparison=comparisons)
    for suffix, groups in [('', [('all', boxes)]), ('_by_class', [(name, [b for b in boxes if b['class_id'] == cid]) for cid, name in enumerate(classes)]),
                           ('_by_split', [(s, [b for b in boxes if b['split'] == s]) for s in SPLITS])]:
        result['box_statistics'+suffix] = [dict(group=name, metric=metric, **stats([b[metric] for b in group]))
                                            for name, group in groups for metric in METRICS]
    size_rows = []
    for group_type, groups in [('all', [('all', boxes)]), ('class', [(n, [b for b in boxes if b['class_id'] == c]) for c, n in enumerate(classes)]),
                               ('split', [(s, [b for b in boxes if b['split'] == s]) for s in SPLITS])]:
        for name, group in groups:
            for size in SIZE_BINS:
                count = sum(b['size_category'] == size for b in group)
                size_rows.append(dict(group_type=group_type, group=name, size_category=size, box_count=count,
                                      percent=100*count/len(group) if group else 0))
    result['box_size_distribution'] = size_rows
    result['box_measurements'] = boxes
    extremes = []
    for kind, chosen in [('smallest', sorted(boxes, key=lambda b: b['normalized_area'])[:20]),
                         ('largest', sorted(boxes, key=lambda b: -b['normalized_area'])[:20]),
                         ('extreme_aspect_ratio', [b for b in boxes if b['extreme_aspect_ratio']]),
                         ('near_border', [b for b in boxes if b['near_border']]),
                         ('rounding_warning', [b for b in boxes if b['rounding_warning']])]:
        extremes.extend(dict(example_type=kind, **b) for b in chosen)
    result['box_examples'] = extremes
    result['annotation_count_examples'] = [dict(**{k: v for k, v in s.items() if k != 'classes'},
                                                class_ids=';'.join(map(str, s['classes'])))
        for s in sorted(paired, key=lambda s: (-s['annotation_count'], s['split'], s['image_filename']))[:30]]
    resolutions, aspects, image_stats = [], [], []
    for view, population in [(RAW, samples), (BASELINE, paired)]:
        for split in ('all', *SPLITS):
            group = [s for s in population if split == 'all' or s['split'] == split]
            counter = Counter((s['width'], s['height']) for s in group)
            for (w, h), count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
                resolutions.append(dict(view=view, split=split, width=w, height=h, images=count,
                    percent=100*count/len(group), rare_resolution=count < 10))
            for orientation in ('landscape', 'portrait', 'square'):
                for low, high in [(0, .5), (.5, 1), (1, 1.5), (1.5, 2), (2, float('inf'))]:
                    count = sum(s['orientation'] == orientation and low <= s['image_aspect_ratio'] < high for s in group)
                    aspects.append(dict(view=view, split=split, orientation=orientation, aspect_min=low,
                                        aspect_max='inf' if high == float('inf') else high, images=count,
                                        percent=100*count/len(group) if group else 0))
            image_stats.extend(dict(view=view, split=split, metric=m, **stats([s[m] for s in group]))
                               for m in ('width', 'height', 'megapixels', 'image_aspect_ratio'))
    result.update(resolution_distribution=resolutions, aspect_ratio_distribution=aspects, image_statistics=image_stats)
    matrix = cooccurrence(samples, len(classes))
    result['class_cooccurrence'] = [dict(class_name=name, **dict(zip(classes, matrix[c]))) for c, name in enumerate(classes)]
    result['class_cooccurrence_normalized'] = [dict(class_name=name, **{n: matrix[c][d]/matrix[c][c] if matrix[c][c] else 0
                                              for d, n in enumerate(classes)}) for c, name in enumerate(classes)]
    combos = Counter(tuple(s['classes']) for s in paired)
    result['class_combination_statistics'] = [dict(class_ids=';'.join(map(str, c)),
        class_names=' + '.join(classes[i] for i in c) or 'explicit empty label', class_count=len(c), images=n,
        percent_exact_pairs=100*n/len(paired)) for c, n in sorted(combos.items(), key=lambda kv: (-kv[1], kv[0]))]
    return result


def figures(output: Path, classes: list[str], samples: list[dict[str, Any]], boxes: list[dict[str, Any]],
            result: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 11, 'figure.dpi': 110, 'savefig.dpi': 220})

    def save(name: str, ax: Any, title: str, xlabel: str, ylabel: str) -> None:
        ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
        ax.figure.tight_layout()
        ax.figure.savefig(output / (name+'.png'), metadata={'Software': 'AegisInspect GYU EDA'})
        plt.close(ax.figure)

    _, ax = plt.subplots(figsize=(10, 5))
    ax.bar(classes, [r['exact_pair_annotation_instances'] for r in result['class_distribution']])
    save('class_distribution', ax, 'Defect instances in exact image-label pairs', 'Raw class', 'Annotation instances')
    _, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(classes))
    for i, split in enumerate(SPLITS):
        group = [r for r in result['class_distribution_by_split'] if r['split'] == split]
        ax.bar(x+(i-1)*.25, [r['instance_share_percent'] for r in group], width=.25, label=split)
    ax.set_xticks(x, classes)
    ax.legend(title='Original split')
    save('class_distribution_by_split', ax, 'Class instance shares by original split', 'Raw class', 'Percent of split annotations')
    _, ax = plt.subplots(figsize=(9, 5))
    bins = [r for r in result['annotation_count_distribution'] if r['split'] == 'all']
    ax.bar([r['annotation_bin'] for r in bins], [r['exact_pair_images'] for r in bins])
    ax.tick_params(axis='x', labelrotation=15)
    save('annotations_per_image', ax, 'Annotation density: exact pairs only', 'Boxes per image (unlabeled excluded)', 'Images')
    for name, metric, xlabel in [('box_area_distribution', 'normalized_area', 'Box area / image area (log scale)'),
                                  ('box_aspect_ratio_distribution', 'aspect_ratio', 'Pixel width / pixel height (log scale)')]:
        _, ax = plt.subplots(figsize=(9, 5))
        values = [b[metric] for b in boxes]
        edges = np.geomspace(min(values)*.99, max(values)*1.01, 65)
        ax.hist(values, bins=edges)
        ax.set_xscale('log')
        save(name, ax, 'Exact-pair bounding-box distribution', xlabel, 'Annotation instances')
    _, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot([[b['normalized_area'] for b in boxes if b['class_id'] == c] for c in range(len(classes))],
               tick_labels=classes, showfliers=False)
    ax.set_yscale('log')
    save('box_area_by_class', ax, 'Box area by class (outlier points hidden; retained in statistics)', 'Raw class', 'Box / image area (log scale)')
    _, ax = plt.subplots(figsize=(11, 6))
    rr = [r for r in result['resolution_distribution'] if r['view'] == RAW and r['split'] == 'all'][:12]
    ax.barh([f"{r['width']} x {r['height']}" for r in rr][::-1], [r['images'] for r in rr][::-1])
    save('resolution_distribution', ax, 'Twelve most common stored image resolutions (all raw images)', 'Images', 'Width x height (pixels)')
    _, ax = plt.subplots(figsize=(9, 5))
    ax.hist([s['image_aspect_ratio'] for s in samples], bins=50)
    save('image_aspect_ratio_distribution', ax, 'Stored aspect ratios: all raw images', 'Width / height', 'Images')
    _, ax = plt.subplots(figsize=(9, 7))
    matrix = np.array(cooccurrence(samples, len(classes)))
    im = ax.imshow(matrix)
    ax.figure.colorbar(im, ax=ax, label='Exact-pair images')
    ax.set_xticks(range(len(classes)), classes, rotation=35, ha='right')
    ax.set_yticks(range(len(classes)), classes)
    for (i, j), value in np.ndenumerate(matrix):
        ax.text(j, i, str(value), ha='center', va='center', bbox={'facecolor': 'white', 'alpha': .8, 'edgecolor': 'none'})
    save('class_cooccurrence_heatmap', ax, 'Image-level class co-occurrence (diagonal = prevalence)', 'Class present', 'Class present')
    return dict(python=platform.python_version(), numpy=np.__version__, matplotlib=matplotlib.__version__)


def report(summary: dict[str, Any], result: dict[str, list[dict[str, Any]]]) -> str:
    classes = result['class_distribution']
    dominant = max(classes, key=lambda r: r['exact_pair_annotation_instances'])
    rare = min(classes, key=lambda r: r['exact_pair_annotation_instances'])
    overview = next(r for r in result['dataset_overview'] if r['view'] == BASELINE and r['split'] == 'all')
    sizes = [r for r in result['box_size_distribution'] if r['group_type'] == 'all']
    resolutions = [r for r in result['resolution_distribution'] if r['view'] == RAW and r['split'] == 'all']
    lines = ['# GYU-DET V3 exploratory data analysis', '',
        'M1 remains incomplete. This is a complete-inventory EDA, not a processed dataset or a training run.', '',
        '## Scope and reproducibility', '',
        'Two views are explicit in dataset_overview.csv: RAW_VALIDATED_INVENTORY includes all images and separately identified orphan annotation instances; '
        'PROVISIONAL_BASELINE_ELIGIBLE contains exact image-label pairs only. All box, class-prevalence, density and co-occurrence statistics use exact pairs. '
        'The provisional view does not exclude reviewed leakage groups or readable MPO primary images. No samples have been removed.', '',
        'Image metadata is reused from the manifest and full validation. No raw image is opened or decoded. '
        'All label bytes are checked against their existing validation SHA-256 before the shared YOLO parser reads geometry. '
        'Input hashes, package versions and output inventory are recorded in eda_summary.json. Image byte hashes are reused, not recomputed; '
        'therefore this analysis assumes raw image content remains unchanged since validation.', '',
        'Install the recorded versions with `python -m pip install -r scripts/data/requirements-gyu-eda.txt`, then run from the repository: '
        '`python scripts/data/eda_gyu_det.py`. Dependencies: NumPy, Pillow (shared parser import) and Matplotlib; no seaborn. '
        'Deterministic ordering, linear-interpolated NumPy percentiles, no random sampling and no run timestamps are used. '
        'PNG reproducibility assumes the recorded plotting/runtime versions and fonts.', '',
        '## Dataset and classes', '',
        f"Analyzed {summary['exact_pair_images']:,} exact-pair images with {summary['exact_pair_annotation_instances']:,} instances. "
        f"The {summary['orphan_labels']} orphan labels contain {summary['orphan_annotation_instances']} additional instances, never assigned to supervised images. "
        f"The {summary['unlabeled_images']} unlabeled images have unknown annotation status; they are not counted as zero-box images.", '',
        '| Class | Exact-pair instances | Orphan instances | Images containing class | % exact pairs |',
        '|---|---:|---:|---:|---:|']
    lines += [f"| {r['class_name']} | {r['exact_pair_annotation_instances']:,} | {r['orphan_annotation_instances']} | {r['exact_pair_images_containing_class']:,} | {r['percent_exact_pair_images']:.2f} |" for r in classes]
    lines += ['', f"{dominant['class_name']} dominates instance counts; {rare['class_name']} is rarest. "
        f"The majority/minority instance ratio is {summary['class_imbalance_ratio']:.2f}:1. "
        'Instance balance and image prevalence differ because multiple boxes can share a class in one image.', '',
        '## Annotation density and co-occurrence', '',
        f"Per exact-pair image: mean {overview['annotations_per_exact_pair_mean']:.2f}, median {summary['median_annotations_per_image']:g}, "
        f"minimum {overview['annotations_per_exact_pair_min']:g}, maximum {overview['annotations_per_exact_pair_max']:g}. "
        f"{summary['multi_class_percent']:.2f}% of exact-pair images contain multiple defect classes; "
        f"{overview['one_class_images']:,} contain one class. annotation_count_examples.csv identifies the 30 densest images.", '',
        'Most common class combinations (single-class combinations included):', '']
    lines += [f"- {r['class_names']}: {r['images']:,} images ({r['percent_exact_pairs']:.2f}%)." for r in result['class_combination_statistics'][:5]]
    lines += ['', 'The raw 6x6 matrix counts images, not pairs of boxes. The normalized matrix is P(column class present | row class present); '
        'its diagonal is 1 for observed classes and its rows need not sum to 1. Multi-defect scenes suggest checking augmentation effects jointly across classes.', '',
        '## Box geometry and small objects', '',
        'Relative area categories are descriptive, not COCO pixel-area categories: tiny <0.001 (0.1%); '
        'small [0.001,0.01); medium [0.01,0.1); large >=0.1. These order-of-magnitude intervals '
        'compare scenes with different resolutions. Relative image area and normalized area are identical.', '',
        f"Median normalized area is {summary['median_normalized_box_area']:.6g}. " +
        '; '.join(f"{r['size_category']} {r['percent']:.2f}%" for r in sizes) + '.', '',
        'Pixel aspect ratio uses pixel width / pixel height; normalized aspect ratio is separately retained. '
        'A border box has any edge within 0.01 normalized units of a frame boundary, including overshoots. '
        'Extreme aspect ratios are <0.1 or >10. Measurements retain original geometry without clipping. '
        'box_examples.csv lists the 20 smallest/largest relative-area boxes and every border, extreme-ratio and rounding-warning box.', '',
        f"Exact-pair boxes: {summary['near_border_boxes']:,} near borders, {summary['extreme_aspect_ratio_boxes']:,} extreme aspect ratios, "
        f"{summary['exact_pair_rounding_warning_boxes']:,} boundary rounding warnings. "
        'The full validated label inventory has 1,809 overshoot warnings <=1e-6; one belongs to an orphan label. '
        'Orphan boxes are not silently mixed into exact-pair box distributions.', '',
        'Small relative boxes can lose pixel detail when resized for YOLO. Before choosing input resolution, inspect their post-letterbox pixel dimensions '
        'at candidate sizes; relative area alone does not establish visibility. Larger inputs or tiles are hypotheses to evaluate later, '
        'with scene groups kept together and border/crop effects tracked. Extreme thin boxes make aggressive downscaling and geometric transforms especially worth checking.', '',
        '## Resolution and original split differences', '',
        f"There are {len(resolutions)} unique stored resolutions. Rare means fewer than 10 images in the stated view/split; "
        'rarity is descriptive and not an exclusion rule. Width, height, megapixel and aspect quantiles are in image_statistics.csv. Major groups:', '']
    lines += [f"- {r['width']} x {r['height']}: {r['images']:,} images ({r['percent']:.2f}%)." for r in resolutions[:5]]
    lines += ['', '| Split | Pairs | Instances | Mean boxes/image | Median box area | Median MP (raw) |', '|---|---:|---:|---:|---:|---:|']
    lines += [f"| {r['split']} | {r['exact_pairs']} | {r['annotation_instances']} | {r['annotation_density_mean']:.2f} | {r['median_normalized_box_area']:.5f} | {r['median_megapixels']:.3f} |" for r in result['split_comparison']]
    lines += ['', 'Notable differences are descriptive flags, not significance tests: instance-share or resolution-share range >=5 percentage points, '
        'or largest/smallest nonzero split median/mean >=1.25.', '']
    lines += ['- '+s for s in summary['split_difference_flags']] or ['- No thresholds exceeded.']
    lines += ['', 'Variation in image scale can change effective defect size after letterboxing. Preserve aspect ratio and assess candidate input sizes '
        'against both small-box dimensions and computational cost. Augmentation experiments should preserve defect semantics: '
        'check that crops do not erase tiny reinforcement/hole targets and that geometry or photometric changes remain physically plausible. '
        'No augmentation configuration or input size is approved by this EDA.', '',
        '## Evaluation and data-quality limitations', '',
        'Class imbalance motivates reporting per-class precision/recall and AP alongside aggregate mAP, plus size-stratified errors and sample support. '
        'Rare-class estimates may be unstable; co-occurring defects and scene families reduce independence. '
        'These are implications inferred from the inventory, not model-performance claims.', '',
        'All 21 orphan labels were human triaged, with zero confirmed mappings and no repair authorization. '
        'Plausible candidates remain unconfirmed. The 712 unlabeled images remain UNCLASSIFIED; the supplied 691 negative/no-defect total '
        'cannot identify intentional negatives by subtraction. Background-only evaluation and false-positive estimates remain limited until negative identity is resolved.', '',
        'Leakage review retains its approved decisions: one confirmed exact cross-split duplicate, one high-confidence near duplicate, '
        'one conservative unresolved same-scene group and 14 rejected perceptual candidates. Future processed splits must keep each of the three groups together '
        '(or an approved representative for exact/high-confidence groups); unresolved is not confirmed leakage. No member is removed here.', '',
        '- Exact: train/9838.jpg with valid/11989.jpg.',
        '- High-confidence: train/11727.jpg with valid/11985.jpg.',
        '- Conservative unresolved: train/11334.jpg with test/12582.jpg.', '',
        'Full validation found 565 MPO auxiliary-frame failures while all 11,123 primary images decoded. These remain warning-only under '
        'the provisional policy; eventual training-reader compatibility remains to be established. Raw geometry, official splits, prior human decisions '
        'and data/raw remain unchanged. No final processed training dataset exists from this pipeline.', '',
        '## Outputs', '', 'See output_inventory.csv for every generated relative path and purpose; figures/ contains nine 220-DPI PNGs. '
        'All box tables and figures refer to PROVISIONAL_BASELINE_ELIGIBLE unless explicitly marked raw. '
        'Class tables expose orphan counts separately, never as supervised image counts.', '']
    return '\n'.join(lines)


def run_eda(repository: Path, manifest: Path, validation: Path, triage: Path, leakage: Path,
            policy: Path, classes_path: Path, output: Path) -> dict[str, Any]:
    repository = repository.resolve()
    manifest, validation, triage, leakage, policy, classes_path, output = [
        (p if p.is_absolute() else repository / p).resolve() for p in
        (manifest, validation, triage, leakage, policy, classes_path, output)]
    # Restrict writes to an EDA directory, never input inventories, raw data or review outputs.
    if (repository / 'outputs/eda').resolve() not in output.parents:
        raise ValueError('EDA output must be a subdirectory of repository outputs/eda')
    output.mkdir(parents=True, exist_ok=True)
    inputs = [manifest, validation/'label_validation.csv', validation/'image_validation.csv',
              validation/'validation.json', triage, leakage, policy, classes_path]
    hashes = {str(p.relative_to(repository)): digest(p) for p in inputs}
    classes, samples, boxes, orphans = load_inventory(repository, manifest, validation, classes_path)
    labels = read_csv(validation/'label_validation.csv')
    orphan_labels = [r for r in labels if r['pairing_status'] == 'orphan_label']
    triaged = read_csv(triage)
    if {(r['split'], r['label_filename']) for r in triaged} != {(r['split'], r['label_filename']) for r in orphan_labels}:
        raise ValueError('Human triage does not cover the orphan inventory')
    decisions = read_csv(leakage)
    if any(r['review_authorized'].lower() != 'true' for r in decisions):
        raise ValueError('Leakage review is incomplete')
    result = tables(classes, samples, boxes, orphans, Counter(r['split'] for r in orphan_labels))
    paired = baseline_samples(samples)
    class_counts = [r['exact_pair_annotation_instances'] for r in result['class_distribution']]
    flags = []
    split_rows = result['split_comparison']
    for name in classes:
        shares = {r['split']: r[name+'_instance_share_percent'] for r in split_rows}
        if max(shares.values())-min(shares.values()) >= 5:
            flags.append(name+' instance shares: '+', '.join(f'{s} {v:.2f}%' for s, v in shares.items())+'.')
    for metric in ('annotation_density_mean', 'median_normalized_box_area', 'median_megapixels'):
        values = {r['split']: r[metric] for r in split_rows}
        if min(values.values()) > 0 and max(values.values())/min(values.values()) >= 1.25:
            flags.append(metric+': '+', '.join(f'{s} {v:.4g}' for s, v in values.items())+'.')
    resolutions = result['resolution_distribution']
    for w, h in sorted({(s['width'], s['height']) for s in samples}):
        shares = {split: sum(r['percent'] for r in resolutions if r['view'] == RAW and r['split'] == split
                            and r['width'] == w and r['height'] == h) for split in SPLITS}
        if max(shares.values())-min(shares.values()) >= 5:
            flags.append(f'Resolution {w}x{h} raw image shares: '+', '.join(f'{s} {v:.2f}%' for s, v in shares.items())+'.')
    summary = dict(total_images=len(samples), exact_pair_images=len(paired), unlabeled_images=len(samples)-len(paired),
        orphan_labels=len(orphan_labels), exact_pair_annotation_instances=len(boxes), orphan_annotation_instances=len(orphans),
        class_imbalance_ratio=max(class_counts)/min(class_counts) if min(class_counts) else None,
        median_annotations_per_image=stats([s['annotation_count'] for s in paired])['median'],
        median_normalized_box_area=stats([b['normalized_area'] for b in boxes])['median'],
        multi_class_percent=100*sum(len(s['classes']) > 1 for s in paired)/len(paired),
        near_border_boxes=sum(b['near_border'] for b in boxes), extreme_aspect_ratio_boxes=sum(b['extreme_aspect_ratio'] for b in boxes),
        exact_pair_rounding_warning_boxes=sum(b['rounding_warning'] for b in boxes),
        split_difference_flags=flags, leakage_outcomes=dict(Counter(r['human_outcome'] for r in decisions)),
        orphan_outcomes=dict(Counter(r['outcome'] for r in triaged)),
        repairs_authorized=sum(r['repair_authorized'].lower() == 'true' for r in triaged),
        input_sha256=hashes, source_sha256={p.name: digest(p) for p in (Path(__file__), repository/'scripts/data/eda_gyu_det.py')},
        methodology={'size_area_edges': [.001, .01, .1], 'near_border_distance': .01,
                     'extreme_pixel_aspect_ratio': [.1, 10], 'rounding_tolerance': 1e-6,
                     'normalized_cooccurrence': 'P(column present | row present)', 'no_images_decoded': True,
                     'supervised_view': BASELINE, 'leakage_members_removed': 0},
        validation_context=json.loads((validation/'validation.json').read_text(encoding='utf-8'))['summary'])
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in result.items():
        write_csv(output/(name+'.csv'), rows)
    summary['runtime_versions'] = figures(output/'figures', classes, samples, boxes, result)
    if hashes != {str(p.relative_to(repository)): digest(p) for p in inputs}:
        raise RuntimeError('Input artifacts changed during EDA')
    summary['input_artifacts_unchanged'] = True
    summary['size_distribution'] = [r for r in result['box_size_distribution'] if r['group_type'] == 'all']
    summary['class_distribution'] = result['class_distribution']
    inventory = [dict(path=name+'.csv', purpose=name.replace('_', ' ')) for name in result]
    inventory += [dict(path='figures/'+p.name, purpose='EDA figure') for p in sorted((output/'figures').glob('*.png'))]
    inventory += [dict(path=name, purpose=purpose) for name, purpose in
                  [('eda_summary.json', 'Statistics, provenance and methods'), ('eda_report.md', 'Interpretation and limitations'),
                   ('output_inventory.csv', 'Complete generated file inventory')]]
    write_csv(output/'output_inventory.csv', inventory)
    summary['outputs'] = [r['path'] for r in inventory]
    (output/'eda_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')
    (output/'eda_report.md').write_text(report(summary, result), encoding='utf-8')
    return summary
