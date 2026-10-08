"""Reproducible static OpenAPI 3.1 document and normalized JSON Schema."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
measurement={'type':'object','required':['metric','value','unit'],'properties':{
 'metric':{'type':'string','pattern':'^[A-Za-z0-9_-]{1,80}$'},
 'value':{'type':['number','null']},'unit':{'type':'string','minLength':1,'maxLength':40},
 'status':{'enum':['verified','unverified']},'confidence':{'type':'number','minimum':0,'maximum':1},
 'quality_note':{'type':'string','maxLength':500},
 'device_reference':{'type':['object','null'],'required':['low','high','source','version'],
                     'properties':{'low':{'type':'number'},'high':{'type':'number'},'source':{'type':'string'},'version':{'type':'string'}}}}}
result={'type':'object','required':['encounter_id','test_timestamp','source_identifier','measurements'],'properties':{
 'patient_id':{'type':'string'},'encounter_id':{'type':'string'},'test_timestamp':{'type':'string','format':'date-time'},
 'source_identifier':{'type':'string','minLength':1,'maxLength':200},'device_model':{'type':'string'},
 'source_type':{'enum':['manual','mock_api','pdf','image']},
 'measurements':{'type':'array','minItems':1,'maxItems':200,'items':measurement}}}
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://inbodystage1.local/normalized-v1.json',**result}
(ROOT/'schemas/normalized-v1.json').write_text(json.dumps(schema,indent=2)+'\n')
paths={}
def operation(path,method,summary,body=None,parameters=None,status='200'):
 op={'summary':summary,'operationId':method+'_'+path.replace('/','_').replace('{','').replace('}',''),
     'security':[{'BearerAuth':[]}],'responses':{status:{'description':'Successful response','content':{'application/json':{'schema':{'type':['object','array']}}}},
      '400':{'description':'Validation error'},'403':{'description':'Authentication or role denied'},'404':{'description':'Patient-scoped resource not found'},'409':{'description':'Version or idempotency conflict'}}}
 params=[{'name':x,'in':'path','required':True,'schema':{'type':'string'}} for x in ('patient_id','result_id') if '{'+x+'}' in path]
 if parameters:params+=parameters
 if params:op['parameters']=params
 if body:op['requestBody']={'required':True,'content':body}
 paths.setdefault(path,{})[method]=op
json_body=lambda schema:{'application/json':{'schema':schema}}
base='/patients/{patient_id}/inbody'
operation('/patients','get','List synthetic patients')
operation('/patients','post','Create synthetic patient',json_body({'type':'object','required':['id','name','synthetic'],'properties':{'id':{'type':'string'},'name':{'type':'string'},'synthetic':{'const':True},'dob':{'type':'string','format':'date'},'sex':{'enum':['male','female','unknown']}}}),status='201')
operation('/patients/{patient_id}/encounters','get','List patient encounters')
operation('/patients/{patient_id}/encounters','post','Create encounter',json_body({'type':'object','required':['id'],'properties':{'id':{'type':'string'},'label':{'type':'string'}}}),status='201')
operation(base+'/import','post','Import completed result; source file values require confirmation',{
 **json_body(result),'multipart/form-data':{'schema':{'type':'object','required':['metadata','files'],'properties':{
 'metadata':{'type':'string','description':'JSON metadata: encounter_id, test_timestamp, source_identifier, device_model, source_type; optional scanned_codes (max 4096 chars) and transcribed_measurements (1–200). No guessed timestamp.'},
 'files':{'type':'array','minItems':1,'maxItems':5,'items':{'type':'string','format':'binary'}}}}}},status='201')
operation('/inbody/extract','post','Preview OCR and barcode/QR evidence without saving a result',{'multipart/form-data':{'schema':{'type':'object','required':['files'],'properties':{'metadata':{'type':'string'},'files':{'type':'array','minItems':1,'maxItems':5,'items':{'type':'string','format':'binary'}}}}}})
operation('/inbody/connectivity','get','Report app sync readiness; does not probe the clinic network')
operation('/inbody/webhook','post','Internal synthetic fixture webhook; live vendor webhook disabled',json_body({'allOf':[result,{'type':'object','required':['patient_id','contract'],'properties':{'contract':{'const':'synthetic-normalized-v1'}}}]}),status='201')
operation(base,'get','List all patient studies including superseded versions')
operation(base+'/{result_id}','get','Get source, measurements, analysis versions and review history')
operation(base+'/trends','get','Verified measurement trends excluding superseded tests')
context={'type':'object','additionalProperties':False,'properties':{
 'goals':{'type':'string','maxLength':500},'activity_level':{'enum':['unknown','sedentary','some','regular']},
 **{key:{'enum':['unknown','yes','no']} for key in ('pain_present','falls_or_balance_concern','pregnancy_or_breastfeeding','cardiovascular_symptoms')},
 'clinical_history_reviewed':{'type':'boolean'},'medications_reviewed':{'type':'boolean'}}}
operation(base+'/{result_id}/analyze','post','Append analysis and clinician recommendation draft; optional AI evidence selection',json_body({'type':'object','properties':{'recommendation_context':context}}),status='201')
operation(base+'/{result_id}/review','post','Clinician-only review of current analysis',json_body({'type':'object','required':['analysis_id','status'],'properties':{'analysis_id':{'type':'string'},'status':{'enum':['accepted','held']},'identity_confirmed':{'type':'boolean'},'note':{'type':'string','maxLength':2000}}}))
operation(base+'/{result_id}/correct','post','Clinician-only linked correction; source facts remain immutable',json_body({'type':'object','required':['reason','measurements'],'properties':{'reason':{'type':'string','maxLength':500},'measurements':result['properties']['measurements']}}))
operation(base+'/{result_id}/source','get','Source metadata and SHA-256 hashes')
operation(base+'/{result_id}/sources/{sha256}','get','Download authorized original source bytes')
paths[base+'/{result_id}/sources/{sha256}']['get']['parameters'].append({'name':'sha256','in':'path','required':True,'schema':{'type':'string','pattern':'^[a-f0-9]{64}$'}})
operation('/health','get','Health and synthetic-only mode');paths['/health']['get']['security']=[]
doc={'openapi':'3.1.0','info':{'title':'InBodyStage1','version':'0.1.0','description':'Local-first synthetic proof of concept. See README for explicit deployment limits.'},
     'servers':[{'url':'http://127.0.0.1:8080'}],'paths':paths,'components':{'securitySchemes':{'BearerAuth':{'type':'http','scheme':'bearer','description':'Server-configured operator/clinician token. Separate token for internal webhook.'}}}}
(ROOT/'docs/openapi.json').write_text(json.dumps(doc,indent=2)+'\n')
