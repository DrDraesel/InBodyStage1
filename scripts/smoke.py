"""Synthetic smoke test against a separately started authenticated HTTP server."""
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from backend.config import ROOT
from scripts.local_export_bridge import collect


def main():
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        with socket.socket() as socket_:
            socket_.bind(('127.0.0.1', 0))
            port = socket_.getsockname()[1]
        token, operator = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
        env = dict(os.environ, INBODY_HOST='127.0.0.1', INBODY_PORT=str(port), AI_ENABLED='false',
                   INBODY_CLINICIAN_TOKEN=token, INBODY_OPERATOR_TOKEN=operator,
                   INBODY_DATABASE_URL='sqlite:///'+str(work/'smoke.db'),
                   INBODY_STORAGE_DIR=str(work/'sources'), INBODY_INBOX_DIR=str(work/'queue'))
        process = subprocess.Popen([sys.executable, '-m', 'backend.server', '--seed'], cwd=ROOT,
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = 'http://127.0.0.1:'+str(port)

        def request(path, payload=None, auth=True, raw=None, content_type=None):
            headers = {'Authorization':'Bearer '+token} if auth else {}
            data = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
            if data is not None: headers['Content-Type']=content_type or 'application/json'
            with urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers),timeout=5) as response:
                body=response.read()
                return json.loads(body) if response.headers.get('Content-Type','').startswith('application/json') else body

        try:
            for attempt in range(50):
                if process.poll() is not None: raise RuntimeError('HTTP server did not start')
                try:
                    request('/health', auth=False); break
                except (OSError, urllib.error.URLError): time.sleep(.1)
            else: raise RuntimeError('HTTP startup timeout')
            assert b'InBody results' in request('/',auth=False)
            assert b'#1565d8' in request('/style.css',auth=False)
            try:
                request('/patients',auth=False)
                raise AssertionError('Unauthenticated access accepted')
            except urllib.error.HTTPError as error: assert error.code==403
            assert request('/inbody/readiness')['ai']['enabled'] is False
            catalog=request('/inbody/services')
            assert len(catalog['services'])==12
            exports=work/'exports';exports.mkdir()
            source=b'metric,value,unit\nweight,80,kg\nbmi,27,kg/m2\n'
            (exports/'synthetic.csv').write_bytes(source)
            digest=collect(exports,work/'queue',0)[0]
            assert request('/inbody/inbox')[0]['sha256']==digest
            assert request('/inbody/inbox/'+digest+'/source')==source
            metadata={'patient_id':'SYN-001','encounter_id':'SYN-001-FOLLOW','source_type':'spreadsheet',
                      'source_identifier':'synthetic-http-smoke','device_model':'Synthetic fixture',
                      'test_timestamp':'2026-10-08T11:00:00-04:00'}
            boundary='SyntheticSmokeBoundary'
            body=(f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'+json.dumps(metadata)+
                  f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="synthetic.csv"\r\nContent-Type: text/csv\r\n\r\n').encode()+source+f'\r\n--{boundary}--\r\n'.encode()
            preview=request('/inbody/extract',raw=body,content_type='multipart/form-data; boundary='+boundary)
            assert preview['saved'] is False and len(preview['measurements'])==2
            result=request('/patients/SYN-001/inbody/import',raw=body,content_type='multipart/form-data; boundary='+boundary)
            assert result['source_result']['files'][0]['sha256']==hashlib.sha256(source).hexdigest()
            assert result['analyses'][0]['data_quality_passed'] is False
            path='/patients/SYN-001/inbody/'+result['id']
            measurements=[dict(m,status='verified',confidence=1,quality_note='') for m in result['measurements']]
            corrected=request(path+'/correct',{'measurements':measurements,'reason':'Synthetic smoke source confirmation'})
            corrected_path='/patients/SYN-001/inbody/'+corrected['id']
            analysis=request(corrected_path+'/analyze',{'recommendation_context':{'requested_service_topics':['weight_management']}})
            assert next(o for o in analysis['recommendation_plan']['clinic_care_options'] if o['id']=='weight_management')['status']=='education_requested'
            request(corrected_path+'/review',{'analysis_id':analysis['id'],'status':'accepted','identity_confirmed':True,'note':'Synthetic smoke'})
            saved=request(corrected_path)
            assert saved['analyses'][0]['review_status']=='accepted'
            assert request(corrected_path+'/sources/'+digest)==source
            assert saved['analyses'][0]['recommendation_plan']['status']=='draft_for_clinician_review'
            print('HTTP smoke passed: auth, blue UI, readiness, 12-service catalog, inbox, extraction, import, correction, context, review and original source retrieval.')
        finally:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill();process.wait()
            process.stderr.close()


if __name__=='__main__': main()
