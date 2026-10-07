CREATE TABLE IF NOT EXISTS patients (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, dob TEXT, sex TEXT, synthetic INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS encounters (
 id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patients(id), label TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
 id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patients(id),
 encounter_id TEXT NOT NULL REFERENCES encounters(id), test_timestamp TEXT NOT NULL,
 ingested_at TEXT NOT NULL, source_type TEXT NOT NULL, source_identifier TEXT NOT NULL,
 source_hash TEXT NOT NULL, content TEXT NOT NULL, supersedes TEXT REFERENCES results(id),
 UNIQUE(patient_id, source_type, source_identifier), UNIQUE(supersedes)
);
CREATE INDEX IF NOT EXISTS results_patient ON results(patient_id);
CREATE TABLE IF NOT EXISTS analyses (
 id TEXT PRIMARY KEY, result_id TEXT NOT NULL REFERENCES results(id),
 created_at TEXT NOT NULL, content TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
 id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL REFERENCES analyses(id),
 created_at TEXT NOT NULL, actor TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, actor TEXT NOT NULL,
 action TEXT NOT NULL, entity_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, event_type TEXT NOT NULL, content TEXT NOT NULL
);
