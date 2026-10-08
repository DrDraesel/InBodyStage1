import sqlite3
import unittest

from backend.database import Database
from backend.service import Invalid
from tests import test_stage1 as fixtures


class PatientIdentity(unittest.TestCase):
    setUp = fixtures.Stage1.setUp
    tearDown = fixtures.Stage1.tearDown

    def test_structured_names_and_dob_survive_restart(self):
        created = self.s.add_patient({'id':'SYN-3','first_name':' Avery ',
            'last_name':'Example-Smith','dob':'1990-05-16','synthetic':True}, 'operator')
        self.assertEqual(created['name'], 'Avery Example-Smith')
        self.db.close()
        self.db = Database('sqlite:///'+str(self.path/'tests.db'))
        stored = self.db.one('SELECT * FROM patients WHERE id=?', ('SYN-3',))
        self.assertEqual((stored['first_name'],stored['last_name'],stored['dob']),
                         ('Avery','Example-Smith','1990-05-16'))

    def test_invalid_dates_and_incomplete_names_rejected(self):
        base={'id':'SYN-3','first_name':'Avery','last_name':'Example','synthetic':True}
        for dob in ('2026-02-30','9999-01-01','19900516',123):
            with self.subTest(dob=dob), self.assertRaises(Invalid):
                self.s.add_patient(dict(base,dob=dob), 'operator')
        with self.assertRaises(Invalid):
            self.s.add_patient(dict(base,last_name=' '), 'operator')
        with self.assertRaises(Invalid):
            self.s.add_patient(dict(base,synthetic=False), 'operator')

    def test_old_database_migrates_without_guessing_name_parts(self):
        path=self.path/'legacy.db'
        conn=sqlite3.connect(path)
        conn.execute('CREATE TABLE patients (id TEXT PRIMARY KEY, name TEXT NOT NULL, dob TEXT, sex TEXT, synthetic INTEGER NOT NULL)')
        conn.execute('INSERT INTO patients VALUES (?,?,?,?,?)',('SYN-OLD','Unsplit Historical Name','1980-01-01','unknown',1))
        conn.commit();conn.close()
        db=Database('sqlite:///'+str(path))
        try:
            db.migrate()
            old=db.one('SELECT * FROM patients WHERE id=?',('SYN-OLD',))
            self.assertEqual(old['name'],'Unsplit Historical Name')
            self.assertIsNone(old['first_name'])
            self.assertIsNone(old['last_name'])
        finally:
            db.close()
