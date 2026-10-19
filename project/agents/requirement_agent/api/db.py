"""SQLite storage (standard library). One short-lived connection per operation, so request threads and the generation worker never share one."""
import json
import re
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
CREATE TABLE IF NOT EXISTS publish_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, graph_project_id TEXT NOT NULL, graph_project_name TEXT NOT NULL DEFAULT '', content_hash TEXT NOT NULL, published_at TEXT NOT NULL,
    seconds REAL NOT NULL, counts TEXT NOT NULL);
-- who published or unpublished which documents, and when (internal; no endpoint returns it)
CREATE TABLE IF NOT EXISTS publish_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, action TEXT NOT NULL, scope TEXT NOT NULL, sprint_id INTEGER,
    document_ids TEXT NOT NULL, skipped TEXT NOT NULL DEFAULT '[]', at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (uid TEXT PRIMARY KEY, decision TEXT NOT NULL, edited_text TEXT, note TEXT, updated_at TEXT NOT NULL);
-- internal and append-only: a decision that was replaced or removed is copied here. No endpoint returns it and it is never published.
CREATE TABLE IF NOT EXISTS decision_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT NOT NULL, decision TEXT NOT NULL, edited_text TEXT, note TEXT, decided_at TEXT NOT NULL,
    superseded_at TEXT NOT NULL, reason TEXT NOT NULL DEFAULT 'replaced');
-- planning: phases group sprints; a sprint belongs to at most one phase. Names are unique per project, ignoring case.
CREATE TABLE IF NOT EXISTS phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, name TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS idx_phases_name ON phases(project_id, name COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS sprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, phase_id INTEGER, name TEXT NOT NULL, start_date TEXT, end_date TEXT, goal TEXT,
    origin TEXT NOT NULL DEFAULT 'manual', confirmed INTEGER NOT NULL DEFAULT 1, external_id TEXT, position INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sprints_name ON sprints(project_id, name COLLATE NOCASE);
-- Jira (read-only import). The tokens are in this file only and are never returned, logged, exported or published; states are stored as hashes.
CREATE TABLE IF NOT EXISTS jira_connections (
    project_id INTEGER PRIMARY KEY, cloud_id TEXT NOT NULL, site_name TEXT NOT NULL DEFAULT '', site_url TEXT NOT NULL DEFAULT '', access_token TEXT NOT NULL DEFAULT '',
    refresh_token TEXT NOT NULL DEFAULT '', expires_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'connected', connected_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jira_states (state_hash TEXT PRIMARY KEY, project_id INTEGER NOT NULL, created_at TEXT NOT NULL, used INTEGER NOT NULL DEFAULT 0);
-- the issue map: one row per imported issue, the text the requirement is made from, and where it sits
CREATE TABLE IF NOT EXISTS jira_issues (
    project_id INTEGER NOT NULL, issue_key TEXT NOT NULL, jira_project TEXT NOT NULL, source_id INTEGER NOT NULL, issue_type TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL, text_hash TEXT NOT NULL, sprint_id INTEGER, url TEXT NOT NULL DEFAULT '', scope TEXT NOT NULL DEFAULT '', missing INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL, PRIMARY KEY (project_id, issue_key));
CREATE INDEX IF NOT EXISTS idx_jira_issues_source ON jira_issues(source_id);
CREATE TABLE IF NOT EXISTS jira_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, jira_project TEXT NOT NULL, board_id INTEGER, at TEXT NOT NULL, counts TEXT NOT NULL, missing_keys TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, project_id INTEGER NOT NULL, stage TEXT NOT NULL, part_a_done INTEGER NOT NULL DEFAULT 0, error TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, policy TEXT NOT NULL DEFAULT 'smart');
"""

# columns added after the first version: older database files get them on start
MIGRATIONS = (
    ("generation", "priority", "INTEGER NOT NULL DEFAULT 1"),
    ("jobs", "policy", "TEXT NOT NULL DEFAULT 'smart'"),
    ("gen_latency", "target", "TEXT NOT NULL DEFAULT 'device'"),
    ("gen_latency", "finished", "REAL"),
    ("sources", "source_type", "TEXT NOT NULL DEFAULT 'srs'"),
    ("sources", "sha256", "TEXT"),
    ("projects", "project_key", "TEXT"),
    ("projects", "archived", "INTEGER NOT NULL DEFAULT 0"),
    ("projects", "current_sprint_id", "INTEGER"),
    ("sources", "default_sprint_id", "INTEGER"),
    ("sources", "analysis_state", "TEXT NOT NULL DEFAULT 'not_analyzed'"),
    ("sources", "analyzed_at", "TEXT"),
    ("sources", "analyzed_hash", "TEXT"),
    ("requirements", "sprint_id", "INTEGER"),  # override of the document's default sprint; null = follow the document
    ("sources", "published", "INTEGER NOT NULL DEFAULT 0"),  # shared with the other components only when the user publishes the document
    ("sources", "published_at", "TEXT"),
    ("jira_connections", "scope", "TEXT NOT NULL DEFAULT ''"),  # the permissions the connection was made with; empty = made before they were recorded
)

DEFAULT_SPRINT_NAME = "Sprint 1"

DEFAULT_PROJECT_KEY = "demo-project"


def slugify(name, fallback="project"):
    """Lower-case letters, digits and single hyphens (at most 60 characters); this is also a valid Neo4j project id."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60].strip("-")
    return slug or fallback


def unique_key(taken, name, fallback="project"):
    base = slugify(name, fallback)
    key, n = base, 1
    while key in taken:
        n += 1
        key = f"{base[:55]}-{n}"
    return key


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_planning(con, pid):
    """Every project has at least one sprint, one of them is current, and every document has a default sprint. Safe to run again at any time."""
    first = con.execute("SELECT id FROM sprints WHERE project_id=? ORDER BY position, id LIMIT 1", (pid,)).fetchone()
    if first is None:
        first = {"id": con.execute("INSERT INTO sprints (project_id, name, origin, confirmed, position, created_at) VALUES (?,?,?,?,?,?)",
                                   (pid, DEFAULT_SPRINT_NAME, "manual", 1, 1, now())).lastrowid}
    con.execute("UPDATE projects SET current_sprint_id=? WHERE id=? AND (current_sprint_id IS NULL OR current_sprint_id NOT IN (SELECT id FROM sprints WHERE project_id=?))",
                (first["id"], pid, pid))
    current = con.execute("SELECT current_sprint_id c FROM projects WHERE id=?", (pid,)).fetchone()["c"]
    con.execute("UPDATE sources SET default_sprint_id=? WHERE project_id=? AND (default_sprint_id IS NULL OR default_sprint_id NOT IN (SELECT id FROM sprints WHERE project_id=?))",
                (current, pid, pid))
    return current


class Database:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as con:
            con.execute("PRAGMA journal_mode=WAL")  # the worker pool and the request threads write at the same time: readers never block the writer
            con.executescript(SCHEMA)
            columns = [r["name"] for r in con.execute("PRAGMA table_info(sources)").fetchall()]
            had_state, had_published = "analysis_state" in columns, "published" in columns
            for table, column, ddl in MIGRATIONS:
                if column not in [r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            self._backfill_project_keys(con)
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_key ON projects(project_key)")
            self._migrate_decision_history(con)
            if not had_state:
                self._backfill_analysis_state(con)
            if not had_published:
                self._backfill_published(con)
            con.execute("UPDATE sources SET analysis_state='failed' WHERE analysis_state='analyzing'")  # the process stopped in the middle of an analysis
            for p in con.execute("SELECT id FROM projects").fetchall():
                ensure_planning(con, p["id"])

    @staticmethod
    def _backfill_analysis_state(con):
        """Sources of files from before the analysis state existed: analysed when they have requirements or an analysis finished after they were uploaded."""
        con.execute(
            "UPDATE sources SET analysis_state='analyzed', analyzed_hash=sha256, "
            "analyzed_at=COALESCE((SELECT MAX(r.created_at) FROM requirements r WHERE r.source_id=sources.id), "
            "(SELECT MAX(j.updated_at) FROM jobs j WHERE j.project_id=sources.project_id AND j.part_a_done=1)) "
            "WHERE id IN (SELECT DISTINCT source_id FROM requirements) OR EXISTS "
            "(SELECT 1 FROM jobs j WHERE j.project_id=sources.project_id AND j.part_a_done=1 AND j.updated_at>=sources.created_at)")

    @staticmethod
    def _backfill_published(con):
        """Files from before publishing was manual: the analysed documents of a project that was already synced to the graph stay published, so nothing disappears."""
        con.execute(
            "UPDATE sources SET published=1, published_at=(SELECT MAX(l.published_at) FROM publish_log l WHERE l.project_id=sources.project_id) "
            "WHERE analysis_state='analyzed' AND project_id IN (SELECT DISTINCT project_id FROM publish_log)")

    @staticmethod
    def _backfill_project_keys(con):
        """Every project gets a key once: project 1 is "demo-project", the others a slug of their name. Keys never change afterwards."""
        rows = con.execute("SELECT id, name, project_key FROM projects ORDER BY id").fetchall()
        taken = {r["project_key"] for r in rows if r["project_key"]}
        for r in rows:
            if r["project_key"]:
                continue
            key = unique_key(taken, DEFAULT_PROJECT_KEY if r["id"] == 1 else r["name"], f"project-{r['id']}")
            taken.add(key)
            con.execute("UPDATE projects SET project_key=? WHERE id=?", (key, r["id"]))

    @staticmethod
    def _migrate_decision_history(con):
        """Older files kept every decision in an append-only decision_history table. Now there is one current decision per requirement (table decisions);
        the older rows move to decision_audit and the old table is dropped. The newest history row of a requirement is its current decision."""
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='decision_history'").fetchone():
            return
        stamp = now()
        # a requirement with history but no current decision (cannot happen in files this API wrote) keeps its newest history row as the current one
        con.execute("INSERT INTO decisions (uid, decision, edited_text, note, updated_at) SELECT h.uid, h.decision, h.edited_text, h.note, h.created_at "
                    "FROM decision_history h WHERE h.id=(SELECT MAX(id) FROM decision_history WHERE uid=h.uid) AND h.uid NOT IN (SELECT uid FROM decisions)")
        con.execute("INSERT INTO decision_audit (uid, decision, edited_text, note, decided_at, superseded_at, reason) "
                    "SELECT h.uid, h.decision, h.edited_text, h.note, h.created_at, ?, 'migrated' FROM decision_history h "
                    "WHERE h.id<(SELECT MAX(id) FROM decision_history WHERE uid=h.uid) ORDER BY h.id", (stamp,))
        con.execute("DROP TABLE decision_history")

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)  # waits up to 30 s for a lock held by another thread
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def ensure_planning(self, pid):
        with self.connect() as con:
            return ensure_planning(con, pid)

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
