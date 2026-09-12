"""Lightweight read-only checks of GYU-DET's documented evidence package."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from data.validators.gyu_m1_documentation import MD5, REQUIRED, validate_provenance
from data.validators.gyu_baseline_split import hash_file
from data.validators.gyu_orphan_review import read_csv


class M1DocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.provenance = json.loads((ROOT/'data/manifests/gyu_det_v3_source_provenance.json').read_text(encoding='utf-8'))

    def test_provenance_required_fields(self) -> None:
        self.assertTrue(set(REQUIRED) <= self.provenance.keys())
        validate_provenance(self.provenance)
        bad=copy.deepcopy(self.provenance); del bad['dataset_doi']
        with self.assertRaisesRegex(ValueError,'Missing'):
            validate_provenance(bad)

    def test_source_md5_values(self) -> None:
        self.assertEqual(self.provenance['source_archive_md5'], MD5)
        source = json.loads((ROOT/'outputs/validation/gyu_det_v3/m1_evidence/source_verification.json').read_text())
        self.assertEqual(source['selected_version'],'V3')
        self.assertEqual(source['official_v3_md5'],MD5)
        bad=copy.deepcopy(self.provenance); bad['source_archive_md5']['train.zip']='0'*32
        with self.assertRaisesRegex(ValueError,'MD5'):
            validate_provenance(bad)

    def test_dataset_article_license_distinction(self) -> None:
        self.assertEqual(self.provenance['dataset_license'],'CC BY-NC-SA 4.0')
        self.assertEqual(self.provenance['paper_license'],'CC BY-NC-ND 4.0')
        bad=copy.deepcopy(self.provenance); bad['dataset_license']=bad['paper_license']
        with self.assertRaisesRegex(ValueError,'license'):
            validate_provenance(bad)

    def test_registry_completeness(self) -> None:
        text=(ROOT/'docs/data/DATASET_REGISTRY.md').read_text(encoding='utf-8')
        datasets=['GYU-DET','CODEBRIM','SDNET2018','DeepCrack','2D Structural Damage Dataset','LOL-v2','ExDark',
            'VisDrone','EuRoC MAV','TUM RGB-D','Hilti SLAM 2022','Hilti SLAM 2023','Hilti x Trimble SLAM 2026',
            'TU Delft ODA','FLIR ADAS','AegisInspect Gazebo-generated dataset']
        for name in datasets: self.assertIn('| '+name+' |',text)
        self.assertIn('| GYU-DET | USE |',text)
        for field in ['Official source','Current availability','Source version','Dataset license',
                      'Commercial/non-commercial restriction','Approximate compressed size','Modalities','Classes',
                      'Annotation format','AegisInspect workstream','Allowed role','Limitations','Decision']:
            self.assertIn('| '+field+' |',text)
        # The authoritative sweep replaces the former pending-only rows.
        # Retain all approved GYU checks above and require evidence for each
        # newly researched entry rather than freezing obsolete placeholders.
        registry=json.loads((ROOT/'data/manifests/dataset_registry.json').read_text(encoding='utf-8'))
        by_name={r['dataset_name']:r for r in registry['datasets']}
        self.assertEqual(set(by_name),set(datasets))
        for name in datasets[1:]:
            row=by_name[name]
            self.assertTrue(row['verification_sources'])
            self.assertTrue(row['verification_status'])
            self.assertIn('| '+name+' | '+row['decision']+' | '+row['verification_status']+' |',text)
            self.assertNotIn('| '+name+' | PENDING_VERIFICATION | PENDING_VERIFICATION |',text)

    def test_evidence_index_paths_exist(self) -> None:
        rows=read_csv(ROOT/'outputs/validation/gyu_det_v3/M1_EVIDENCE_INDEX.csv')
        self.assertGreater(len(rows),40)
        markdown=(ROOT/'outputs/validation/gyu_det_v3/M1_EVIDENCE_INDEX.md').read_text(encoding='utf-8')
        for row in rows:
            self.assertTrue((ROOT/row['repository_relative_path']).exists(),row['repository_relative_path'])
            self.assertIn('`'+row['repository_relative_path']+'`',markdown)

    def test_handoff_counts_match_manifests(self) -> None:
        text=(ROOT/'docs/data/GYU_DET_M1_HANDOFF.md').read_text(encoding='utf-8')
        rows=[]
        for split in ('train','valid','test'):
            group=read_csv(ROOT/f'data/manifests/gyu_det_v3_baseline_v1/{split}.csv')
            self.assertIn(f'| {split.title()} | {len(group):,} |',text)
            rows.extend(group)
        self.assertIn(f'| Total | {len(rows):,} |',text)
        self.assertIn(f'**Annotation instances: {sum(int(r["annotation_count"]) for r in rows):,}.**',text)

    def test_handoff_class_mapping_matches_yaml(self) -> None:
        config=json.loads((ROOT/'configs/data/gyu_det_v3_baseline_v1.yaml').read_text())
        text=(ROOT/'docs/data/GYU_DET_M1_HANDOFF.md').read_text(encoding='utf-8')
        for cid,name in config['names'].items():
            self.assertIn(f'| {cid} | {self.provenance["source_classes"][cid]} | {name} |',text)

    def test_version_manifest_hashes(self) -> None:
        version=json.loads((ROOT/'data/manifests/gyu_det_v3_baseline_v1/VERSION.json').read_text())
        for split,sha in version['manifest_sha256'].items():
            self.assertEqual(sha,hash_file(ROOT/f'data/manifests/gyu_det_v3_baseline_v1/{split}.csv'))
            self.assertEqual(sha,self.provenance[f'baseline_{split}_manifest_sha256'])
        self.assertEqual(version['source_manifest_sha256'],self.provenance['source_manifest_sha256'])

    def test_raw_data_modified_false(self) -> None:
        self.assertIs(self.provenance['raw_data_modified'],False)
        bad=copy.deepcopy(self.provenance); bad['raw_data_modified']='false'
        with self.assertRaisesRegex(ValueError,'raw_data_modified'):
            validate_provenance(bad)


if __name__=='__main__': unittest.main()
