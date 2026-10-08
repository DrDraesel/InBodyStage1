import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.local_export_bridge import collect


class LocalExportBridge(unittest.TestCase):
    def test_export_retained_deduplicated_and_unassigned(self):
        with tempfile.TemporaryDirectory() as directory:
            inbox = Path(directory) / 'exports'; inbox.mkdir()
            queue = Path(directory) / 'review'
            original = b'Unmapped vendor column,Another column\r\n123,456\r\n'
            (inbox / 'synthetic.csv').write_bytes(original)
            digest = hashlib.sha256(original).hexdigest()
            self.assertEqual(collect(inbox, queue, 0), [digest])
            self.assertEqual(collect(inbox, queue, 0), [])
            record = json.loads((queue / digest / 'review.json').read_text())
            self.assertIsNone(record['patient_id'])
            self.assertTrue(record['review_required'])
            self.assertFalse(record['hardware_connection_verified'])
            self.assertEqual(record['extraction']['measurements'], [])
            self.assertEqual((queue / digest / record['original_file']).read_bytes(), original)
            self.assertEqual((inbox / 'synthetic.csv').read_bytes(), original)

    def test_waits_for_recent_file_and_rejects_nested_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            inbox = Path(directory) / 'exports'; inbox.mkdir()
            (inbox / 'synthetic.csv').write_text('header\nvalue\n')
            self.assertEqual(collect(inbox, Path(directory) / 'review', 60), [])
            with self.assertRaises(ValueError):
                collect(inbox, inbox / 'review', 0)
