"""Read-only integrity validation using the existing GYU pairing/triage inventories."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import platform
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageFile, __version__ as PILLOW_VERSION

from data.validators.gyu_pairing import IMAGE_EXTENSIONS, SPLITS, enumerate_entries, pairing_key
from data.validators.gyu_orphan_review import Box, box_pixels, parse_yolo, read_csv, safe_filename


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def issue(code: str, detail: str, row: int = 0, severity: str = 'error') -> dict[str, Any]:
    return dict(row_number=row, issue_code=code, severity=severity, detail=detail)


def status(issues: list[dict[str, Any]]) -> str:
    return 'invalid' if any(i['severity'] == 'error' for i in issues) else ('warning' if issues else 'valid')


def validate_image(path: Path) -> dict[str, Any]:
    """Hash bytes, verify structure, reopen and fully decode every frame; never save."""
    result: dict[str, Any] = dict(image_filename=path.name, exists=path.is_file(), file_size_bytes=None,
        image_sha256='', extension=Path(path.name.strip()).suffix.casefold(), decoded_format='',
        width=None, height=None, channels=None, image_mode='', exif_orientation=None,
        aspect_ratio=None, frame_count=None, primary_decode_success=False,
        decode_success=False, decoder_failure_stage='', issues=[])
    errors = result['issues']
    if result['extension'] not in IMAGE_EXTENSIONS:
        errors.append(issue('unsupported_image_extension', result['extension']))
    try:
        result['file_size_bytes'] = path.stat().st_size
        result['image_sha256'] = sha256(path)
        if not result['file_size_bytes']:
            errors.append(issue('zero_byte_image', 'Image file is empty'))
        else:
            with Image.open(path) as im:
                result.update(width=im.width, height=im.height, channels=len(im.getbands()),
                              image_mode=im.mode, decoded_format=im.format,
                              aspect_ratio=im.width / im.height if im.height else None)
                if im.width <= 0 or im.height <= 0:
                    errors.append(issue('invalid_image_dimensions', str(im.size)))
                try:
                    orientation = im.getexif().get(274)
                    result['exif_orientation'] = int(orientation) if orientation is not None else None
                    if orientation not in (None, 1):
                        errors.append(issue('exif_orientation', f'Stored orientation {orientation}; not transformed', severity='warning'))
                except (OSError, ValueError, TypeError, SyntaxError) as exc:
                    errors.append(issue('exif_read_error', str(exc), severity='warning'))
                expected = Image.registered_extensions().get(result['extension'])
                if expected and expected != im.format and not (expected == 'JPEG' and im.format == 'MPO'):
                    errors.append(issue('extension_format_mismatch', f"Extension expects {expected}, decoded {im.format}"))
            # PNG EXIF access may load pixels, invalidating verify() on that handle.
            # Structural verification therefore always gets a freshly opened handle.
            with Image.open(path) as checked:
                checked.verify()
            with Image.open(path) as im:
                result['frame_count'] = getattr(im, 'n_frames', 1)
                result['decoder_failure_stage'] = 'primary_frame'
                im.load()
                result['primary_decode_success'] = True
                for frame in range(1, result['frame_count']):
                    result['decoder_failure_stage'] = f'auxiliary_frame_{frame}'
                    im.seek(frame)
                    im.load()
            result['decode_success'] = True
            result['decoder_failure_stage'] = ''
    except (OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError) as exc:
        code = 'auxiliary_frame_decode_failure' if result['primary_decode_success'] else 'unreadable_or_corrupted_image'
        errors.append(issue(code, f'{type(exc).__name__}: {exc}'))
    if result['file_size_bytes'] == 0:
        result['decode_success'] = False
    result.update(validation_status=status(errors), validation_issue_count=len(errors))
    return result


def validate_label(path: Path, classes: list[str]) -> dict[str, Any]:
    """Accumulate row diagnostics; reuse the review parser and corner conversion."""
    result: dict[str, Any] = dict(label_filename=path.name, readable=False, label_sha256='',
        annotation_count=0, class_ids=[], empty=False, rows=[], issues=[])
    errors = result['issues']
    try:
        raw = path.read_bytes()
        result['label_sha256'] = hashlib.sha256(raw).hexdigest()
        text = raw.decode('utf-8-sig', errors='strict')
        result['readable'] = True
    except (OSError, UnicodeError) as exc:
        errors.append(issue('unreadable_label', f'{type(exc).__name__}: {exc}'))
        result.update(validation_status='invalid', validation_issue_count=len(errors))
        return result
    seen: dict[tuple[str, ...], int] = {}
    class_ids = set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        result['annotation_count'] += 1
        fields = line.split()
        row: dict[str, Any] = dict(row_number=number, raw_text=line, class_id=None,
                                  corners=None, duplicate=False, issues=[])
        ri = row['issues']
        tokens = tuple(fields)
        if tokens in seen:
            row['duplicate'] = True
            ri.append(issue('duplicate_annotation_row', f'Identical tokens to row {seen[tokens]}', number, 'warning'))
        else:
            seen[tokens] = number
        if len(fields) != 5:
            ri.append(issue('malformed_field_count', f'Expected 5 fields, got {len(fields)}', number))
        else:
            values = []
            for index, value in enumerate(fields):
                try:
                    numeric = float(value)
                    values.append(numeric)
                    if not math.isfinite(numeric):
                        ri.append(issue('nonfinite_value', f'Field {index + 1}: {value}', number))
                except ValueError:
                    values.append(None)
                    ri.append(issue('nonnumeric_value', f'Field {index + 1}: {value}', number))
            try:
                class_id = int(fields[0])
                if not 0 <= class_id < len(classes):
                    raise ValueError('outside class ordering')
                row['class_id'] = class_id
                class_ids.add(class_id)
            except ValueError:
                ri.append(issue('invalid_class_id', f'Expected integer token in [0,{len(classes)-1}]: {fields[0]}', number))
            coords = values[1:]
            if all(v is not None and math.isfinite(v) for v in coords):
                x, y, width, height = coords
                if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
                    ri.append(issue('normalized_value_out_of_range', str(coords), number))
                if width <= 0 or height <= 0:
                    ri.append(issue('zero_or_negative_box', f'width={width}, height={height}', number))
                box = Box(row['class_id'] or 0, x, y, width, height)
                if not any(i['severity'] == 'error' for i in ri):
                    box = parse_yolo(line, classes)[0]
                corners = box_pixels(box, (1, 1))
                row['corners'] = corners
                if width > 0 and height > 0 and (min(corners[:2]) < 0 or max(corners[2:]) > 1):
                    excess = max(0, -corners[0], -corners[1], corners[2]-1, corners[3]-1)
                    # Report even tiny serialization/rounding overshoots, without hiding them.
                    ri.append(issue('derived_box_outside_frame', f'normalized corners={corners}; max excess={excess:.12g}', number,
                                    'warning' if excess <= 1e-6 else 'error'))
        row['valid'] = not any(i['severity'] == 'error' for i in ri)
        result['rows'].append(row)
        errors.extend(ri)
    result['empty'] = result['annotation_count'] == 0
    if result['empty']:
        errors.append(issue('empty_label_file', 'No nonblank annotation rows; no negative-image identity inferred', severity='warning'))
    result['class_ids'] = sorted(class_ids)
    result.update(validation_status=status(errors), validation_issue_count=len(errors))
    return result


def manifest_row(image: dict[str, Any], label: dict[str, Any] | None, classes: list[str],
                 references: list[dict[str, Any]]) -> dict[str, Any]:
    issues = image['issues'] + (label['issues'] if label else [])
    if image['pairing_status'] == 'image_without_label':
        issues = issues + [issue('image_without_label', 'Unresolved missing annotation; not classified as negative', severity='warning')]
    result = dict(dataset='gyu_det', dataset_version='v3', split=image['split'],
                  image_filename=image['image_filename'], image_relative_path=image['image_relative_path'],
                  **{k: image[k] for k in ('image_sha256','file_size_bytes','width','height','channels','image_mode','exif_orientation')},
                  label_filename=label['label_filename'] if label else '',
                  label_relative_path=label['label_relative_path'] if label else '',
                  pairing_status=image['pairing_status'], annotation_count=label['annotation_count'] if label else None,
                  class_ids=label['class_ids'] if label else [],
                  class_names=[classes[i] for i in label['class_ids']] if label else [],
                  validation_status=status(issues), validation_issue_count=len(issues),
                  human_triage_outcome=references, repair_authorized=False)
    return result


def csv_output(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row.get(k), sort_keys=True, ensure_ascii=False) if isinstance(row.get(k), (list,dict))
                             else row.get(k) for k in fields})


def validate_dataset(root: Path, audit_dir: Path, classes_path: Path, output: Path,
                     manifest_path: Path, repository: Path, workers: int = 4,
                     progress: Callable[[str], None] = print) -> dict[str, Any]:
    root, audit_dir, classes_path, output, manifest_path, repository = (
        p.resolve() for p in (root, audit_dir, classes_path, output, manifest_path, repository))
    protected = (repository / 'data/raw').resolve()
    for target in (output, manifest_path, manifest_path.with_suffix('.parquet')):
        if any(target == p or p in target.parents for p in (protected, root)):
            raise ValueError('Validation output must be outside data/raw and the input root')
    if output == audit_dir or audit_dir / 'orphan_review' == output or audit_dir / 'orphan_review' in output.parents:
        raise ValueError('Use a separate full_validation directory; preserve existing audit and triage')
    classes = classes_path.read_text(encoding='utf-8-sig').splitlines()
    if not classes or any(not c.strip() for c in classes):
        raise ValueError('Authoritative classes.txt must have a nonempty name on each line')
    classes = [c.strip() for c in classes]
    review = audit_dir / 'orphan_review'
    sources = [audit_dir / n for n in ('matched_pairs.csv','unmatched_images.csv','unmatched_labels.csv','pairing_summary.csv')]
    sources += [review / 'human_triage_decisions.csv', review / 'index.csv', classes_path]
    input_hashes = {str(p.relative_to(repository)): sha256(p) for p in sources}
    pairs, unimages, unlabels, pairing_summary, decisions, review_index = [read_csv(p) for p in sources[:-1]]
    image_map: dict[tuple[str,str], tuple[str,str]] = {}
    label_map: dict[tuple[str,str], tuple[str,str]] = {}
    for row in pairs:
        split, im, lab = row['split'], safe_filename(row['image_filename']), safe_filename(row['label_filename'])
        if split not in SPLITS or pairing_key(im) != pairing_key(lab):
            raise ValueError('Invalid existing exact-pair inventory; investigate without rewriting audit')
        if (split, im) in image_map or (split, lab) in label_map:
            raise ValueError('Duplicate record in exact-pair inventory')
        image_map[split, im] = ('exact_pair', lab)
        label_map[split, lab] = ('exact_pair', im)
    for rows, mapping, kind in ((unimages,image_map,'image_without_label'), (unlabels,label_map,'orphan_label')):
        for row in rows:
            key = row['split'], safe_filename(row['filename'])
            if key[0] not in SPLITS or key in mapping:
                raise ValueError('Conflicting pairing inventory')
            mapping[key] = kind, ''
    triage = {(r['label_split'],r['label_filename']): r for r in decisions}
    if len(triage) != len(decisions) or set(triage) != {(r['split'],r['filename']) for r in unlabels}:
        raise ValueError('Triage coverage differs from orphan inventory')
    if any(r['repair_authorized'].lower() != 'false' for r in decisions):
        raise ValueError('Unexpected repair authorization; this validator never applies repairs')
    refs: dict[tuple[str,str], list[dict[str, Any]]] = defaultdict(list)
    for row in review_index:
        if row['review_status'] != 'pending':
            refs[row['candidate_image_split'], row['candidate_image_filename']].append(dict(
                label_split=row['label_split'], label_filename=row['label_filename'],
                candidate_review_status=row['review_status'], role='diagnostic_candidate_only',
                tentative_preference=row['reviewer_selected_candidate'] == row['candidate_image_filename']))
    inventory_issues = []
    image_jobs, label_jobs = [], []
    raw_before = {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    for split in SPLITS:
        # Reuse original enumeration for supported images and labels; also detect unsupported files.
        observed_images = {e.path.name for e in enumerate_entries(root, split, 'images')}
        all_image_files = {p.name for p in (root/split/split/'images').iterdir() if p.is_file()}
        observed_labels = {e.path.name for e in enumerate_entries(root, split, 'labels')}
        expected_images = {name for s,name in image_map if s == split}
        expected_labels = {name for s,name in label_map if s == split}
        for kind, observed, expected in (('images', all_image_files, expected_images), ('labels', observed_labels, expected_labels)):
            for name in sorted(observed ^ expected):
                inventory_issues.append(dict(split=split,kind=kind,filename=name,
                    issue='not_in_existing_pairing_audit' if name in observed else 'missing_from_disk'))
        image_jobs.extend((split,root/split/split/'images'/name) for name in sorted(all_image_files | expected_images))
        label_jobs.extend((split,root/split/split/'labels'/name) for name in sorted(observed_labels | expected_labels))
    label_results = []
    for split, path in label_jobs:
        record = validate_label(path, classes)
        pair_status, im = label_map.get((split,path.name), ('not_in_pairing_audit',''))
        record.update(split=split, label_relative_path=path.relative_to(repository).as_posix(),
                      pairing_status=pair_status, image_filename=im,
                      human_triage_outcome=triage.get((split,path.name),{}).get('review_status',''), repair_authorized=False)
        label_results.append(record)
    progress(f'Validated all {len(label_results)} annotation files; decoding {len(image_jobs)} images with {workers} workers.')
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    image_results = []
    def image_job(job: tuple[str, Path]) -> dict[str, Any]:
        split, path = job
        record = validate_image(path)
        record.update(split=split,image_relative_path=path.relative_to(repository).as_posix(),
                      pairing_status=image_map.get((split,path.name),('not_in_pairing_audit',''))[0])
        if record['pairing_status'] == 'not_in_pairing_audit':
            record['issues'].append(issue('not_in_pairing_audit','File absent from existing audit'))
        return record
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for n, record in enumerate(executor.map(image_job, image_jobs),1):
            image_results.append(record)
            if n % 500 == 0:
                progress(f'Images fully decoded and hashed: {n}/{len(image_jobs)}')
    resolutions = Counter((r['width'],r['height']) for r in image_results if r['primary_decode_success'])
    for r in image_results:
        if r['primary_decode_success']:
            reasons = []
            if min(r['width'],r['height']) < 256: reasons.append('minimum dimension <256')
            if max(r['width'],r['height']) > 10000: reasons.append('maximum dimension >10000')
            if not .2 <= r['aspect_ratio'] <= 5: reasons.append('aspect ratio outside [0.2,5]')
            if resolutions[r['width'],r['height']] < 10: reasons.append('resolution appears fewer than 10 times')
            if reasons:
                r['issues'].append(issue('unusual_resolution', '; '.join(reasons), severity='warning'))
        r.update(validation_status=status(r['issues']),validation_issue_count=len(r['issues']))
    label_lookup = {(r['split'],r['label_filename']): r for r in label_results}
    manifest = []
    for r in image_results:
        lab = image_map.get((r['split'],r['image_filename']), ('',''))[1]
        manifest.append(manifest_row(r, label_lookup.get((r['split'],lab)), classes, refs[r['split'],r['image_filename']]))
    annotation_issues = [dict(split=r['split'],label_filename=r['label_filename'],pairing_status=r['pairing_status'],**i)
                         for r in label_results for i in r['issues']]
    image_issues = [dict(split=r['split'],image_filename=r['image_filename'],**i) for r in image_results for i in r['issues']]
    instance_counts: Counter = Counter()
    valid_counts: Counter = Counter()
    orphan_counts: Counter = Counter()
    containing: dict[tuple[str,int], set[str]] = defaultdict(set)
    for r in label_results:
        for box in r['rows']:
            class_id = box['class_id']
            if class_id is not None:
                key = r['split'],class_id
                instance_counts[key] += 1
                valid_counts[key] += box['valid']
                orphan_counts[key] += r['pairing_status'] == 'orphan_label'
                if r['pairing_status'] == 'exact_pair': containing[key].add(r['image_filename'])
    class_stats = [dict(split=s,raw_class_id=i,raw_class_name=name,annotation_instances=instance_counts[s,i],
                       valid_annotation_instances=valid_counts[s,i],orphan_annotation_instances=orphan_counts[s,i],
                       images_containing_class=len(containing[s,i])) for s in SPLITS for i,name in enumerate(classes)]
    resolution_stats = []
    for (width,height),count in sorted(resolutions.items(),key=lambda item:(-item[1],item[0])):
        resolution_stats.append(dict(width=width,height=height,aspect_ratio=width/height,total_images=count,
            **{s:sum(r['split']==s and r['primary_decode_success'] and r['width']==width and r['height']==height for r in image_results) for s in SPLITS}))
    codes = Counter(i['issue_code'] for i in annotation_issues)
    syntax_codes = {'malformed_field_count','nonnumeric_value','invalid_class_id','nonfinite_value','unreadable_label'}
    summary: dict[str, Any] = dict(total_images_validated=len(image_results),total_label_files_validated=len(label_results),
        corrupted_unreadable_images=sum(not r['decode_success'] for r in image_results),
        primary_image_decode_failures=sum(not r['primary_decode_success'] for r in image_results),
        auxiliary_frame_decode_failures=sum(r['primary_decode_success'] and not r['decode_success'] for r in image_results),
        unreadable_labels=codes['unreadable_label'],
        malformed_label_files=sum(any(i['issue_code'] in syntax_codes for i in r['issues']) for r in label_results),
        invalid_label_files=sum(r['validation_status']=='invalid' for r in label_results),
        invalid_annotation_rows=sum(not row['valid'] for r in label_results for row in r['rows']),
        invalid_class_id_rows=codes['invalid_class_id'], nonfinite_value_issues=codes['nonfinite_value'],
        out_of_range_normalized_rows=codes['normalized_value_out_of_range'],
        derived_boxes_outside_frame=codes['derived_box_outside_frame'],
        out_of_range_box_rows=sum(any(i['issue_code'] in {'normalized_value_out_of_range','derived_box_outside_frame'} for i in row['issues']) for r in label_results for row in r['rows']),
        zero_negative_box_rows=codes['zero_or_negative_box'], duplicate_annotation_rows=codes['duplicate_annotation_row'],
        empty_label_files=codes['empty_label_file'],exact_pairs=len(pairs),image_without_label=len(unimages),orphan_labels=len(unlabels),
        unsupported_image_formats=sum(any(i['issue_code']=='unsupported_image_extension' for i in r['issues']) for r in image_results),
        unusual_resolution_images=sum(any(i['issue_code']=='unusual_resolution' for i in r['issues']) for r in image_results),
        unique_resolutions=len(resolutions),manifest_rows=len(manifest),inventory_discrepancies=len(inventory_issues),
        human_triaged_orphans=len(triage),confirmed_mappings=0,repairs_authorized=0)
    raw_after = {str(p): (p.stat().st_size,p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
    if raw_before != raw_after:
        raise RuntimeError('Raw input paths/size/mtime changed during validation; results not published')
    if input_hashes != {str(p.relative_to(repository)): sha256(p) for p in sources}:
        raise RuntimeError('Existing audit/triage inputs changed during validation; results not published')
    output.mkdir(parents=True,exist_ok=True)
    manifest_path.parent.mkdir(parents=True,exist_ok=True)
    csv_output(output/'validation_summary.csv',[dict(metric=k,value=v) for k,v in summary.items()],['metric','value'])
    csv_output(output/'image_validation.csv',image_results,[k for k in image_results[0] if k!='issues']+['issues'])
    csv_output(output/'label_validation.csv',label_results,[k for k in label_results[0] if k!='rows'])
    csv_output(output/'annotation_issues.csv',annotation_issues,['split','label_filename','pairing_status','row_number','issue_code','severity','detail'])
    csv_output(output/'image_issues.csv',image_issues,['split','image_filename','row_number','issue_code','severity','detail'])
    csv_output(output/'class_statistics.csv',class_stats,list(class_stats[0]))
    csv_output(output/'resolution_statistics.csv',resolution_stats,['width','height','aspect_ratio','total_images',*SPLITS])
    csv_output(output/'inventory_issues.csv',inventory_issues,['split','kind','filename','issue'])
    csv_output(manifest_path,manifest,list(manifest[0]))
    parquet = 'not generated: pyarrow not installed; no dependency added'
    if importlib.util.find_spec('pyarrow') is not None:
        import pyarrow as pa
        import pyarrow.parquet as pq
        flat = [{k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in manifest]
        pq.write_table(pa.Table.from_pylist(flat),manifest_path.with_suffix('.parquet'))
        parquet = manifest_path.with_suffix('.parquet').relative_to(repository).as_posix()
    data = dict(summary=summary,archive_integrity='Previously verified complete per user; archives not re-tested by this extracted-file pass',
        python_version=platform.python_version(),pillow_version=PILLOW_VERSION, input_sha256=input_hashes,
        pairing_summary=pairing_summary,human_triage_outcomes=dict(Counter(r['review_status'] for r in decisions)),
        exif_orientation_counts=dict(Counter(str(r['exif_orientation']) if r['exif_orientation'] is not None else 'absent' for r in image_results)),
        image_mode_counts=dict(Counter(r['image_mode'] for r in image_results)), annotation_issue_counts=dict(codes),
        class_statistics=class_stats, resolution_statistics=resolution_stats,parquet=parquet,
        manifest_path=manifest_path.relative_to(repository).as_posix(), raw_paths_sizes_mtimes_unchanged=True,
        audit_and_triage_hashes_unchanged=True, inventory_issues=inventory_issues)
    (output/'validation.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    write_report(output/'validation_report.md',data)
    return data


def write_report(path: Path, data: dict[str, Any]) -> None:
    s = data['summary']
    lines = ['# GYU-DET V3 full read-only validation','',
        'This pass validates every inventoried image and every .txt label, including all orphan labels. '
        'No images are sampled, rewritten, reoriented, repaired, or used for training. M1 remains incomplete.','',
        '## Reproduce','', '```text',
        'python scripts/data/validate_gyu_det.py --root data/raw/gyu_det/v3/extracted --audit outputs/validation/gyu_det_v3 --classes data/raw/gyu_det/v3/archives/classes.txt --output outputs/validation/gyu_det_v3/full_validation --manifest data/manifests/gyu_det_v3_raw_manifest.csv',
        'python -m unittest discover -s tests/data -v','```','',
        'Python and Pillow versions and input audit/class SHA-256 hashes are in validation.json. '
        'SHA-256 is streamed for every image, including images which fail decoding. '
        'File metadata and audit/triage hashes are checked again before publishing outputs.','',
        '## Archive integrity','',data['archive_integrity']+'. This is separate from the checks below.','',
        '## Image integrity','',
        f"Images validated: {s['total_images_validated']}; strict all-frame integrity failures: {s['corrupted_unreadable_images']}; primary-image decode failures: {s['primary_image_decode_failures']}; auxiliary-frame failures: {s['auxiliary_frame_decode_failures']}; unsupported extensions: {s['unsupported_image_formats']}.",
        'JPEG files with MPF metadata can be recognized as MPO (multi-picture) containers. MPO is accepted '
        'under JPEG extensions. Auxiliary-frame failure remains an integrity error, but does not imply the '
        'primary image is unreadable. image_validation.csv separates primary_decode_success, decode_success '
        '(all declared frames), and decoder_failure_stage. Resolution statistics use successfully decoded primary images.',
        'Pillow verify() plus a separate reopen and full load() of every frame is used with truncated-image acceptance disabled. '
        'These are decoder-based checks, not a guarantee against every possible bit-level defect. '
        'Channel counts are stored bands (palette images are not silently converted). EXIF orientation is reported, never applied.',
        'EXIF counts: '+json.dumps(data['exif_orientation_counts'],sort_keys=True)+'.',
        'Image mode counts: '+json.dumps(data['image_mode_counts'],sort_keys=True)+'.','',
        '## Label syntax validity','',
        f"Label files: {s['total_label_files_validated']}; unreadable: {s['unreadable_labels']}; malformed files: {s['malformed_label_files']}; invalid class-ID rows: {s['invalid_class_id_rows']}; empty: {s['empty_label_files']}; duplicate extra rows: {s['duplicate_annotation_rows']}.",
        'UTF-8 is decoded strictly (optional BOM accepted); blank lines are ignored. Class IDs must parse with int(), '
        'so decimal/scientific class tokens are invalid. Malformed-file counts cover unreadable text, field counts, '
        'nonnumeric/nonfinite fields, and class IDs; geometry is reported separately. '
        'Duplicates mean identical whitespace-separated tokens; different numeric spellings are not silently equated. '
        'Empty labels are flagged but do not establish negative-image identity.','',
        '## Bounding-box validity','',
        f"Invalid annotation rows (any row-level error): {s['invalid_annotation_rows']}; normalized out-of-range rows: {s['out_of_range_normalized_rows']}; derived boxes outside frame: {s['derived_boxes_outside_frame']}; zero/negative dimensions: {s['zero_negative_box_rows']}.",
        'Corners use the existing YOLO-to-corners helper in normalized space, so the check also applies to orphan labels. '
        'Every outside corner is flagged; excess <=1e-6 is a warning for possible decimal-rounding effects, '
        'larger excess is an error. No clipping or correction is applied. Multiple issue rows can refer to one annotation.','',
        '## Pairing anomalies','',
        f"Exact pairs: {s['exact_pairs']}; images without labels: {s['image_without_label']}; orphan labels: {s['orphan_labels']}; inventory discrepancies: {s['inventory_discrepancies']}.",
        'Statuses come from the existing audit CSVs; no pairing conclusions are recomputed or overwritten. '
        'Missing/extra files are separately flagged as inventory drift. image_without_label does not mean negative.','',
        '## Human-triaged orphan labels','',
        'Existing outcomes: '+json.dumps(data['human_triage_outcomes'],sort_keys=True)+'.',
        'All orphan statuses are included in label_validation.csv. See ../orphan_review/final_triage_summary.csv '
        'and ../orphan_review/human_triage_decisions.csv for complete decisions. No plausible preference is a confirmed mapping. '
        'Manifest human_triage_outcome is a JSON array of candidate-review references from the existing index, '
        'not an annotation linkage. Candidate image label paths remain blank when no exact label exists.','',
        '## Unresolved negative-image identity','',
        'The supplied published total is 691 negative/no-defect images. 712 unlabeled images minus 21 orphan labels '
        'equals 691, but the relationship remains unproven. None is classified as negative here.','',
        '## Class statistics','',
        'Class IDs/names use the authoritative local archives/classes.txt line ordering. Annotation instances count '
        'every five-field row with a valid class-ID token, including duplicates and rows with coordinate errors. '
        'valid_annotation_instances excludes rows with errors. Images containing a class count distinct existing '
        'audit exact-pair filenames only; orphan annotations contribute instances but no inferred images.','',
        '| Split | ID | Class | Instances | Valid instances | Orphan instances | Images |',
        '|---|---:|---|---:|---:|---:|---:|']
    for r in data['class_statistics']:
        lines.append(f"| {r['split']} | {r['raw_class_id']} | {r['raw_class_name']} | {r['annotation_instances']} | {r['valid_annotation_instances']} | {r['orphan_annotation_instances']} | {r['images_containing_class']} |")
    lines += ['', '## Resolution statistics','',
        f"Unique decoded resolutions: {s['unique_resolutions']}; unusual-resolution images: {s['unusual_resolution_images']}.",
        'Heuristic warnings: minimum dimension <256, maximum >10000, aspect ratio outside [0.2,5], '
        'or fewer than 10 examples at that resolution. Rarity is not corruption. All resolutions are in resolution_statistics.csv.','',
        '| Width | Height | Count |','|---:|---:|---:|']
    for r in data['resolution_statistics'][:15]:
        lines.append(f"| {r['width']} | {r['height']} | {r['total_images']} |")
    lines += ['', '## Manifest and remaining work','',
        f"Manifest: {data['manifest_path']} ({s['manifest_rows']} image rows). Parquet: {data['parquet']}.",
        'Manifest validation_status aggregates image and paired-label diagnostics plus an unlabeled-image warning. '
        'Absent annotation_count is blank, not zero. Orphan labels are not inserted as image rows. '
        'Quality warnings do not authorize removal, correction, or negative classification.',
        'Human intervention is required for unresolved pairing/negative identity and any reported annotation '
        'or integrity errors before a training-data policy is accepted. This pass does not create training data.']
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
