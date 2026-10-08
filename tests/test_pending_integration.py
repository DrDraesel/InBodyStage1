import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import openpyxl

from adapters.inbody.spreadsheets import extract_sheet
from backend.config import load_env, readiness
from backend import inbox
from backend.server import Application
from scripts.local_export_bridge import collect
from scripts.setup_local import initialize
from tests import test_stage1 as fixtures


class PendingIntegration(unittest.TestCase):
    setUp = fixtures.Stage1.setUp
    tearDown = fixtures.Stage1.tearDown
    payload = fixtures.Stage1.payload

    def test_env_literal_preserves_overrides_and_setup_secrets_not_in_readiness(self):
        config = self.path / '.env'
        config.write_text('AI_MODEL="literal-model"\nAI_API_KEY=literal-secret\nAI_ENABLED=true\n')
        environment = {'AI_MODEL': 'process-model'}
        load_env(config, environment)
        self.assertEqual(environment['AI_MODEL'], 'process-model')
        self.assertTrue(readiness(environment)['ai']['configured'])
        self.assertNotIn('literal-secret', json.dumps(readiness(environment)))
        path = self.path / 'generated.env'
        self.assertTrue(initialize(path))
        self.assertFalse(initialize(path))
        settings = {}; load_env(path, settings)
        self.assertGreaterEqual(len(settings['INBODY_CLINICIAN_TOKEN']), 32)
        self.assertNotEqual(settings['INBODY_CLINICIAN_TOKEN'], settings['INBODY_OPERATOR_TOKEN'])
        with patch.dict(os.environ, settings, clear=True): Application(self.s)

    def test_actual_xlsx_and_csv_extraction_with_units_no_formula_execution(self):
        workbook = openpyxl.Workbook(); sheet = workbook.active
        sheet.append(['Patient ID','Weight (lb)','BMI (kg/m2)'])
        sheet.append(['SYN-1',180,27])
        content = io.BytesIO(); workbook.save(content)
        parsed = extract_sheet(content.getvalue(), 'xlsx')
        self.assertEqual(parsed['claimed_patient_id'], 'SYN-1')
        self.assertEqual(next(m for m in parsed['measurements'] if m['metric']=='weight')['value'],180)
        result = self.s.import_result('SYN-1', self.payload(), 'test', 'spreadsheet', [(content.getvalue(),'xlsx')])
        self.assertAlmostEqual(next(m for m in result['measurements'] if m['metric']=='weight')['value'],81.646627)
        self.assertFalse(result['analyses'][0]['data_quality_passed'])
        digest = result['source_result']['files'][0]['sha256']
        source,media = self.s.source_bytes('SYN-1', result['id'], digest)
        self.assertEqual(source, content.getvalue()); self.assertIn('spreadsheetml',media)
        formula = extract_sheet(b'metric,value,unit\nweight,=1+1,kg\n','csv')
        self.assertIsNone(formula['measurements'][0]['value'])
        with self.assertRaises(ValueError):
            extract_sheet(b'patient_id,Weight (kg)\nSYN-1,80\nSYN-2,75\n','csv')

    def test_export_queue_to_import_and_tamper_rejection(self):
        exports = self.path / 'exports'; exports.mkdir()
        queue = self.path / 'queue'
        data = b'metric,value,unit\nweight,80,kg\nbmi,27,kg/m2\n'
        (exports/'synthetic.csv').write_bytes(data)
        digest = collect(exports,queue,0)[0]
        with patch.dict(os.environ,{'INBODY_INBOX_DIR':str(queue)}):
            self.assertEqual(inbox.listing()[0]['sha256'],digest)
            record,original,kind=inbox.package(digest)
            self.assertEqual(original,data)
            result=self.s.import_result('SYN-1',self.payload(),'test','spreadsheet',[(original,kind)])
            self.assertEqual(result['source_result']['files'][0]['sha256'],digest)
            (queue/digest/'original.csv').write_bytes(b'tampered')
            with self.assertRaises(ValueError): inbox.package(digest)
            self.assertEqual(inbox.listing(),[])

    def test_catalog_sources_are_imw_and_requested_topics_not_orders(self):
        result=self.s.import_result('SYN-1',self.payload(),'test','mock_api')
        analysis=self.s.analyze('SYN-1',result['id'],'test',{'requested_service_topics':['weight_management']})
        options=analysis['recommendation_plan']['clinic_care_options']
        self.assertTrue(all(o['source_url'].startswith('https://www.innovativemedicalwellness.com/en/') for o in options))
        self.assertTrue(all(o['price'] is None and not o['booking_created'] for o in options))
        weight=next(o for o in options if o['id']=='weight_management')
        self.assertEqual(weight['status'],'education_requested')
        exosomes=next(o for o in options if o['id']=='exosome_review')
        self.assertEqual(exosomes['status'],'evidence_regulatory_review_required')
        with self.assertRaises(ValueError):
            self.s.analyze('SYN-1',result['id'],'test',{'requested_service_topics':['imaginary_offering']})
