"""Synthetic tests for exact grouping, perceptual matching and deterministic audit outputs."""
from __future__ import annotations
import hashlib
import random
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageEnhance

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from data.validators.gyu_leakage import (HammingIndex,basename_groups,difference_hash,exact_groups,
    near_pairs,numeric_neighbors,pair_row,run_audit,split_pair)
from data.validators.gyu_full_validation import csv_output


def noise(seed: int) -> Image.Image:
    rng=random.Random(seed)
    image=Image.new('RGB',(96,64))
    image.putdata([(rng.randrange(30,190),)*3 for _ in range(96*64)])
    return image


class LeakageTests(unittest.TestCase):
    def test_identical_file_hash_detection(self) -> None:
        self.assertEqual(exact_groups([{'image_sha256':'a'},{'image_sha256':'b'},{'image_sha256':'a'}]),[[0,2]])

    def test_within_split_duplicate(self) -> None:
        rows=[{'image_sha256':'a','split':'train'},{'image_sha256':'a','split':'train'}]
        self.assertEqual(exact_groups(rows),[[0,1]])
        self.assertEqual(split_pair(rows[0]['split'],rows[1]['split']),'train/train')

    def test_cross_split_exact_duplicate(self) -> None:
        rows=[{'image_sha256':'a','split':'train'},{'image_sha256':'a','split':'test'}]
        self.assertEqual(exact_groups(rows),[[0,1]])
        self.assertEqual(split_pair('test','train'),'train/test')

    def test_basename_collision_without_identical_content(self) -> None:
        rows=[{'image_filename':' AbC .JPG','image_sha256':'a'}, {'image_filename':'abc.png','image_sha256':'b'}]
        self.assertEqual(basename_groups(rows),[[0,1]])
        self.assertEqual(exact_groups(rows),[])

    def test_identical_perceptual_hash(self) -> None:
        image=noise(1)
        self.assertEqual(difference_hash(image),difference_hash(image.copy()))
        h=difference_hash(image)
        self.assertEqual(near_pairs([{'split':'train','perceptual_hash':h},{'split':'valid','perceptual_hash':h}]),[(0,1,0)])

    def test_similar_image_candidate(self) -> None:
        image=noise(2)
        ha=difference_hash(image)
        hb=difference_hash(ImageEnhance.Brightness(image).enhance(1.05))
        self.assertLessEqual((int(ha,16)^int(hb,16)).bit_count(),12)
        self.assertEqual(len(near_pairs([{'split':'train','perceptual_hash':ha},{'split':'test','perceptual_hash':hb}])),1)

    def test_unrelated_images(self) -> None:
        ha,hb=difference_hash(noise(3)),difference_hash(noise(9))
        self.assertGreater((int(ha,16)^int(hb,16)).bit_count(),12)
        self.assertEqual(near_pairs([{'split':'train','perceptual_hash':ha},{'split':'valid','perceptual_hash':hb}]),[])

    def test_split_pair_classification(self) -> None:
        self.assertEqual(split_pair('test','valid'),'valid/test')
        self.assertEqual(split_pair('valid','train'),'train/valid')

    def test_metric_index_matches_exhaustive_search(self) -> None:
        rng=random.Random(17)
        values=[rng.getrandbits(128) for _ in range(40)]
        values += [values[0],values[0]^31,values[1]^4095]
        index=HammingIndex()
        for i,v in enumerate(values): index.add(v,i)
        for v in values:
            self.assertEqual(index.query(v,12),[(i,(v^w).bit_count()) for i,w in enumerate(values) if (v^w).bit_count()<=12])

    def test_numeric_proximity_is_separate(self) -> None:
        rows=[{'split':'train','image_filename':'100.JPG'},{'split':'valid','image_filename':'102.JPG'},
              {'split':'test','image_filename':'106.JPG'}]
        self.assertEqual(numeric_neighbors(rows),[(0,1)])

    def test_deterministic_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp); raw=repo/'data/raw'; raw.mkdir(parents=True)
            manifest=[]
            for n,(split,im) in enumerate([('train',noise(10)),('valid',noise(10)),('test',noise(44))]):
                path=raw/f'{n}.png'; im.save(path)
                manifest.append(dict(split=split,image_filename=path.name,image_relative_path=path.relative_to(repo).as_posix(),
                    image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),width='96',height='64',
                    file_size_bytes=str(path.stat().st_size),pairing_status='exact_pair',exif_orientation=''))
            mp=repo/'manifest.csv'; csv_output(mp,manifest,list(manifest[0]))
            validation=repo/'outputs/full_validation'; validation.mkdir(parents=True)
            csv_output(validation/'image_validation.csv',[],['primary_decode_success','decode_success'])
            orphan=repo/'outputs/orphan_review'; orphan.mkdir()
            for name in ('human_triage_decisions.csv','index.csv','final_triage_summary.csv'):
                (orphan/name).write_text('header\n')
            before={p.name:p.read_bytes() for p in raw.iterdir()}
            a=run_audit(repo,mp,validation,repo/'outputs/a',repo/'outputs/review_a',1,lambda _:None)
            b=run_audit(repo,mp,validation,repo/'outputs/b',repo/'outputs/review_b',1,lambda _:None)
            self.assertEqual(a,b)
            self.assertEqual(a['summary']['cross_split_exact_duplicate_pairs'],1)
            self.assertEqual(a['summary']['review_pairs_shown'],1)
            for x,y in [('a','b'),('review_a','review_b')]:
                self.assertEqual({p.name:p.read_bytes() for p in (repo/'outputs'/x).iterdir()},
                                 {p.name:p.read_bytes() for p in (repo/'outputs'/y).iterdir()})
            self.assertEqual(before,{p.name:p.read_bytes() for p in raw.iterdir()})


if __name__=='__main__': unittest.main()
