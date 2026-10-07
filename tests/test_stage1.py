import copy
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from backend.database import Database
from backend.service import Service, Invalid, Missing, Conflict
from backend.analysis import apply_rules, RULES
from backend.server import Application, Server, Handler
from adapters.storage.local import LocalSourceStorage
from adapters.inbody.documents import extract, parse_text
from adapters.ai.providers import OpenAICompatibleProvider

class EvidenceAI:
    model='synthetic-selector'
    def synthesize(self,evidence):
        return {'provider':'test','model':self.model,'clinician':[s for k,s in evidence['sentences'].items() if k.startswith('c')],
                'patient':[s for k,s in evidence['sentences'].items() if k.startswith('p')]}

class Stage1(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        self.db=Database('sqlite:///'+str(self.path/'tests.db'))
        self.s=Service(self.db,LocalSourceStorage(self.path/'sources'))
        for pid in ('SYN-1','SYN-2'):
            self.s.add_patient({'id':pid,'name':pid,'dob':'1980-01-01','sex':'male','synthetic':True},'test')
            self.s.add_encounter(pid,{'id':pid+'-E','label':'Test'},'test')
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def payload(self,sid='one',stamp='2026-10-07T10:00:00-04:00',pid='SYN-1'):
        return {'patient_id':pid,'encounter_id':pid+'-E','test_timestamp':stamp,'source_identifier':sid,
                'device_model':'Synthetic fixture','measurements':[{'metric':'weight','value':80,'unit':'kg'},
                    {'metric':'bmi','value':27,'unit':'kg/m2'}, {'metric':'percent_body_fat','value':24,'unit':'%'}]}
    def result(self,**kw): return self.s.import_result('SYN-1',self.payload(**kw),'test','mock_api')
    def test_valid_api_result(self):
        r=self.result();self.assertEqual(r['measurements'][0]['value'],80);self.assertTrue(r['analyses'][0]['data_quality_passed'])
    def pdf(self):
        import fitz
        doc=fitz.open();page=doc.new_page();page.insert_text((60,80),'Patient ID: SYN-1\nWeight: 80 kg\nBMI: 27 kg/m2');return doc.tobytes()
    def image(self):
        from PIL import Image,ImageDraw,ImageFont
        img=Image.new('RGB',(1200,300),'white');draw=ImageDraw.Draw(img)
        font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',42)
        draw.text((30,20),'Patient ID: SYN-1\nWeight: 80 kg\nBMI: 27 kg/m2',fill='black',font=font,spacing=18)
        out=io.BytesIO();img.save(out,format='PNG');return out.getvalue()
    def test_valid_pdf_import(self):
        r=self.s.import_result('SYN-1',self.payload(),'test','pdf',[(self.pdf(),'pdf')]);self.assertEqual(r['measurements'][0]['value'],80);self.assertFalse(r['analyses'][0]['data_quality_passed'])
    def test_valid_screenshot_import(self):
        r=self.s.import_result('SYN-1',self.payload(),'test','image',[(self.image(),'image')]);self.assertEqual(r['measurements'][0]['value'],80)
    def test_missing_measurement(self):
        p=self.payload();p['measurements']=[p['measurements'][0]];r=self.s.import_result('SYN-1',p,'test');self.assertEqual(len(r['measurements']),1)
    def test_unreadable_field(self):
        parsed=parse_text('Weight: ??? kg\nBMI: 27 kg/m2');self.assertIsNone(parsed['measurements'][0]['value'])
    def test_duplicate_webhook(self):
        app=Application(self.s);p=self.payload();p['contract']='synthetic-normalized-v1'
        first=app.route('POST','/inbody/webhook',p,None,'webhook')[1];second=app.route('POST','/inbody/webhook',p,None,'webhook')[1]
        self.assertEqual(first['id'],second['id']);self.assertTrue(second['duplicate']);self.assertEqual(len(self.s.history('SYN-1')),1)
    def test_duplicate_conflicting_content(self):
        self.result();p=self.payload();p['measurements'][0]['value']=99
        with self.assertRaises(Conflict):self.s.import_result('SYN-1',p,'test','mock_api')
    def test_wrong_patient_encounter(self):
        p=self.payload();p['encounter_id']='SYN-2-E'
        with self.assertRaises(Invalid):self.s.import_result('SYN-1',p,'test')
    def test_missing_patient(self):
        with self.assertRaises(Missing):self.s.import_result('absent',self.payload(),'test')
    def test_source_patient_mismatch(self):
        import fitz
        doc=fitz.open();page=doc.new_page();page.insert_text((60,80),'Patient ID: SYN-2\nWeight: 80 kg')
        with self.assertRaises(Invalid):self.s.import_result('SYN-1',self.payload(),'test','pdf',[(doc.tobytes(),'pdf')])
    def test_repeat_study_longitudinal(self):
        first=self.result(sid='prior',stamp='2026-09-07T10:00:00-04:00');p=self.payload();p['measurements'][0]['value']=82
        r=self.s.import_result('SYN-1',p,'test');c=r['analyses'][0]['longitudinal_comparison']
        self.assertEqual(c['interval_days'],30);self.assertEqual(c['changes'][0]['absolute_change'],2);self.assertEqual(c['previous_result_id'],first['id'])
    def test_no_prior(self):self.assertIsNone(self.result()['analyses'][0]['longitudinal_comparison']['previous_result_id'])
    def test_out_of_order_previous_is_time_based(self):
        self.result(sid='later',stamp='2026-11-07T10:00:00-04:00');r=self.result(sid='earlier');self.assertIsNone(r['analyses'][0]['longitudinal_comparison']['previous_result_id'])
    def test_abnormal_rule(self):
        flags=self.result()['analyses'][0]['rule_findings'];self.assertEqual(flags[0]['source'],'CDC Adult BMI Categories');self.assertNotIn('urgent',flags[0]['severity'])
    def test_age_restriction(self):
        flags=apply_rules([{'metric':'bmi','unit':'kg/m2','value':27,'status':'verified'}],{'dob':'2015-01-01'},'2026-10-07T00:00:00+00:00');self.assertEqual(flags,[])
    def test_conflicting_findings(self):
        p=self.payload();p['measurements'][1]['device_reference']={'low':20,'high':28,'source':'Synthetic report only','version':'fixture-v1'}
        r=self.s.import_result('SYN-1',p,'test');self.assertIn('conflicting references',[f['flag_type'] for f in r['analyses'][0]['rule_findings']])
    def test_ai_unavailable(self):
        class Broken:
            def synthesize(self,_):raise ConnectionError()
        self.s.provider=Broken();r=self.result();self.assertEqual(r['analyses'][0]['provenance']['ai']['status'],'unavailable-or-invalid')
    def test_ai_malformed(self):
        class Bad:
            def synthesize(self,_):return {'diagnosis':'bad'}
        self.s.provider=Bad();r=self.result();self.assertEqual(r['analyses'][0]['provenance']['ai']['status'],'unavailable-or-invalid')
    def test_ai_cannot_invent_values(self):
        class Bad:
            def synthesize(self,_):return {'provider':'bad','model':'x','patient':['Weight is 1 kg'],'clinician':[]}
        self.s.provider=Bad();r=self.result();self.assertFalse(r['analyses'][0]['provenance']['ai']['used']);self.assertEqual(r['measurements'][0]['value'],80)
    def test_ai_paid_provider_contract(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,_):return json.dumps({'model':'paid-test','choices':[{'message':{'content':json.dumps({'clinician_sentence_ids':['c0'],'patient_sentence_ids':['p0']})}}]}).encode()
        with patch('urllib.request.urlopen',return_value=Response()):
            output=OpenAICompatibleProvider('https://example.test/v1','test','paid-test').synthesize({'sentences':{'c0':'Review','p0':'Your test'}})
        self.assertEqual(output['patient'],['Your test'])
    def test_clinician_review(self):
        r=self.result();a=r['analyses'][0];r=self.s.review('SYN-1',r['id'],{'analysis_id':a['id'],'status':'accepted','identity_confirmed':True},'clinician');self.assertEqual(r['analyses'][0]['review_status'],'accepted')
    def test_stale_review_rejected(self):
        r=self.result();a=r['analyses'][0];self.s.analyze('SYN-1',r['id'],'test')
        with self.assertRaises(Conflict):self.s.review('SYN-1',r['id'],{'analysis_id':a['id'],'status':'accepted','identity_confirmed':True},'clinician')
    def test_unverified_review_blocked(self):
        p=self.payload();p['measurements'][0]['status']='unverified';r=self.s.import_result('SYN-1',p,'test')
        with self.assertRaises(Invalid):self.s.review('SYN-1',r['id'],{'analysis_id':r['analyses'][0]['id'],'status':'accepted','identity_confirmed':True},'clinician')
    def test_provenance_preservation(self):
        r=self.result();data=self.s.storage.get(r['source_result']['payload_sha256']);self.assertEqual(json.loads(data)['test_timestamp'],self.payload()['test_timestamp']);self.assertEqual(r['analyses'][0]['provenance']['source_hash'],r['provenance']['source_hash'])
    def test_timestamp_preservation(self):
        r=self.result();self.assertEqual(r['test_timestamp'],'2026-10-07T10:00:00-04:00');self.assertNotEqual(r['test_timestamp'],r['ingested_at'])
    def test_timezone_required(self):
        with self.assertRaises(Invalid):self.result(stamp='2026-10-07T10:00:00')
    def test_correction_versioning(self):
        r=self.result();ms=copy.deepcopy(r['measurements']);ms[0]['value']=81;c=self.s.correct('SYN-1',r['id'],{'measurements':ms,'reason':'Correct source value'},'clinician')
        self.assertEqual(c['supersedes'],r['id']);self.assertEqual(self.s.detail('SYN-1',r['id'])['measurements'][0]['value'],80);self.assertEqual(len(self.s.history('SYN-1')),1);self.assertEqual(len(self.s.history('SYN-1',True)),2)
    def test_append_only_database(self):
        r=self.result()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.transaction():self.db.execute('DELETE FROM results WHERE id=?',(r['id'],))
    def test_restart_recovery(self):
        r=self.result();self.db.close();self.db=Database('sqlite:///'+str(self.path/'tests.db'));s=Service(self.db,self.s.storage);self.assertEqual(s.detail('SYN-1',r['id'])['id'],r['id'])
    def test_no_cross_patient_leakage(self):
        r=self.result();self.assertEqual(self.s.history('SYN-2'),[])
        with self.assertRaises(Missing):self.s.detail('SYN-2',r['id'])
    def test_file_validation(self):
        with self.assertRaises(Invalid):extract(b'not pdf','pdf')
    def test_operator_cannot_review(self):
        app=Application(self.s);r=self.result()
        with self.assertRaises(PermissionError):app.route('POST',f"/patients/SYN-1/inbody/{r['id']}/review",{},None,'operator')
    def test_no_phi_patient(self):
        with self.assertRaises(Invalid):self.s.add_patient({'id':'real','name':'Real','synthetic':False},'test')
    def test_unit_conversion(self):
        p=self.payload();p['measurements'][0].update(value=200,unit='lb');r=self.s.import_result('SYN-1',p,'test');self.assertAlmostEqual(r['measurements'][0]['value'],90.718474)
    def test_unknown_model_metric(self):
        p=self.payload();p['measurements'].append({'metric':'right_arm_lean','value':3.8,'unit':'kg'});r=self.s.import_result('SYN-1',p,'test');self.assertEqual(r['measurements'][-1]['value'],3.8)
    def test_http_end_to_end(self):
        server=Server(('127.0.0.1',0),Handler);server.app=Application(self.s);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            req=urllib.request.Request(url+'/patients/SYN-1/inbody/import',data=json.dumps(self.payload()).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req) as response:r=json.load(response)
            self.assertEqual(r['patient_id'],'SYN-1')
            with urllib.request.urlopen(url+'/patients/SYN-1/inbody/trends') as response:trends=json.load(response)
            self.assertEqual(trends[0]['points'][0]['value'],80)
        finally:server.shutdown();server.server_close();thread.join()
    def test_source_download_scoped(self):
        r=self.s.import_result('SYN-1',self.payload(),'test','pdf',[(self.pdf(),'pdf')])
        digest=r['source_result']['files'][0]['sha256']
        data,media=self.s.source_bytes('SYN-1',r['id'],digest)
        self.assertEqual(media,'application/pdf');self.assertTrue(data.startswith(b'%PDF-'))
        with self.assertRaises(Missing):self.s.source_bytes('SYN-2',r['id'],digest)
        with self.assertRaises(Missing):self.s.source_bytes('SYN-1',r['id'],'f'*64)
    def test_source_tamper_detected(self):
        r=self.result();digest=r['source_result']['payload_sha256']
        (self.path/'sources'/digest).write_bytes(b'altered')
        with self.assertRaises(ValueError):self.s.source_bytes('SYN-1',r['id'],digest)
    def test_review_projection_consistent(self):
        r=self.result();r=self.s.review('SYN-1',r['id'],{'analysis_id':r['analyses'][0]['id'],'status':'accepted','identity_confirmed':True},'clinician')
        a=r['analyses'][0]
        self.assertEqual(a['patient_summary']['review_status'],'accepted')
        self.assertEqual(a['clinician_summary']['review_status'],'accepted')
    def test_auth_tokens_and_webhook_separation(self):
        with patch.dict(os.environ,{'INBODY_CLINICIAN_TOKEN':'c'*32,'INBODY_OPERATOR_TOKEN':'o'*32,'INBODY_WEBHOOK_TOKEN':'w'*32}):
            app=Application(self.s)
            self.assertEqual(app.role('c'*32),'clinician');self.assertEqual(app.role('o'*32),'operator')
            self.assertEqual(app.role('w'*32,True),'webhook')
            with self.assertRaises(PermissionError):app.role('w'*32)
            with self.assertRaises(PermissionError):app.role('')
    def test_percent_change_is_percentage_points(self):
        self.result(sid='previous',stamp='2026-09-07T10:00:00-04:00')
        p=self.payload();p['measurements'][2]['value']=25
        r=self.s.import_result('SYN-1',p,'test')
        change=next(c for c in r['analyses'][0]['longitudinal_comparison']['changes'] if c['metric']=='percent_body_fat')
        self.assertEqual(change['change_unit'],'percentage points');self.assertIsNone(change['percentage_change'])
    def test_physical_validation_blocks_acceptance(self):
        p=self.payload();p['measurements'][2]['value']=200
        r=self.s.import_result('SYN-1',p,'test');self.assertEqual(r['measurements'][2]['status'],'unverified')
        self.assertFalse(r['analyses'][0]['data_quality_passed'])
    def test_conflicting_document_fields(self):
        parsed=parse_text('Weight: 80 kg\nWeight: 90 kg')
        self.assertIsNone(parsed['measurements'][0]['value'])
    def test_http_multipart_import(self):
        server=Server(('127.0.0.1',0),Handler);server.app=Application(self.s)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            boundary='stage1boundary';metadata=self.payload();metadata['source_type']='pdf'
            body=(('--'+boundary+'\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n').encode()+json.dumps(metadata).encode()+
                  ('\r\n--'+boundary+'\r\nContent-Disposition: form-data; name="files"; filename="synthetic.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+self.pdf()+
                  ('\r\n--'+boundary+'--\r\n').encode())
            request=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/patients/SYN-1/inbody/import',data=body,
                headers={'Content-Type':'multipart/form-data; boundary='+boundary})
            with urllib.request.urlopen(request) as response:result=json.load(response)
            self.assertEqual(result['source_type'],'pdf');self.assertEqual(result['measurements'][0]['value'],80)
        finally:server.shutdown();server.server_close();thread.join()

    def test_ten_consecutive_acceptance_flows(self):
        self.s.provider=EvidenceAI();prior=None
        for i in range(10):
            stamp=f'2026-09-{i+1:02d}T09:30:00-04:00';p=self.payload(sid=f'acceptance-{i}',stamp=stamp);p['measurements'][0]['value']=80+i
            r=self.s.import_result('SYN-1',p,'test','mock_api');a=r['analyses'][0]
            self.assertEqual(r['test_timestamp'],stamp);self.assertTrue(a['data_quality_passed']);self.assertTrue(a['provenance']['ai']['used'])
            self.assertEqual(a['longitudinal_comparison']['previous_result_id'],prior);self.assertTrue(a['patient_summary']['sentences']);self.assertTrue(a['clinician_summary']['measured_facts'])
            self.s.review('SYN-1',r['id'],{'analysis_id':a['id'],'status':'accepted','identity_confirmed':True},'clinician')
            self.assertEqual(self.s.detail('SYN-1',r['id'])['analyses'][0]['review_status'],'accepted');prior=r['id']
        self.assertEqual(len(self.s.history('SYN-1')),10)
        self.assertEqual(len(self.db.rows('SELECT * FROM outbox')),10)

if __name__=='__main__':unittest.main()
