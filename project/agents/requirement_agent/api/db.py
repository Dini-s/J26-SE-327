"""SQLite storage (standard library). One short-lived connection per operation, so request threads and the generation worker never share one."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, filename TEXT NOT NULL, stored_path TEXT NOT NULL, ext TEXT NOT NULL,
    size_bytes INTEGER NOT NULL, pages INTEGER, warnings TEXT NOT NULL DEFAULT '[]', extracted TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requirements (
    uid TEXT PRIMARY KEY, project_id INTEGER NOT NULL, rid TEXT NOT NULL, seq INTEGER NOT NULL, source_id INTEGER NOT NULL, source_file TEXT NOT NULL,
    page INTEGER, paragraph INTEGER, position INTEGER, clause_label TEXT, text TEXT NOT NULL, text_hash TEXT NOT NULL, occurrence INTEGER NOT NULL,
    word_count INTEGER, fr_nfr TEXT, nfr_probability REAL, is_security INTEGER, security_cue_words TEXT, ambiguity_label TEXT,
    ambiguity_probability REAL, weak_words TEXT, duplicate_group TEXT, duplicate_matches TEXT, conflict_matches TEXT,
    risk_score INTEGER, risk_level TEXT, findings TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_req_project ON requirements(project_id, seq);
CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, a_uid TEXT NOT NULL, b_uid TEXT NOT NULL, cosine REAL NOT NULL,
    kind TEXT NOT NULL, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS generation (
    uid TEXT PRIMARY KEY, state TEXT NOT NULL, message TEXT NOT NULL DEFAULT '', result TEXT, attempts INTEGER NOT NULL DEFAULT 0,
    manual_review INTEGER NOT NULL DEFAULT 0, cache_key TEXT, updated_at TEXT NOT NULL, priority INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS gen_cache (key TEXT PRIMARY KEY, result TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS gen_latency (id INTEGER PRIMARY KEY AUTOINCREMENT, backend TEXT NOT NULL, model TEXT NOT NULL, seconds REAL NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (uid TEXT PRIMARY KEY, decision TEXT NOT NULL, edited_text TEXT, note TEXT, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decision_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT NOT NULL, decision TEXT NOT NULL, edited_text TEXT, note TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, project_id INTEGER NOT NULL, stage TEXT NOT NULL, part_a_done INTEGER NOT NULL DEFAULT 0, error TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, policy TEXT NOT NULL DEFAULT 'smart');
"""

# columns added after the first version: older database files get them on start
MIGRATIONS = (
    ("generation", "priority", "INTEGER NOT NULL DEFAULT 1"),
    ("jobs", "policy", "TEXT NOT NULL DEFAULT 'smart'"),
)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as con:
            con.executescript(SCHEMA)
            for table, column, ddl in MIGRATIONS:
                if column not in [r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def one(self, sql, args=()):
        with self.connect() as con:
            row = con.execute(sql, args).fetchone()
        return dict(row) if row else None

    def all(self, sql, args=()):
        with self.connect() as con:
            return [dict(r) for r in con.execute(sql, args).fetchall()]

    def run(self, sql, args=()):
        with self.connect() as con:
            return con.execute(sql, args).lastrowid


def dumps(value):
    return json.dumps(value, ensure_ascii=False)


def loads(value, default=None):
    if value is None or value == "":
        return default
    return json.loads(value)
