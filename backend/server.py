"""Loopback HTTP application with bounded requests, same-origin checks and bearer RBAC."""
import argparse
import hmac
import json
import os
import re
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from backend.database import Database, ROOT
from backend.service import Service, Invalid, Missing, Conflict, dumps
from adapters.storage.local import LocalSourceStorage
from adapters.inbody.documents import MAX_BYTES

MAX_REQUEST = 5*MAX_BYTES+65536

class Application:
    def __init__(self, service):
        self.service = service
        self.clinician = os.getenv('INBODY_CLINICIAN_TOKEN','')
        self.operator = os.getenv('INBODY_OPERATOR_TOKEN','')
        self.webhook = os.getenv('INBODY_WEBHOOK_TOKEN','')
        if bool(self.clinician) != bool(self.operator):
            raise ValueError('Configure both clinician and operator tokens, or neither for loopback demo')
        if any(t and len(t)<32 for t in (self.clinician,self.operator,self.webhook)):
            raise ValueError('Tokens must contain at least 32 characters')
        if self.clinician and self.clinician==self.operator:
            raise ValueError('Operator and clinician tokens must differ')

    def role(self, token, webhook=False):
        if webhook:
            if self.webhook and hmac.compare_digest(token,self.webhook): return 'webhook'
            raise PermissionError('Webhook bearer token required')
        if not self.clinician: return 'demo-clinician'
        if hmac.compare_digest(token,self.clinician): return 'clinician'
        if hmac.compare_digest(token,self.operator): return 'operator'
        raise PermissionError('Authentication required')

    def route(self,method,path,payload,files,role):
        s = self.service
        if path=='/inbody/extract' and method=='POST':
            return 200,s.extract_sources(files)
        if path=='/inbody/connectivity' and method=='GET':
            return 200,{'automatic_sync':'not_configured','vendor_mapping':'awaiting_official_documentation',
                'required':['Exact device model','Clinic computer access','Activated LookinBody 120 installation','Verified device pairing in LookinBody','Automatic CSV/image export folder','Local intake bridge and confirmed patient/encounter mapping'],
                'connection_mode':'local_export_without_cloud_api','hardware_pairing':'not_verified','local_intake_bridge':'available_not_running_on_clinic_pc',
                'import_methods':['pdf','photo_ocr','barcode_qr_evidence','scanner_entry'],
                'network_note':'Device Wi-Fi was reported by the operator. This server cannot verify or pair clinic hardware; run LookinBody and the intake bridge locally.'}
        if path=='/patients':
            if method=='GET': return 200,s.patients()
            if method=='POST': return 201,s.add_patient(payload,role)
        if path=='/inbody/webhook' and method=='POST':
            # INTERNAL normalized fixture webhook. Vendor auth/envelope is not invented.
            if payload.get('contract')!='synthetic-normalized-v1':
                raise Invalid('Only synthetic-normalized-v1 webhook contract is enabled')
            return 201,s.import_result(payload.get('patient_id'),payload,role,'mock_api')
        m = re.fullmatch(r'/patients/([A-Za-z0-9_-]+)/encounters',path)
        if m:
            if method=='GET': return 200,s.encounters(m[1])
            if method=='POST': return 201,s.add_encounter(m[1],payload,role)
        m = re.fullmatch(r'/patients/([A-Za-z0-9_-]+)/inbody(?:/([A-Za-z0-9_-]+))?(?:/([a-z]+))?',path)
        if m:
            pid,rid,action=m.groups()
            if method=='GET' and rid is None: return 200,s.history(pid,True)
            if method=='GET' and rid=='trends': return 200,s.trends(pid)
            if method=='POST' and rid=='import':
                return 201,s.import_result(pid,payload,role,payload.get('source_type','manual'),files)
            if rid and method=='GET' and not action: return 200,s.detail(pid,rid)
            if method=='POST' and action=='analyze': return 201,s.analyze(pid,rid,role)
            if method=='POST' and action in ('review','correct'):
                if role not in ('clinician','demo-clinician'): raise PermissionError('Clinician role required')
                return 200,(s.review(pid,rid,payload,role) if action=='review' else s.correct(pid,rid,payload,role))
            if method=='GET' and action=='source':
                result=s.detail(pid,rid)
                return 200,result['source_result']
        raise Missing('Endpoint not found')

class Handler(BaseHTTPRequestHandler):
    server_version='InBodyStage1'
    def log_message(self,*args): pass  # Avoid identifiers in console/access logs.
    def send(self,status,body,kind='application/json'):
        data = dumps(body).encode() if kind=='application/json' else body
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def dispatch(self):
        try:
            # Reject DNS rebinding and unrecognized proxy hosts. No CORS is enabled.
            host = self.headers.get('Host','').split(':')[0]
            allowed = os.getenv('INBODY_ALLOWED_HOSTS','localhost,127.0.0.1').split(',')
            if host not in allowed: raise PermissionError('Host is not allowed')
            origin=self.headers.get('Origin')
            if origin and urlparse(origin).netloc!=self.headers.get('Host'):
                raise PermissionError('Cross-origin requests are not allowed')
            path=urlparse(self.path).path
            if path=='/health' and self.command=='GET':
                self.server.app.service.db.one('SELECT 1 AS ready')
                return self.send(200,{'status':'ok','mode':'synthetic-only','version':'0.1.0'})
            if self.command=='GET' and path in ('/','/app.js','/style.css','/openapi.json'):
                name={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/openapi.json':'../docs/openapi.json'}[path]
                file=ROOT/'frontend'/name
                kind={'/':'text/html; charset=utf-8','/app.js':'text/javascript','/style.css':'text/css','/openapi.json':'application/json'}[path]
                return self.send(200,file.read_bytes(),kind if path!='/openapi.json' else 'application/json; charset=utf-8')
            token=self.headers.get('Authorization','').removeprefix('Bearer ')
            role=self.server.app.role(token,path=='/inbody/webhook')
            source_match=re.fullmatch(r'/patients/([A-Za-z0-9_-]+)/inbody/([A-Za-z0-9_-]+)/sources/([a-f0-9]{64})',path)
            if source_match and self.command=='GET':
                with self.server.app.service.db.transaction():
                    data,media=self.server.app.service.source_bytes(*source_match.groups())
                    self.server.app.service.audit(role,'source.downloaded',source_match[2])
                return self.send(200,data,media+'; charset=binary')
            payload,files={},None
            if self.command=='POST':
                length=int(self.headers.get('Content-Length','0'))
                if length<1 or length>MAX_REQUEST: raise Invalid('Request exceeds size limit or is empty')
                body=self.rfile.read(length)
                content_type=self.headers.get('Content-Type','')
                if content_type.startswith('multipart/form-data'):
                    message=BytesParser(policy=default).parsebytes(b'Content-Type: '+content_type.encode()+b'\r\nMIME-Version: 1.0\r\n\r\n'+body)
                    if not message.is_multipart(): raise Invalid('Invalid multipart form')
                    files=[]
                    for part in message.iter_parts():
                        name=part.get_param('name',header='content-disposition')
                        data=part.get_payload(decode=True)
                        if name=='metadata': payload=json.loads(data)
                        elif name=='files':
                            typ=part.get_content_type()
                            kind='pdf' if typ=='application/pdf' else 'image' if typ in ('image/png','image/jpeg') else None
                            if not kind: raise Invalid('Only PDF, PNG, JPEG files accepted')
                            if len(data)>MAX_BYTES: raise Invalid('File too large')
                            files.append((data,kind))
                        else: raise Invalid('Unexpected multipart field')
                elif content_type.startswith('application/json'):
                    payload=json.loads(body,parse_constant=lambda _: (_ for _ in ()).throw(Invalid('Non-finite JSON number')))
                else: raise Invalid('Use JSON or multipart/form-data')
                if not isinstance(payload,dict): raise Invalid('JSON object required')
            # Single app lock serializes DB access and idempotency (one process in Stage 1).
            with self.server.app.service.db.lock:
                status,result=self.server.app.route(self.command,path,payload,files,role)
                with self.server.app.service.db.transaction():
                    self.server.app.service.audit(role,'http.'+self.command,path)
            self.send(status,result)
        except PermissionError as e: self.send(403,{'error':str(e)})
        except Missing as e: self.send(404,{'error':str(e)})
        except Conflict as e: self.send(409,{'error':str(e)})
        except (Invalid,ValueError,KeyError,TypeError) as e: self.send(400,{'error':str(e)})
        except Exception: self.send(500,{'error':'Internal operation failed; no result accepted. Check local configuration.'})
    def do_GET(self): self.dispatch()
    def do_POST(self): self.dispatch()

class Server(ThreadingHTTPServer):
    def get_request(self):
        sock,addr=super().get_request()
        sock.settimeout(45)
        return sock,addr

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seed',action='store_true')
    args=parser.parse_args()
    db=Database(os.getenv('INBODY_DATABASE_URL','sqlite:///runtime/inbody.db'))
    service=Service(db,LocalSourceStorage(os.getenv('INBODY_STORAGE_DIR','runtime/sources')))
    if args.seed: service.seed()
    app=Application(service)
    host=os.getenv('INBODY_HOST','127.0.0.1')
    if host not in ('127.0.0.1','localhost') and not app.clinician:
        raise ValueError('Non-loopback binding requires authenticated mode')
    server=Server((host,int(os.getenv('INBODY_PORT','8080'))),Handler)
    server.app=app
    print(f'InBodyStage1 synthetic-only server: http://{host}:{server.server_port}',flush=True)
    try: server.serve_forever()
    finally: server.server_close(); db.close()

if __name__=='__main__': main()
