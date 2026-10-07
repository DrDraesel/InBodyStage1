import hashlib
import json
import uuid
from datetime import datetime, timezone
from backend.validation import normalize, safe_id, Invalid
from backend.analysis import apply_rules, compare, summaries, VERSION, RULES
from adapters.inbody.documents import extract, PARSER_VERSION
from adapters.ai.providers import configured_provider

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc).isoformat()
def dumps(value): return json.dumps(value,sort_keys=True,allow_nan=False)

class Missing(Invalid): pass
class Conflict(Invalid): pass

class Service:
    def __init__(self, db, storage, provider=None):
        self.db, self.storage = db, storage
        self.provider = provider if provider is not None else configured_provider()

    def audit(self, actor, action, entity):
        self.db.execute('INSERT INTO audit VALUES (?,?,?,?,?)',(uid(),now(),actor,action,entity))

    def patients(self):
        return self.db.rows('SELECT * FROM patients ORDER BY name')

    def add_patient(self, data, actor):
        pid = safe_id(data.get('id'),'patient_id')
        if data.get('synthetic') is not True:
            raise Invalid('Stage 1 accepts synthetic patients only')
        name = data.get('name')
        if not isinstance(name,str) or not 1<=len(name)<=100:
            raise Invalid('Patient name required, maximum 100 characters')
        dob = data.get('dob')
        if dob:
            from datetime import date
            date.fromisoformat(dob)
        sex = data.get('sex')
        if sex not in (None,'female','male','unknown'):
            raise Invalid('Invalid sex')
        with self.db.transaction():
            if self.db.one('SELECT id FROM patients WHERE id=?',(pid,)):
                raise Conflict('Patient already exists')
            self.db.execute('INSERT INTO patients VALUES (?,?,?,?,?)',(pid,name,dob,sex,1))
            self.audit(actor,'patient.created',pid)
        return self.patient(pid)

    def patient(self, pid):
        patient = self.db.one('SELECT * FROM patients WHERE id=?',(pid,))
        if not patient:
            raise Missing('Patient not found')
        return patient

    def encounters(self,pid):
        self.patient(pid)
        return self.db.rows('SELECT * FROM encounters WHERE patient_id=? ORDER BY id',(pid,))

    def add_encounter(self,pid,data,actor):
        self.patient(pid)
        eid = safe_id(data.get('id'),'encounter_id')
        label = data.get('label','Assessment')
        if not isinstance(label,str) or len(label)>120:
            raise Invalid('Invalid encounter label')
        with self.db.transaction():
            if self.db.one('SELECT id FROM encounters WHERE id=?',(eid,)):
                raise Conflict('Encounter identifier already exists')
            self.db.execute('INSERT INTO encounters VALUES (?,?,?)',(eid,pid,label))
            self.audit(actor,'encounter.created',eid)
        return {'id':eid,'patient_id':pid,'label':label}

    def import_result(self,pid,payload,actor,source_type='manual',files=None,supersedes=None):
        self.patient(pid)
        if source_type not in ('manual','mock_api','pdf','image','correction'):
            raise Invalid('Unsupported source type; live vendor mapping is disabled')
        if payload.get('patient_id') and payload['patient_id'] != pid:
            raise Invalid('Payload patient association differs from selected patient')
        raw_payload = dumps(payload).encode()
        source_files = []
        claimed = None
        if source_type in ('pdf','image'):
            if not files or not 1<=len(files)<=5:
                raise Invalid('Supply 1–5 source files')
            combined = {}
            for data, kind in files:
                if kind != source_type:
                    raise Invalid('Choose a single import type')
                parsed = extract(data,kind)
                if parsed['claimed_patient_id'] and parsed['claimed_patient_id'] != pid:
                    raise Invalid('Source patient identifier conflicts with selected patient')
                claimed = parsed['claimed_patient_id'] or claimed
                for m in parsed['measurements']:
                    if m['metric'] in combined and combined[m['metric']]['value']!=m['value']:
                        m['value'],m['confidence'],m['quality_note'] = None,0,'Conflicting values across source files.'
                    combined[m['metric']]=m
                source_files.append({'sha256':self.storage.put(data),'media_type':kind,'size_bytes':len(data)})
            payload = dict(payload,measurements=list(combined.values()))
        result = normalize(payload)
        if not self.db.one('SELECT id FROM encounters WHERE id=? AND patient_id=?',(result['encounter_id'],pid)):
            raise Invalid('Encounter must belong to the selected patient')
        raw_hash = self.storage.put(raw_payload)
        digest = hashlib.sha256(dumps({'normalized':result,'files':source_files}).encode()).hexdigest()
        with self.db.transaction():
            previous = self.db.one('SELECT * FROM results WHERE patient_id=? AND source_type=? AND source_identifier=?',
                (pid,source_type,result['source_identifier']))
            if previous:
                if previous['source_hash'] != digest:
                    raise Conflict('Source identifier already used with different content')
                return self.detail(pid,previous['id']) | {'duplicate':True}
            original = self.detail(pid,supersedes) if supersedes else None
            if supersedes and self.db.one('SELECT id FROM results WHERE supersedes=?',(supersedes,)):
                raise Conflict('Result already superseded; correct the latest version')
            if original and result['test_timestamp'] != original['test_timestamp']:
                raise Invalid('Corrections must preserve the original test timestamp')
            result.update({'id':uid(),'patient_id':pid,'ingested_at':now(),'source_type':source_type,
                'supersedes':supersedes, 'claimed_patient_id':claimed,
                'source_result':{'payload_sha256':raw_hash,'files':source_files},
                'provenance':{'parser_version':PARSER_VERSION if files else 'normalized-contract-v1.0',
                    'software_version':'InBodyStage1-0.1.0','schema_version':'normalized-v1.0',
                    'source_hash':digest,'identity_binding':'operator-selected; no automatic name matching',
                    'superseded_source':original['source_result'] if original else None}})
            self.db.execute('INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?)',
                (result['id'],pid,result['encounter_id'],result['test_timestamp'],result['ingested_at'],source_type,
                 result['source_identifier'],digest,dumps(result),supersedes))
            self.audit(actor,'result.imported',result['id'])
        self.analyze(pid,result['id'],actor)
        return self.detail(pid,result['id'])

    def history(self,pid,include_superseded=False):
        self.patient(pid)
        rows = self.db.rows('SELECT * FROM results WHERE patient_id=?',(pid,))
        replaced = {r['supersedes'] for r in rows if r['supersedes']}
        content = [json.loads(r['content']) for r in rows if include_superseded or r['id'] not in replaced]
        return sorted(content,key=lambda r:datetime.fromisoformat(r['test_timestamp']),reverse=True)

    def detail(self,pid,rid):
        self.patient(pid)
        row = self.db.one('SELECT * FROM results WHERE id=? AND patient_id=?',(rid,pid))
        if not row: raise Missing('Result not found for this patient')
        result = json.loads(row['content'])
        analysis_rows = self.db.rows('SELECT * FROM analyses WHERE result_id=? ORDER BY created_at DESC,id DESC',(rid,))
        result['analyses'] = []
        for row in analysis_rows:
            a = json.loads(row['content'])
            reviews = self.db.rows('SELECT * FROM reviews WHERE analysis_id=? ORDER BY created_at DESC,id DESC',(row['id'],))
            a['reviews'],a['review_status'] = reviews,reviews[0]['status'] if reviews else 'pending'
            a['clinician_summary']['review_status'] = a['review_status']
            a['patient_summary']['review_status'] = a['review_status']
            result['analyses'].append(a)
        return result

    def analyze(self,pid,rid,actor):
        result = self.detail(pid,rid)
        patient = self.patient(pid)
        earlier = [r for r in self.history(pid) if datetime.fromisoformat(r['test_timestamp'])<datetime.fromisoformat(result['test_timestamp'])]
        previous = earlier[0] if earlier else None
        flags = apply_rules(result['measurements'],patient,result['test_timestamp'])
        comparison = compare(result,previous)
        clinician,patient_summary = summaries(result,flags,comparison)
        ai = {'used':False,'status':'disabled','model':None}
        if self.provider:
            try:
                sentences = {'c'+str(i):f['reason'] for i,f in enumerate(flags)}
                sentences |= {'p'+str(i):s for i,s in enumerate(patient_summary['sentences'])}
                synthesis = self.provider.synthesize({'sentences':sentences})
                # Providers cannot introduce text outside deterministic evidence.
                if not isinstance(synthesis,dict) or not all(k in synthesis for k in ('clinician','patient','model','provider')):
                    raise ValueError('Invalid synthesis')
                for key,prefix in (('clinician','c'),('patient','p')):
                    allowed = [v for k,v in sentences.items() if k.startswith(prefix)]
                    if not isinstance(synthesis[key],list) or not all(s in allowed for s in synthesis[key]):
                        raise ValueError('Unsupported synthesis')
                clinician['ai_generated_synthesis'] = synthesis['clinician']
                patient_summary['ai_generated_synthesis'] = synthesis['patient']
                ai = {'used':True,'status':'complete','model':synthesis['model'],'provider':synthesis['provider'],
                    'reported_model':synthesis.get('reported_model'), 'interface_version':'evidence-selection-v1.0'}
            except Exception:
                ai = {'used':False,'status':'unavailable-or-invalid','model':getattr(self.provider,'model','unknown')}
        analysis = {'id':uid(),'result_id':rid,'created_at':now(),
            'rule_findings':flags,'longitudinal_comparison':comparison,
            'clinician_summary':clinician,'patient_summary':patient_summary,
            'review_status':'pending','data_quality_passed':all(m['status']=='verified' and m['value'] is not None for m in result['measurements']),
            'provenance':{'analysis_version':VERSION,'rules_version':RULES['version'],'rules_snapshot':RULES,
                'source_hash':result['provenance']['source_hash'],'test_timestamp':result['test_timestamp'],
                'patient_context':{'dob':patient['dob'],'sex':patient['sex']}, 'ai':ai}}
        with self.db.transaction():
            self.db.execute('INSERT INTO analyses VALUES (?,?,?,?)',(analysis['id'],rid,analysis['created_at'],dumps(analysis)))
            self.db.execute('INSERT INTO outbox VALUES (?,?,?,?)',(uid(),now(),'inbody.analysis.complete',
                dumps({'patient_id':pid,'encounter_id':result['encounter_id'],'result_id':rid,
                       'analysis_id':analysis['id'],'review_required':True})))
            self.audit(actor,'result.analyzed',rid)
        return analysis

    def review(self,pid,rid,data,actor):
        result = self.detail(pid,rid)
        if not result['analyses']: raise Invalid('Analyze result before review')
        a = result['analyses'][0]
        if data.get('analysis_id') != a['id']:
            raise Conflict('Analysis changed; refresh before reviewing')
        status = data.get('status')
        if status not in ('accepted','held'):
            raise Invalid('Review status must be accepted or held')
        if status=='accepted' and not a['data_quality_passed']:
            raise Invalid('Confirm or correct extracted values in a linked new version before acceptance')
        if status=='accepted' and data.get('identity_confirmed') is not True:
            raise Invalid('Patient, encounter, test date/time and source identity must be confirmed')
        note = data.get('note','')
        if not isinstance(note,str) or len(note)>2000: raise Invalid('Invalid review note')
        with self.db.transaction():
            self.db.execute('INSERT INTO reviews VALUES (?,?,?,?,?,?)',(uid(),a['id'],now(),actor,status,note))
            self.audit(actor,'result.reviewed.'+status,rid)
        return self.detail(pid,rid)

    def correct(self,pid,rid,data,actor):
        current = self.detail(pid,rid)
        if not data.get('reason') or not isinstance(data['reason'],str) or len(data['reason'])>500:
            raise Invalid('A correction reason is required')
        # A new version links the original source and never modifies the old result.
        payload = {'patient_id':pid,'encounter_id':current['encounter_id'],
            'test_timestamp':current['test_timestamp'],'device_model':current['device_model'],
            'source_identifier':'correction-'+uid(),'measurements':data.get('measurements'),
            'correction_reason':data['reason']}
        return self.import_result(pid,payload,actor,'correction',supersedes=rid)

    def source_bytes(self,pid,rid,digest):
        result = self.detail(pid,rid)
        permitted = []
        source = result['source_result']
        permitted.append(source['payload_sha256'])
        permitted.extend(f['sha256'] for f in source['files'])
        inherited = result['provenance'].get('superseded_source')
        if inherited:
            permitted.append(inherited['payload_sha256'])
            permitted.extend(f['sha256'] for f in inherited['files'])
        if digest not in permitted:
            raise Missing('Source not found for this result')
        data = self.storage.get(digest)
        media = 'application/pdf' if data.startswith(b'%PDF-') else 'image/png' if data.startswith(b'\x89PNG') else 'image/jpeg' if data.startswith(b'\xff\xd8') else 'application/json'
        return data,media

    def trends(self,pid):
        results = list(reversed(self.history(pid)))
        metrics = {}
        for r in results:
            for m in r['measurements']:
                if m['status']=='verified' and m['value'] is not None:
                    key = m['metric']+'|'+m['unit']
                    metrics.setdefault(key,{'metric':m['metric'],'unit':m['unit'],'points':[]})['points'].append(
                        {'test_timestamp':r['test_timestamp'],'result_id':r['id'],'value':m['value']})
        return list(metrics.values())

    def seed(self):
        if self.patients(): return
        for pid,name,sex,dob in [('SYN-001','Alex Morgan · Synthetic','male','1982-04-17'),
                                  ('SYN-002','Jordan Lee · Synthetic','female','1990-08-22')]:
            self.add_patient({'id':pid,'name':name,'sex':sex,'dob':dob,'synthetic':True},'seed')
            self.add_encounter(pid,{'id':pid+'-BASE','label':'Baseline assessment'},'seed')
            self.add_encounter(pid,{'id':pid+'-FOLLOW','label':'Follow-up assessment'},'seed')
        for index,stamp in enumerate(('2026-08-07T09:30:00-04:00','2026-09-07T09:30:00-04:00','2026-10-07T09:30:00-04:00')):
            self.import_result('SYN-001',{'encounter_id':'SYN-001-BASE' if index==0 else 'SYN-001-FOLLOW',
                'test_timestamp':stamp,'source_identifier':'demo-'+str(index),'device_model':'Synthetic InBody fixture',
                'measurements':[{'metric':m,'value':v,'unit':u} for m,v,u in
                    [('weight',84-index*1.2,'kg'),('bmi',27.4-index*0.4,'kg/m2'),
                     ('skeletal_muscle_mass',34+index*0.3,'kg'),('body_fat_mass',22-index*0.9,'kg'),
                     ('percent_body_fat',26.2-index*0.7,'%'),('total_body_water',44.7+index*0.2,'L'),
                     ('ecw_tbw',0.385,'ratio'),('visceral_fat_area',105-index*4,'cm2'),
                     ('phase_angle',5.8+index*0.1,'deg')]]},'seed','mock_api')
