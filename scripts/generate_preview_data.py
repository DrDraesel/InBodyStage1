"""Generate ONLY fixed synthetic preview fixtures from the real local analysis pipeline."""
import json
import tempfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.database import Database
from backend.service import Service
from adapters.storage.local import LocalSourceStorage
with tempfile.TemporaryDirectory() as directory:
    db=Database('sqlite:///'+directory+'/preview.db')
    service=Service(db,LocalSourceStorage(directory+'/sources'))
    service.seed()
    patients=service.patients()
    encounters={p['id']:service.encounters(p['id']) for p in patients}
    histories={p['id']:[service.detail(p['id'],r['id']) for r in service.history(p['id'])] for p in patients}
    samples={}
    for pid,weight,bmi,muscle,fat in [('SYN-001',79.9,26.1,34.9,23.6),('SYN-002',64.2,23.4,25.1,28.0)]:
        payload={'patient_id':pid,'encounter_id':pid+'-FOLLOW','test_timestamp':'2026-10-08T09:30:00-04:00',
                 'source_identifier':'visual-sample-'+pid,'device_model':'Synthetic InBody fixture',
                 'measurements':[{'metric':m,'value':v,'unit':u} for m,v,u in [('weight',weight,'kg'),('bmi',bmi,'kg/m2'),
                 ('skeletal_muscle_mass',muscle,'kg'),('percent_body_fat',fat,'%'),('body_fat_mass',round(weight*fat/100,2),'kg')]]}
        samples[pid]=service.import_result(pid,payload,'preview-generator','mock_api')
    data={'mode':'synthetic-visual-preview','patients':patients,'encounters':encounters,'histories':histories,'samples':samples}
    assert all(p['synthetic']==1 for p in patients)
    (ROOT/'preview/demo-data.json').write_text(json.dumps(data,indent=2)+'\n')
    db.close()
