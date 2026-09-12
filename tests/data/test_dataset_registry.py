"""Offline checks for the sourced registry and its approved-data boundary."""
from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'outputs/validation/dataset_registry'
IDS = {'gyu_det_v3','codebrim','sdnet2018','deepcrack','structural_damage_2d',
       'lol_v2','exdark','visdrone','euroc_mav','tum_rgbd','hilti_slam_2022',
       'hilti_slam_2023','hilti_trimble_slam_2026','tu_delft_oda','flir_adas',
       'aegisinspect_gazebo_dataset'}


class DatasetRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = json.loads((ROOT/'data/manifests/dataset_registry.json').read_text(encoding='utf-8'))['datasets']
        cls.by_id = {r['dataset_id']:r for r in cls.rows}
        cls.snapshot = json.loads((EVIDENCE/'preservation_snapshot.json').read_text(encoding='utf-8'))

    def test_all_sixteen_entries_unique(self) -> None:
        self.assertEqual(len(self.rows),16)
        self.assertEqual(len(self.by_id),16)
        self.assertEqual(set(self.by_id),IDS)

    def test_decisions_and_types(self) -> None:
        decisions={'USE_NOW':'NOW','DEFER_TO_WORKSTREAM':'LATER','OPTIONAL':'NOT_REQUIRED',
                   'HOLD':'DO_NOT_ACQUIRE_YET','REJECT':'NOT_REQUIRED'}
        for r in self.rows:
            self.assertIn(r['decision'],decisions)
            self.assertEqual(r['acquisition_timing'],decisions[r['decision']])
            self.assertIs(type(r['m1_required']),bool)
            self.assertTrue(r['intended_role'])
            self.assertTrue(r['owning_workstream'])

    def test_authoritative_sources_required(self) -> None:
        for r in self.rows:
            self.assertTrue(r['verification_sources'],r['dataset_id'])
            if r['dataset_id']=='aegisinspect_gazebo_dataset':
                self.assertIn('INTERNAL_PLANNED',r['verification_status'])
                self.assertTrue((ROOT/r['official_source_url']).is_file())
            else:
                self.assertTrue(r['official_source_url'].startswith('https://'))
            self.assertFalse(any('kaggle.com' in u for u in r['verification_sources']))

    def test_unresolved_licenses_block_external_acquisition(self) -> None:
        expected={'structural_damage_2d','lol_v2','visdrone','flir_adas','aegisinspect_gazebo_dataset'}
        self.assertEqual({r['dataset_id'] for r in self.rows if r['license_identifier']=='LICENSE_UNRESOLVED'},expected)
        for key in expected:
            r=self.by_id[key]
            self.assertIsNone(r['license_url'])
            self.assertIn('UNRESOLVED',r['verification_status'])
            self.assertIn('LICENSE STATUS: UNRESOLVED',(ROOT/r['license_doc']).read_text(encoding='utf-8'))
            if key!='aegisinspect_gazebo_dataset': self.assertEqual(r['decision'],'HOLD')

    def test_gyu_approved_entry_and_artifacts_unchanged(self) -> None:
        raw=(ROOT/'docs/data/DATASET_REGISTRY.md').read_bytes()
        approved=raw[raw.index(b'## GYU-DET'):]
        self.assertEqual(hashlib.sha256(approved).hexdigest(),self.snapshot['gyu_registry_section_sha256'])
        for path,expected in self.snapshot['protected'].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),expected,path)
        self.assertEqual(self.by_id['gyu_det_v3']['verification_status'],'APPROVED_UNCHANGED')
        self.assertEqual(self.by_id['gyu_det_v3']['approved_registry_decision'],'USE')

    def test_codebrim_isolation(self) -> None:
        r=self.by_id['codebrim']
        self.assertIs(r['external_holdout'],True)
        self.assertEqual(r['decision'],'DEFER_TO_WORKSTREAM')
        text=(ROOT/'docs/data/CODEBRIM_EXTERNAL_HOLDOUT_POLICY.md').read_text(encoding='utf-8')
        for requirement in ['must not be included in GYU-DET baseline training','tune baseline hyperparameters',
                            'baseline is frozen','future fine-tuning experiment','initial external-generalization result']:
            self.assertIn(requirement,text)

    def test_acquisition_plan_covers_every_entry_and_no_new_download(self) -> None:
        with (EVIDENCE/'m1_acquisition_decisions.csv').open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual({r['dataset_id'] for r in rows},IDS)
        self.assertEqual(len(rows),16)
        text=(ROOT/'docs/data/M1_DATASET_ACQUISITION_PLAN.md').read_text(encoding='utf-8')
        for r in rows:
            self.assertIn('| '+r['dataset_name']+' |',text)
            self.assertEqual(r['download_now'],'false')
            self.assertEqual(r['required_before_chat03'],'true' if r['dataset_id']=='gyu_det_v3' else 'false')

    def test_json_and_csv_agree_all_fields(self) -> None:
        with (ROOT/'data/manifests/dataset_registry.csv').open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),len(self.rows))
        for c,j in zip(rows,self.rows):
            self.assertEqual(set(c),set(j))
            for key,value in j.items():
                expected=json.dumps(value,ensure_ascii=False,sort_keys=True) if isinstance(value,(list,dict,bool)) or value is None else str(value)
                self.assertEqual(c[key],expected,(j['dataset_id'],key))

    def test_source_and_license_docs_exist(self) -> None:
        for r in self.rows:
            for field in ['source_doc','license_doc']:
                self.assertTrue((ROOT/r[field]).is_file(),r[field])
            if r['dataset_id']!='gyu_det_v3':
                text=(ROOT/r['source_doc']).read_text(encoding='utf-8')
                self.assertIn('AUTHORITATIVE SOURCE FACTS',text)
                self.assertIn('AEGISINSPECT ROLE / DECISION',text)

    def test_field_level_evidence(self) -> None:
        facts=['official_source','version','doi','modalities','annotation_type','classes_or_content',
               'license_identifier','commercial_restriction','redistribution_notes','approximate_size','availability']
        with (EVIDENCE/'source_evidence.csv').open(encoding='utf-8',newline='') as f:
            evidence=list(csv.DictReader(f))
        for r in self.rows:
            for key in facts:
                self.assertTrue(r['field_sources'][key])
                self.assertTrue(any(e['dataset_id']==r['dataset_id'] and e['field']==key for e in evidence))

    def test_no_false_acquisition_claim(self) -> None:
        acquired=[r for r in self.rows if r['acquisition_status']=='ACQUIRED_AND_APPROVED']
        self.assertEqual([r['dataset_id'] for r in acquired],['gyu_det_v3'])
        self.assertTrue((ROOT/'data/manifests/gyu_det_v3_source_provenance.json').is_file())
        self.assertTrue((ROOT/'data/raw/gyu_det/v3/extracted').is_dir())
        for r in self.rows[1:]:
            self.assertIn(r['acquisition_status'],{'NOT_ACQUIRED_IN_THIS_SWEEP','PLANNED_INTERNAL'})

    def test_no_raw_inventory_modifications(self) -> None:
        current={str(p.relative_to(ROOT)):[p.stat().st_size,p.stat().st_mtime_ns]
                 for p in (ROOT/'data/raw').rglob('*') if p.is_file()}
        self.assertEqual(current,self.snapshot['raw'])

    def test_2026_hilti_role_is_not_lidar_input(self) -> None:
        r=self.by_id['hilti_trimble_slam_2026']
        self.assertNotIn('LiDAR',r['modalities'])
        self.assertIn('NOT included',r['limitations'])

    def test_gazebo_requires_asset_licenses_and_later_generation(self) -> None:
        r=self.by_id['aegisinspect_gazebo_dataset']
        self.assertIs(r['required_later'],True)
        text=(ROOT/'docs/data/M1_DATA_FOUNDATION_SCOPE_DECISION.md').read_text(encoding='utf-8')
        self.assertIn('asset-license manifest',text)
        self.assertIn('world/model/mesh/texture/plugin/import',text)


if __name__=='__main__': unittest.main()
