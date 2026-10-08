import os
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]

class Database:
    """Small DB-API repository; same SQL contract for SQLite and PostgreSQL."""
    def __init__(self, url):
        self.lock = threading.RLock()
        self.postgres = url.startswith(('postgres://', 'postgresql://'))
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            self.conn = psycopg.connect(url, row_factory=dict_row)
        else:
            path = url.removeprefix('sqlite:///')
            if path != ':memory:':
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute('PRAGMA foreign_keys=ON')
            self.conn.execute('PRAGMA journal_mode=WAL')
        self.migrate()

    def execute(self, sql, params=()):
        if self.postgres:
            sql = sql.replace('?', '%s')
        return self.conn.execute(sql, params)

    def rows(self, sql, params=()):
        return [dict(r) for r in self.execute(sql,params).fetchall()]

    def one(self, sql, params=()):
        result = self.rows(sql, params)
        return result[0] if result else None

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                yield self
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def migrate(self):
        with self.transaction():
            for statement in (ROOT/'migrations/001_initial.sql').read_text().split(';'):
                if statement.strip():
                    self.execute(statement)
            # Add structured identity fields without splitting historical display names.
            columns = ({row['column_name'] for row in self.rows("SELECT column_name FROM information_schema.columns WHERE table_name='patients' AND table_schema=current_schema()")}
                       if self.postgres else {row['name'] for row in self.rows('PRAGMA table_info(patients)')})
            for column in ('first_name', 'last_name'):
                if column not in columns:
                    self.execute(f'ALTER TABLE patients ADD COLUMN {column} TEXT')
            if not self.postgres:
                for table in ('results','analyses','reviews','audit','outbox'):
                    for action in ('UPDATE','DELETE'):
                        self.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only table'); END")
            else:
                self.execute("CREATE OR REPLACE FUNCTION reject_event_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only table'; END $$")
                for table in ('results','analyses','reviews','audit','outbox'):
                    self.execute(f'DROP TRIGGER IF EXISTS immutable_{table} ON {table}')
                    self.execute(f'CREATE TRIGGER immutable_{table} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_event_mutation()')

    def close(self):
        self.conn.close()
