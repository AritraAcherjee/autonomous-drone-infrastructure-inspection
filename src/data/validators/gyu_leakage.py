"""Deterministic duplicate/leakage diagnostics; never alter raw data or splits."""

from __future__ import annotations

import bisect
import hashlib
import importlib.util
import itertools
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFont, ImageStat, __version__ as PILLOW_VERSION

from data.validators.gyu_pairing import SPLITS, pairing_key
from data.validators.gyu_orphan_review import read_csv
from data.validators.gyu_full_validation import csv_output

RADIUS = 12
PAIR_FIELDS = ['image_a','split_a','relative_path_a','image_b','split_b','relative_path_b',
    'split_pair','sha256_a','sha256_b','sha256_equal','dimensions_a','dimensions_b',
    'aspect_ratio_a','aspect_ratio_b','dimensions_match','pairing_status_a','pairing_status_b',
    'perceptual_hash_a','perceptual_hash_b','hamming_distance','candidate_severity',
    'numeric_difference','same_camera','same_capture_time','low_information_fingerprint']


def split_pair(a: str, b: str) -> str:
    return '/'.join(sorted((a,b), key=SPLITS.index))


def difference_hash(image: Image.Image) -> str:
    """128 bits: row-major horizontal 8x8 differences, then vertical 8x8.

    Stored primary pixel orientation, grayscale, LANCZOS resampling, strict >.
    No learned features and no EXIF rotation. Hex is fixed-width lowercase.
    """
    gray = image.convert('L')
    horizontal = list(gray.resize((9,8), Image.Resampling.LANCZOS).getdata())
    vertical = list(gray.resize((8,9), Image.Resampling.LANCZOS).getdata())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | (horizontal[y*9+x+1] > horizontal[y*9+x])
    for y in range(8):
        for x in range(8):
            value = (value << 1) | (vertical[(y+1)*8+x] > vertical[y*8+x])
    return f'{value:032x}'


def fingerprint(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = dict(perceptual_hash='',fingerprint_status='ok',fingerprint_error='',
        camera_make='',camera_model='',exif_datetime='',exif_datetime_original='',
        metadata_warning='',grayscale_stddev=None,low_information_fingerprint=False)
    try:
        with Image.open(path) as image:
            image.seek(0)
            image.load()
            result['perceptual_hash'] = difference_hash(image)
            result['grayscale_stddev'] = round(ImageStat.Stat(image.convert('L').resize((32,32))).stddev[0],6)
            bits = int(result['perceptual_hash'],16).bit_count()
            result['low_information_fingerprint'] = result['grayscale_stddev'] < 5 or bits <= 8 or bits >= 120
            try:
                exif = image.getexif()
                nested = exif.get_ifd(34665) if 34665 in exif else {}
                def clean(value: Any) -> str:
                    return (value.decode('utf-8',errors='replace') if isinstance(value,bytes) else str(value)).strip('\x00 ')
                result.update(camera_make=clean(exif.get(271,'')),camera_model=clean(exif.get(272,'')),
                    exif_datetime=clean(exif.get(306,'')),
                    exif_datetime_original=clean(nested.get(36867,exif.get(36867,''))))
            except (OSError,ValueError,TypeError,SyntaxError) as exc:
                result['metadata_warning'] = str(exc)
    except (OSError,ValueError,SyntaxError,EOFError) as exc:
        result.update(fingerprint_status='failed',fingerprint_error=f'{type(exc).__name__}: {exc}')
    return result


class HammingIndex:
    """BK-tree over unique fingerprints; exact metric radius search, not sampling."""
    def __init__(self) -> None:
        self.nodes: list[tuple[int,list[int],dict[int,int]]] = []

    def add(self, value: int, item: int) -> None:
        if not self.nodes:
            self.nodes.append((value,[item],{}))
            return
        cursor = 0
        while True:
            pivot, items, children = self.nodes[cursor]
            distance = (value ^ pivot).bit_count()
            if distance == 0:
                items.append(item)
                return
            if distance not in children:
                children[distance] = len(self.nodes)
                self.nodes.append((value,[item],{}))
                return
            cursor = children[distance]

    def query(self, value: int, radius: int) -> list[tuple[int,int]]:
        matches = []
        stack = [0] if self.nodes else []
        while stack:
            pivot, items, children = self.nodes[stack.pop()]
            distance = (value ^ pivot).bit_count()
            if distance <= radius:
                matches.extend((item,distance) for item in items)
            stack.extend(child for edge,child in children.items() if distance-radius <= edge <= distance+radius)
        return sorted(matches)


def severity(distance: int) -> str:
    if distance == 0: return 'identical_perceptual_hash'
    if distance <= 4: return 'very_strong_near_duplicate'
    if distance <= 8: return 'probable_near_duplicate'
    return 'weaker_candidate'


def grouped(rows: list[dict[str, Any]], key: str) -> list[list[int]]:
    groups: dict[str,list[int]] = defaultdict(list)
    for n,row in enumerate(rows):
        groups[str(row[key])].append(n)
    return [members for _,members in sorted(groups.items()) if len(members)>1]


def exact_groups(rows: list[dict[str, Any]]) -> list[list[int]]:
    return grouped(rows,'image_sha256')


def basename_groups(rows: list[dict[str, Any]]) -> list[list[int]]:
    return grouped([dict(r,normalized_basename=pairing_key(r['image_filename'])) for r in rows],'normalized_basename')


def near_pairs(rows: list[dict[str, Any]], radius: int = RADIUS) -> list[tuple[int,int,int]]:
    index = HammingIndex()
    matches = []
    # Query a whole split before inserting it, avoiding same-split candidates entirely.
    for split in SPLITS:
        members = [n for n,r in enumerate(rows) if r['split']==split and r.get('perceptual_hash')]
        for n in members:
            value = int(rows[n]['perceptual_hash'],16)
            matches.extend((m,n,distance) for m,distance in index.query(value,radius))
        for n in members: index.add(int(rows[n]['perceptual_hash'],16),n)
    return sorted(matches,key=lambda r:(r[2],r[0],r[1]))


def numeric_key(row: dict[str, Any]) -> int | None:
    stem = pairing_key(row['image_filename'])
    return int(stem) if stem.isascii() and stem.isdecimal() else None


def pair_row(a: dict[str, Any], b: dict[str, Any], distance: int | None) -> dict[str, Any]:
    na, nb = numeric_key(a), numeric_key(b)
    camera_a, camera_b = (a.get('camera_make',''),a.get('camera_model','')), (b.get('camera_make',''),b.get('camera_model',''))
    time_a = a.get('exif_datetime_original') or a.get('exif_datetime','')
    time_b = b.get('exif_datetime_original') or b.get('exif_datetime','')
    result: dict[str, Any] = dict(split_pair=split_pair(a['split'],b['split']),
        sha256_equal=a['image_sha256']==b['image_sha256'],dimensions_match=(a['width'],a['height'])==(b['width'],b['height']),
        hamming_distance=distance,candidate_severity=severity(distance) if distance is not None else 'exact_content_cross_split',
        numeric_difference=abs(na-nb) if na is not None and nb is not None else None,
        same_camera=bool(any(camera_a) and camera_a==camera_b),same_capture_time=bool(time_a and time_a==time_b),
        low_information_fingerprint=bool(a.get('low_information_fingerprint') or b.get('low_information_fingerprint')))
    for suffix,r in (('a',a),('b',b)):
        result.update({f'image_{suffix}':r['image_filename'],f'split_{suffix}':r['split'],
            f'relative_path_{suffix}':r['image_relative_path'],f'sha256_{suffix}':r['image_sha256'],
            f'dimensions_{suffix}':f"{r['width']}x{r['height']}",f'aspect_ratio_{suffix}':int(r['width'])/int(r['height']),
            f'pairing_status_{suffix}':r['pairing_status'],f'perceptual_hash_{suffix}':r.get('perceptual_hash','')})
    return result


def numeric_neighbors(rows: list[dict[str, Any]], radius: int = 2) -> list[tuple[int,int]]:
    result = []
    for sa,sb in itertools.combinations(SPLITS,2):
        a = [(numeric_key(r),n) for n,r in enumerate(rows) if r['split']==sa and numeric_key(r) is not None]
        b = sorted((numeric_key(r),n) for n,r in enumerate(rows) if r['split']==sb and numeric_key(r) is not None)
        values = [v for v,_ in b]
        for value,n in a:
            result.extend((n,m) for _,m in b[bisect.bisect_left(values,value-radius):bisect.bisect_right(values,value+radius)])
    return sorted(result)


def review_sheets(rows: list[dict[str, Any]], repository: Path, directory: Path, limit: int = 24) -> tuple[int,list[str]]:
    selected = sorted(rows,key=lambda r:(not r['sha256_equal'],r['hamming_distance'] if r['hamming_distance'] is not None else -1,
        r['split_a'],r['image_a'],r['split_b'],r['image_b']))[:limit]
    failures = []
    directory.mkdir(parents=True,exist_ok=True)
    index = []
    for page in range(math_ceil(len(selected),4)):
        subset = selected[page*4:page*4+4]
        canvas = Image.new('RGB',(1280,90+len(subset)*430),'#111C27')
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default(size=18)
        draw.text((20,15),'GYU-DET cross-split review | candidates, not accepted leakage decisions',font=font,fill='white')
        draw.text((20,47),'Stored primary pixels; no EXIF rotation. Inspect geometry, scene and metadata.',font=font,fill='#FFCE62')
        sheet_name = f'cross_split_review_{page+1:02d}.png'
        for n,row in enumerate(subset):
            y = 90+n*430
            draw.text((20,y),f"{row['candidate_severity']} | Hamming {row['hamming_distance']} | SHA equal: {row['sha256_equal']}",font=font,fill='#FFCE62')
            for x,suffix in ((20,'a'),(650,'b')):
                draw.text((x,y+28),f"{row['split_'+suffix]}/{row['image_'+suffix]} | {row['dimensions_'+suffix]}",font=font,fill='white')
                try:
                    with Image.open(repository/row['relative_path_'+suffix]) as im:
                        im.seek(0); im.load()
                        panel=im.convert('RGB'); panel.thumbnail((610,350),Image.Resampling.LANCZOS)
                    canvas.paste(panel,(x+(610-panel.width)//2,y+58+(350-panel.height)//2))
                except (OSError,ValueError,SyntaxError) as exc:
                    failures.append(str(exc)); draw.text((x,y+80),'IMAGE LOAD FAILED',font=font,fill='red')
            index.append(dict(row,review_sheet_path=sheet_name,review_status='pending',review_notes=''))
        canvas.save(directory/sheet_name)
    csv_output(directory/'index.csv',index,PAIR_FIELDS+['review_sheet_path','review_status','review_notes'])
    return len(selected),failures


def math_ceil(n: int, divisor: int) -> int:
    return (n+divisor-1)//divisor


POLICY = '''# GYU-DET V3 provisional baseline eligibility policy

This policy is for analysis only. It does not approve final splits, a processed
training export, or training. M1 remains incomplete.

- The 10,411 exact image-label pairs are candidate baseline supervised samples,
  subject to leakage review and an eventual approved training-reader policy.
- All 21 orphan annotations are excluded from baseline eligibility until mappings
  are explicitly confirmed. Tentative human preferences are not repairs.
- All 712 images without labels remain UNCLASSIFIED, not negative. The published
  691 negatives must not be inferred by subtraction.
- Auxiliary MPO-frame failures are warning-only under this provisional policy
  because all primary images decoded in the full Pillow validation. They become
  a reader-compatibility concern if the eventual training reader cannot read the
  primary image. No MPO image is modified or excluded by this audit.
- Derived boundary overshoots <=1e-6 normalized units are rounding warnings;
  raw labels are not clipped, rewritten, or corrected.
- This policy does not overwrite the earlier strict full-validation flags.
- Raw files, official split membership, all 21 human decisions, and repair
  authorization remain unchanged. No final training data has been approved.
'''


def run_audit(repository: Path, manifest_path: Path, validation_dir: Path, output: Path,
              review_dir: Path, workers: int = 8, progress: Callable[[str],None] = print) -> dict[str, Any]:
    repository,manifest_path,validation_dir,output,review_dir = (p.resolve() for p in (repository,manifest_path,validation_dir,output,review_dir))
    raw = (repository/'data/raw').resolve()
    for target in (output,review_dir):
        if target==raw or raw in target.parents or target==validation_dir or validation_dir in target.parents:
            raise ValueError('Use dedicated leakage outputs outside raw and full-validation inputs')
    if (review_dir/'index.csv').exists():
        raise ValueError('Existing review index will not be overwritten; use fresh audit/review directories')
    records = read_csv(manifest_path)
    if len({r['image_relative_path'] for r in records}) != len(records): raise ValueError('Duplicate manifest paths')
    for r in records:
        if r['split'] not in SPLITS or len(r['image_sha256'])!=64: raise ValueError('Invalid manifest split or SHA-256')
        path=(repository/r['image_relative_path']).resolve()
        if raw not in path.parents: raise ValueError('Manifest image path outside raw')
        if path.stat().st_size != int(r['file_size_bytes']): raise ValueError(f'Manifest size drift: {path}')
    records.sort(key=lambda r:(SPLITS.index(r['split']),r['image_filename'].casefold(),r['image_filename']))
    inputs = [manifest_path,validation_dir/'image_validation.csv']
    orphan_dir=validation_dir.parent/'orphan_review'
    inputs.extend(orphan_dir/n for n in ('human_triage_decisions.csv','index.csv','final_triage_summary.csv'))
    hashes = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    snapshots = {r['image_relative_path']: ((repository/r['image_relative_path']).stat().st_size,
                                         (repository/r['image_relative_path']).stat().st_mtime_ns) for r in records}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for n,(record,fp) in enumerate(zip(records,executor.map(fingerprint,[repository/r['image_relative_path'] for r in records])),1):
            record.update(fp)
            if n%500==0: progress(f'Primary-image perceptual fingerprints: {n}/{len(records)}')
    progress('Fingerprinting complete; searching exact hashes, basenames and Hamming neighborhoods.')
    exact = exact_groups(records)
    exact_members, exact_cross, exact_pairs_within = [], [], Counter()
    for group_id,members in enumerate(exact,1):
        splits={records[n]['split'] for n in members}
        for n in members:
            r=records[n]
            exact_members.append(dict(group_id=group_id,sha256=r['image_sha256'],filename=r['image_filename'],
                split=r['split'],relative_path=r['image_relative_path'],dimensions=f"{r['width']}x{r['height']}",
                pairing_status=r['pairing_status'],group_scope='cross_split' if len(splits)>1 else 'within_split'))
        for a,b in itertools.combinations(members,2):
            if records[a]['split']==records[b]['split']:
                exact_pairs_within[records[a]['split']]+=1
            else:
                ha,hb=records[a]['perceptual_hash'],records[b]['perceptual_hash']
                distance=(int(ha,16)^int(hb,16)).bit_count() if ha and hb else None
                row=pair_row(records[a],records[b],distance); row['candidate_severity']='exact_content_cross_split'
                exact_cross.append(row)
    collisions = basename_groups(records)
    collision_rows = []
    for group_id,members in enumerate(collisions,1):
        for n in members:
            r=records[n]
            collision_rows.append(dict(group_id=group_id,normalized_basename=pairing_key(r['image_filename']),
                filename=r['image_filename'],split=r['split'],relative_path=r['image_relative_path'],sha256=r['image_sha256'],
                same_content=len({records[m]['image_sha256'] for m in members})==1,
                group_scope='cross_split' if len({records[m]['split'] for m in members})>1 else 'within_split'))
    near = [pair_row(records[a],records[b],distance) for a,b,distance in near_pairs(records)]
    numeric = []
    for a,b in numeric_neighbors(records):
        ha,hb=records[a]['perceptual_hash'],records[b]['perceptual_hash']
        distance=(int(ha,16)^int(hb,16)).bit_count() if ha and hb else None
        row=pair_row(records[a],records[b],distance)
        row['candidate_severity']='numeric_neighbor_only' if distance is None or distance>RADIUS else severity(distance)
        numeric.append(row)
    capture_groups: dict[tuple[str,str,str],list[int]] = defaultdict(list)
    for n,r in enumerate(records):
        timestamp=r['exif_datetime_original'] or r['exif_datetime']
        if timestamp and (r['camera_make'] or r['camera_model']):
            capture_groups[r['camera_make'],r['camera_model'],timestamp].append(n)
    capture_rows=[]
    for (make,model,timestamp),members in sorted(capture_groups.items()):
        if len({records[m]['split'] for m in members})>1:
            for n in members:
                r=records[n]
                capture_rows.append(dict(make=make,model=model,capture_time=timestamp,split=r['split'],filename=r['image_filename'],relative_path=r['image_relative_path']))
    review_candidates={(r['relative_path_a'],r['relative_path_b']):r for r in near}
    review_candidates.update({(r['relative_path_a'],r['relative_path_b']):r for r in exact_cross})
    progress(f'Cross-split perceptual candidates: {len(near)}. Preparing at most 24 review pairs.')
    review_count,render_failures=review_sheets(list(review_candidates.values()),repository,review_dir)
    cv_available=importlib.util.find_spec('cv2') is not None
    mpo=[r for r in read_csv(validation_dir/'image_validation.csv') if r['primary_decode_success']=='True' and r['decode_success']=='False']
    compatibility=[]
    if cv_available:
        import cv2
        for r in mpo:
            loaded=cv2.imread(str(repository/r['image_relative_path']))
            width,height=(loaded.shape[1],loaded.shape[0]) if loaded is not None else (None,None)
            compatibility.append(dict(split=r['split'],filename=r['image_filename'],loaded=loaded is not None,
                expected_width=r['width'],expected_height=r['height'],reader_width=width,reader_height=height,
                dimensions_match=(width,height)==(int(r['width']),int(r['height']))))
    thresholds=Counter(r['candidate_severity'] for r in near)
    summary=dict(images=len(records),fingerprint_failures=sum(r['fingerprint_status']!='ok' for r in records),
        exact_duplicate_groups=len(exact),within_split_exact_duplicate_pairs=sum(exact_pairs_within.values()),
        cross_split_exact_duplicate_pairs=len(exact_cross),basename_collision_groups=len(collisions),
        within_split_basename_collision_pairs=sum(records[a]['split']==records[b]['split'] for g in collisions for a,b in itertools.combinations(g,2)),
        cross_split_basename_collision_pairs=sum(records[a]['split']!=records[b]['split'] for g in collisions for a,b in itertools.combinations(g,2)),
        cross_split_identical_perceptual_hash=thresholds['identical_perceptual_hash'],
        cross_split_very_strong=thresholds['very_strong_near_duplicate'],cross_split_probable=thresholds['probable_near_duplicate'],
        cross_split_weaker=thresholds['weaker_candidate'],candidate_pairs_needing_review=len(review_candidates),
        review_pairs_shown=review_count,review_sheet_count=math_ceil(review_count,4),rendering_failures=len(render_failures),
        numeric_neighbor_pairs=len(numeric),numeric_neighbors_also_perceptual=sum(r['hamming_distance'] is not None and r['hamming_distance']<=RADIUS for r in numeric),
        cross_split_capture_metadata_groups=len({(r['make'],r['model'],r['capture_time']) for r in capture_rows}),
        mpo_images=len(mpo),opencv_check='performed' if cv_available else 'skipped: OpenCV not installed',
        opencv_load_failures=sum(not r['loaded'] for r in compatibility),opencv_dimension_mismatches=sum(r['loaded'] and not r['dimensions_match'] for r in compatibility))
    for r in records:
        p=repository/r['image_relative_path']
        if snapshots[r['image_relative_path']]!=(p.stat().st_size,p.stat().st_mtime_ns): raise RuntimeError('Raw image metadata changed during audit')
    if hashes!={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}: raise RuntimeError('Protected input changed during audit')
    output.mkdir(parents=True,exist_ok=True)
    csv_output(output/'exact_duplicate_groups.csv',exact_members,['group_id','sha256','filename','split','relative_path','dimensions','pairing_status','group_scope'])
    csv_output(output/'cross_split_exact_duplicates.csv',exact_cross,PAIR_FIELDS)
    csv_output(output/'basename_collisions.csv',collision_rows,['group_id','normalized_basename','filename','split','relative_path','sha256','same_content','group_scope'])
    csv_output(output/'perceptual_hashes.csv',records,['split','image_filename','image_relative_path','image_sha256','width','height','pairing_status','exif_orientation','perceptual_hash','fingerprint_status','fingerprint_error','grayscale_stddev','low_information_fingerprint','camera_make','camera_model','exif_datetime','exif_datetime_original','metadata_warning'])
    csv_output(output/'cross_split_near_duplicates.csv',near,PAIR_FIELDS)
    csv_output(output/'numeric_filename_neighbors.csv',numeric,PAIR_FIELDS)
    csv_output(output/'capture_metadata_groups.csv',capture_rows,['make','model','capture_time','split','filename','relative_path'])
    csv_output(output/'mpo_opencv_compatibility.csv',compatibility,['split','filename','loaded','expected_width','expected_height','reader_width','reader_height','dimensions_match'])
    csv_output(output/'leakage_summary.csv',[dict(metric=k,value=v) for k,v in summary.items()],['metric','value'])
    data=dict(summary=summary,pillow_version=PILLOW_VERSION,hash_algorithm='128-bit horizontal+vertical dHash; stored primary orientation; LANCZOS',
        thresholds={'identical':0,'very_strong':[1,4],'probable':[5,8],'weaker':[9,12]},
        input_sha256={str(p.relative_to(repository)):v for p,v in hashes.items()},
        within_split_exact_pairs={s:exact_pairs_within[s] for s in SPLITS},
        cross_split_exact_pairs=dict(Counter(r['split_pair'] for r in exact_cross)),
        cross_split_candidates_by_split_pair=dict(Counter(r['split_pair'] for r in near)),
        cumulative_candidate_counts={str(k):sum(r['hamming_distance']<=k for r in near) for k in (0,4,8,12)},
        render_failures=render_failures,raw_metadata_unchanged=True,protected_inputs_unchanged=True,
        image_sha256_source='existing manifest only; image bytes not rehashed')
    (output/'leakage_validation.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (output.parent/'baseline_data_policy.md').write_text(POLICY,encoding='utf-8')
    report=['# GYU-DET V3 duplicate and leakage audit','',
        'Analysis only. Raw data, official split membership, the source manifest and human triage are unchanged. '
        'No final training export, deletion, orphan repair, or negative classification is approved. M1 remains incomplete.','',
        '## Method and reproducibility','',
        'Run `python scripts/data/audit_gyu_leakage.py` from the repository root. Run tests with '
        '`python -m unittest discover -s tests/data -v`. Existing review indexes are protected: '
        'use fresh --output and --review directories for another run.',
        'Exact comparisons reuse SHA-256 from the existing manifest without rehashing images. '
        'Raw file sizes are checked against the manifest; size/mtime and protected input hashes are checked at completion. '
        'Therefore exact conclusions depend on the trusted manifest; equal-size external modifications predating this run are not detected.',
        'Every primary image is loaded. Fingerprints use 128 deterministic dHash bits: 64 horizontal '
        '8x8 comparisons after 9x8 grayscale LANCZOS resize, then 64 vertical comparisons after '
        '8x9 resize. Strict greater-than comparison, row-major order, fixed 32-digit hexadecimal. '
        'Pillow version is recorded. EXIF rotation is not applied; rotated or cropped copies can be missed.',
        'A BK-tree searches all cross-split fingerprints with Hamming radius 12; it is an exact metric search, '
        'not a sample or naive all-pairs scan. All qualifying pairs are exported, not just the displayed review subset.',
        'Disjoint diagnostic tiers: distance 0 identical hash; 1-4 very strong; 5-8 probable; 9-12 weaker. '
        'These allow at most 3.125%, 6.25%, and 9.375% of bits to differ. Thresholds are heuristic, '
        'not calibrated probabilities or proof of leakage. Uniform/low-information scenes can collide. '
        'Low grayscale contrast or extreme hash bit counts are flagged. Exact cross-split content duplication '
        'is established by manifest SHA equality; perceptual similarity alone never establishes a leak.',
        'Normalized basename collisions trim whitespace and case-fold stems; they do not imply matching content. '
        'Numeric filenames within absolute difference 2 are searched by sorted bisect ranges. '
        'Capture-series signals include numeric neighbors, matching camera make/model, and equal EXIF capture '
        'timestamps; no reliable temporal ordering, timezone or session identity is assumed. '
        'Missing metadata is not an error. Primary pixels alone contribute to fingerprints.','',
        '## Results','', '| Metric | Value |','|---|---|']
    report.extend(f'| {key} | {value} |' for key,value in summary.items())
    report+=['', 'Within-split exact pair counts: '+json.dumps(data['within_split_exact_pairs'])+'.',
        'Cross-split exact pair counts: '+json.dumps(data['cross_split_exact_pairs'])+'.',
        'Cross-split perceptual candidates by split pair: '+json.dumps(data['cross_split_candidates_by_split_pair'])+'.',
        'Counts are unordered image pairs, not excess files. One duplicate group can contribute multiple '
        'within-split and cross-split pairs. Near tiers include SHA-equal pairs; total review candidates are deduplicated.',
        '', '## Human review and limitations','',
        'The review index contains at most 24 pairs, ordered by exact content duplication, identical '
        'perceptual hash, then lowest distance and deterministic filenames. Four pairs per sheet, '
        'both raw primary images side by side with aspect ratio preserved. All statuses start pending. '
        'See ../leakage_review/index.csv; full near-candidate inventory is cross_split_near_duplicates.csv.',
        f"MPO compatibility: {summary['opencv_check']}. The {len(mpo)} affected images are not excluded or modified.",
        'When available, OpenCV default imread is tested against manifest width/height; EXIF auto-orientation '
        'may cause swapped dimensions, so mismatch is a diagnostic rather than proof of unreadability. '
        'A skipped check does not certify future reader compatibility.',
        'See ../baseline_data_policy.md for the provisional warning-only MPO and rounding policy. '
        'Human review is needed before deciding split contamination or any deduplication policy. '
        'No approved final split/training dataset exists.']
    (output/'leakage_report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
    return data
