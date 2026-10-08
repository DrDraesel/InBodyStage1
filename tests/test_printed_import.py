"""Printed-result evidence: real codes, mixed PDFs, transcription and preserved provenance."""
import io
import unittest
from unittest.mock import patch
from PIL import Image
import zxingcpp
from adapters.inbody.documents import extract, parse_text, decode_codes
from backend.server import Application
from tests import test_stage1 as fixtures

class PrintedImport(unittest.TestCase):
    setUp = fixtures.Stage1.setUp
    tearDown = fixtures.Stage1.tearDown
    payload = fixtures.Stage1.payload
    pdf = fixtures.Stage1.pdf
    image = fixtures.Stage1.image
    def code_image(self, text='SYN-REPORT-1', fmt=zxingcpp.BarcodeFormat.QRCode):
        img=Image.fromarray(zxingcpp.write_barcode(fmt,text,width=500,height=180 if fmt==zxingcpp.BarcodeFormat.Code128 else 500))
        out=io.BytesIO();img.save(out,format='PNG');return out.getvalue()

    def test_real_qr_and_barcode(self):
        for fmt in (zxingcpp.BarcodeFormat.QRCode,zxingcpp.BarcodeFormat.Code128):
            codes,warning=decode_codes(self.code_image(fmt=fmt))
            self.assertIsNone(warning);self.assertEqual(codes[0]['text'],'SYN-REPORT-1')
            self.assertEqual(codes[0]['status'],'unverified')

    def test_qr_link_not_fetched_or_identity_bound(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('Must not fetch code URLs')):
            parsed=extract(self.code_image('https://example.invalid/report/SYN-2'),'image',allow_empty=True)
        self.assertEqual(parsed['barcodes'][0]['text'],'https://example.invalid/report/SYN-2')
        self.assertIsNone(parsed['claimed_patient_id']);self.assertEqual(parsed['measurements'],[])

    def test_printed_units_segmental_and_full_text(self):
        parsed=parse_text('Weight (kg) 80\nTotal Body Water (L)\n44.5\nRight Arm Lean Mass: 3.1 kg\nImpedance table not mapped')
        values={m['metric']:m for m in parsed['measurements']}
        self.assertEqual(values['weight']['value'],80)
        self.assertEqual(values['total_body_water']['value'],44.5)
        self.assertEqual(values['right_arm_lean_mass']['value'],3.1)
        self.assertTrue(all(m['status']=='unverified' for m in values.values()))

    def test_mixed_pdf_reads_scanned_page(self):
        import fitz
        doc=fitz.open();doc.new_page().insert_text((50,50),'Weight: 80 kg')
        page=doc.new_page();page.insert_image(fitz.Rect(20,20,580,160),stream=self.image())
        parsed=extract(doc.tobytes(),'pdf')
        self.assertEqual([p['method'] for p in parsed['pages']],['pdf-text','ocr'])
        self.assertIn('BMI',parsed['raw_text']);self.assertEqual(len(parsed['pages']),2)

    def test_scanner_and_transcription_preserve_source(self):
        p=self.payload();p['scanned_codes']='SYN-REPORT-1'
        p['transcribed_measurements']=[{'metric':'weight','value':80,'unit':'kg','status':'verified','confidence':1}]
        r=self.s.import_result('SYN-1',p,'test','image',[(self.code_image(),'image')])
        self.assertEqual(r['source_extraction'][0]['barcodes'][0]['text'],'SYN-REPORT-1')
        self.assertEqual(r['scanned_codes'][0]['text'],'SYN-REPORT-1')
        self.assertFalse(r['analyses'][0]['data_quality_passed'])
        self.assertEqual(r['measurements'][0]['status'],'unverified')
        corrected=self.s.correct('SYN-1',r['id'],{'reason':'Verified original','measurements':[{'metric':'weight','value':80,'unit':'kg'}]},'clinician')
        self.assertEqual(corrected['source_extraction'],r['source_extraction'])
        self.assertEqual(corrected['scanned_codes'],r['scanned_codes'])
        digest=r['source_result']['files'][0]['sha256']
        self.assertEqual(self.s.source_bytes('SYN-1',corrected['id'],digest)[0],self.code_image())

    def test_preview_does_not_save_and_readiness_honest(self):
        app=Application(self.s)
        preview=app.route('POST','/inbody/extract',{},[(self.pdf(),'pdf')],'operator')[1]
        self.assertFalse(preview['saved']);self.assertEqual(self.s.history('SYN-1'),[])
        status=app.route('GET','/inbody/connectivity',{},None,'operator')[1]
        self.assertEqual(status['automatic_sync'],'not_configured')

    def test_overlong_scanner_rejected(self):
        p=self.payload();p['scanned_codes']='x'*4097
        with self.assertRaises(ValueError):self.s.import_result('SYN-1',p,'test')

