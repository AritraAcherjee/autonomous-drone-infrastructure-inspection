"""Integrity, annotation diagnostics, and manifest regression tests."""

from __future__ import annotations

import csv
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from data.validators.gyu_full_validation import validate_image, validate_label, validate_dataset
from data.validators.gyu_pairing import audit, write_outputs, SPLITS


class FullValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base=Path(temp.name)

    def label(self,text: str) -> dict:
        path=self.base/'label.txt'
        path.write_text(text,encoding='utf-8')
        return validate_label(path,['Crack','Breakage'])

    def codes(self,result: dict) -> set[str]:
        return {i['issue_code'] for i in result['issues']}

    def test_valid_image(self) -> None:
        path=self.base/'valid.JPG'
        Image.new('RGB',(32,24),'red').save(path)
        result=validate_image(path)
        self.assertTrue(result['decode_success'])
        self.assertEqual((result['width'],result['height'],result['channels'],result['image_mode']),(32,24,3,'RGB'))
        self.assertEqual(result['image_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())

    def test_corrupted_image(self) -> None:
        path=self.base/'bad.jpg'; path.write_bytes(b'not a jpeg')
        self.assertIn('unreadable_or_corrupted_image',self.codes(validate_image(path)))

    def test_valid_png_after_exif_access(self) -> None:
        path=self.base/'valid.png'
        exif=Image.Exif(); exif[274]=1
        Image.new('RGBA',(40,25),(255,0,0,128)).save(path,exif=exif)
        result=validate_image(path)
        self.assertTrue(result['decode_success'])
        self.assertEqual(result['channels'],4)
        self.assertEqual(result['validation_status'],'valid')

    def test_truncated_image(self) -> None:
        path=self.base/'truncated.jpg'
        Image.new('RGB',(80,60),'blue').save(path)
        path.write_bytes(path.read_bytes()[:-50])
        self.assertFalse(validate_image(path)['decode_success'])

    def test_zero_byte_image(self) -> None:
        path=self.base/'empty.png'; path.touch()
        result=validate_image(path)
        self.assertIn('zero_byte_image',self.codes(result))
        self.assertFalse(result['decode_success'])

    def test_missing_image(self) -> None:
        result=validate_image(self.base/'missing.JPG')
        self.assertFalse(result['exists'])
        self.assertFalse(result['decode_success'])

    def test_mpo_primary_and_broken_auxiliary_frame(self) -> None:
        path=self.base/'multi.JPG'
        Image.new('RGB',(40,30),'red').save(path,format='MPO',save_all=True,
                                          append_images=[Image.new('RGB',(40,30),'blue')])
        good=validate_image(path)
        self.assertTrue(good['decode_success'])
        raw=path.read_bytes()
        offset=raw.find(b'\xff\xd8\xff',3)
        self.assertGreater(offset,0)
        path.write_bytes(raw[:offset]+b'\x00\x00'+raw[offset+2:])
        result=validate_image(path)
        self.assertTrue(result['primary_decode_success'])
        self.assertFalse(result['decode_success'])
        self.assertIn('auxiliary_frame_decode_failure',self.codes(result))
        self.assertNotIn('extension_format_mismatch',self.codes(result))

    def test_extension_and_exif(self) -> None:
        path=self.base/'wrong.png'
        exif=Image.Exif(); exif[274]=6
        Image.new('RGB',(20,30)).save(path,format='JPEG',exif=exif)
        result=validate_image(path)
        self.assertEqual(result['exif_orientation'],6)
        self.assertEqual((result['width'],result['height']),(20,30))
        self.assertIn('extension_format_mismatch',self.codes(result))

    def test_valid_yolo_row(self) -> None:
        result=self.label('\n0 .5 .5 .2 .4\n')
        self.assertEqual(result['validation_status'],'valid')
        self.assertEqual(result['annotation_count'],1)
        self.assertEqual(result['rows'][0]['corners'],(.4,.3,.6,.7))

    def test_malformed_field_count(self) -> None:
        self.assertIn('malformed_field_count',self.codes(self.label('0 .5 .5 .2')))

    def test_nonnumeric_value(self) -> None:
        self.assertIn('nonnumeric_value',self.codes(self.label('0 x .5 .2 .2')))

    def test_nonfinite_value(self) -> None:
        for value in ('nan','inf','-inf'):
            with self.subTest(value=value):
                self.assertIn('nonfinite_value',self.codes(self.label(f'0 {value} .5 .2 .2')))

    def test_invalid_class_id(self) -> None:
        for value in ('-1','2','1.0','cat'):
            with self.subTest(value=value):
                self.assertIn('invalid_class_id',self.codes(self.label(f'{value} .5 .5 .2 .2')))

    def test_coordinate_outside_range(self) -> None:
        self.assertIn('normalized_value_out_of_range',self.codes(self.label('0 1.2 .5 .2 .2')))

    def test_zero_width_and_height_and_negative(self) -> None:
        for dims in ('0 .2','.2 0','-.2 .2'):
            with self.subTest(dims=dims):
                self.assertIn('zero_or_negative_box',self.codes(self.label('0 .5 .5 '+dims)))

    def test_derived_corner_outside_frame(self) -> None:
        result=self.label('0 .95 .5 .2 .2')
        self.assertIn('derived_box_outside_frame',self.codes(result))
        self.assertNotIn('normalized_value_out_of_range',self.codes(result))
        self.assertFalse(result['rows'][0]['valid'])

    def test_rounding_overshoot_is_visible_warning(self) -> None:
        result=self.label('0 .9000001 .5 .2 .2')
        self.assertIn('derived_box_outside_frame',self.codes(result))
        self.assertEqual(result['validation_status'],'warning')

    def test_duplicate_rows(self) -> None:
        result=self.label('0 .5 .5 .2 .2\n0   .5 .5 .2 .2')
        self.assertEqual(result['annotation_count'],2)
        self.assertEqual(sum(i['issue_code']=='duplicate_annotation_row' for i in result['issues']),1)

    def test_empty_label(self) -> None:
        result=self.label(' \n\t')
        self.assertTrue(result['empty'])
        self.assertIn('empty_label_file',self.codes(result))

    def test_invalid_utf8(self) -> None:
        path=self.base/'invalid.txt'; path.write_bytes(b'\xff')
        self.assertIn('unreadable_label',self.codes(validate_label(path,['Crack'])))

    def test_manifest_exact_unlabeled_and_orphan(self) -> None:
        root=self.base/'data/raw/extracted'
        for split in SPLITS:
            for kind in ('images','labels'): (root/split/split/kind).mkdir(parents=True)
        Image.new('RGB',(300,300)).save(root/'train/train/images/5774.JPG')
        Image.new('RGB',(300,300)).save(root/'train/train/images/unlabeled.JPG')
        (root/'train/train/labels/5774.txt').write_text('0 .5 .5 .2 .2')
        (root/'valid/valid/labels/orphan.txt').write_text('1 .5 .5 .2 .2')
        audit_dir=self.base/'outputs/audit'
        write_outputs(audit(root),audit_dir)
        review=audit_dir/'orphan_review'; review.mkdir()
        (review/'human_triage_decisions.csv').write_text('label_split,label_filename,review_status,repair_authorized\nvalid,orphan.txt,unresolved_hold,false\n')
        (review/'index.csv').write_text('review_status,candidate_image_split,candidate_image_filename,label_split,label_filename,reviewer_selected_candidate\n')
        classes=self.base/'classes.txt'; classes.write_text('Crack\nBreakage\n')
        before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
        manifest=self.base/'data/manifests/manifest.csv'
        result=validate_dataset(root,audit_dir,classes,self.base/'outputs/full',manifest,self.base,1,lambda _:None)
        with manifest.open() as handle: rows=list(csv.DictReader(handle))
        self.assertEqual(len(rows),2)
        exact=next(r for r in rows if r['pairing_status']=='exact_pair')
        missing=next(r for r in rows if r['pairing_status']=='image_without_label')
        self.assertEqual(exact['label_filename'],'5774.txt')
        self.assertEqual(exact['annotation_count'],'1')
        self.assertEqual(missing['label_relative_path'],'')
        self.assertEqual(missing['annotation_count'],'')
        self.assertEqual(missing['repair_authorized'],'False')
        self.assertEqual(result['summary']['orphan_labels'],1)
        stats=result['class_statistics']
        orphan=next(r for r in stats if r['split']=='valid' and r['raw_class_id']==1)
        self.assertEqual(orphan['annotation_instances'],1)
        self.assertEqual(orphan['images_containing_class'],0)
        self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})


if __name__=='__main__': unittest.main()
