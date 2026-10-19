"""Component 1: publishing the clarified requirements to Neo4j.

No real Neo4j is used. A fake driver records every statement and applies it to a tiny in-memory graph (it understands exactly the statements
neo4j_store builds), so idempotency and soft-deactivation are checked on a graph, not only on strings. The one optional integration test at the end runs
only with C1_NEO4J_TEST=1 and a Neo4j URI in the environment, and only touches nodes with project_id "c1-test-project".
"""
import hashlib
import json
import logging
import os
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from agents.requirement_agent.api import neo4j_config, neo4j_store
from agents.requirement_agent.api import neo4j_schema as S
from agents.requirement_agent.api.db import Database, dumps, now
from agents.requirement_agent.api.errors import ApiError
from agents.requirement_agent.api.neo4j_config import Neo4jConfig
from agents.requirement_agent.api.neo4j_store import Neo4jStore
from tests.test_c1_api import make_client  # noqa: F401  (fixture)

PASSWORD = "pw-SECRET-xyz-987"
URI = "neo4j://db.internal.example:7687"
NEO4J_ENV = ("C1_NEO4J_URI", "C1_NEO4J_USER", "C1_NEO4J_PASSWORD", "C1_NEO4J_DATABASE", "NEO4J_URI", "NEO4J_USERNAME", "NEO4J_USER", "NEO4J_PASSWORD",
             "NEO4J_DATABASE", "C1_PROJECT_ID", "C1_PROJECT_NAME")


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """The real .env and the real environment are never consulted by these tests."""
    monkeypatch.setattr(neo4j_config, "ENV_FILES", [])
    for k in NEO4J_ENV:
        monkeypatch.delenv(k, raising=False)


CFG = Neo4jConfig(uri=URI, user="neo4j", password=PASSWORD, database="neo4j")


# ------------------------------------------------------------------------------------------------------------------ fake driver and graph
class Graph:
    """Applies the statements of neo4j_store to dictionaries: MERGE by id, SET properties, soft-deactivate."""

    def __init__(self):
        self.nodes, self.rels, self.dups, self.statements = {}, set(), {}, []
        self.includes = {}  # (sprint id, source id) -> {"requirements", "active"}

    def upsert(self, label, key, props, replace=True):
        node = self.nodes.setdefault((label, key), {})
        node.update(props)
        return node

    def run(self, q, p):
        L, R = S.Label, S.Rel
        self.statements.append(q)
        if q == neo4j_store.Q_PROJECT:
            self.upsert(L.PROJECT, p["project_id"], p["props"])  # SET p += props: the name follows the workspace
        elif q == neo4j_store.Q_SOURCE:
            self.upsert(L.SOURCE, p["source_id"], p["props"])
            self.rels.add((R.HAS_SOURCE, p["project_id"], p["source_id"]))
        elif q == neo4j_store.Q_REQUIREMENTS:
            for row in p["rows"]:
                self.upsert(L.REQUIREMENT, row["id"], row["props"])
                self.rels.add((R.CONTAINS, p["source_id"], row["id"]))
        elif q == neo4j_store.Q_ISSUES:
            for row in p["rows"]:
                self.upsert(L.ISSUE, row["id"], row["props"])
                self.rels.add((R.HAS_ISSUE, row["req_id"], row["id"]))
        elif q == neo4j_store.Q_DRAFTS:
            for row in p["rows"]:
                self.upsert(L.DRAFT, row["id"], row["props"])
                self.rels.add((R.HAS_DRAFT, row["req_id"], row["id"]))
        elif q == neo4j_store.Q_DUPLICATES:
            for row in p["rows"]:
                self.dups[row["id"]] = {"a": row["a"], "b": row["b"], S.DuplicateP.SCORE: row["score"], "active": True, "project_id": p["project_id"]}
        elif q == neo4j_store.Q_INCLUDES:
            for row in p["rows"]:
                self.includes[(row["sprint_id"], row["source_id"])] = {"requirements": row["requirements"], "active": True}
        else:
            held = lambda key: any(key == h or key.startswith(h + ":") for h in p.get("held", []))  # noqa: E731
            for label, query in neo4j_store.Q_DEACTIVATE.items():
                if q == query:
                    n = 0
                    if label == R.INCLUDES_SOURCE:
                        for (sprint, source), e in self.includes.items():
                            if f"{sprint}|{source}" not in p["ids"] and source not in p["held"] and e["active"]:
                                e.update(active=False, requirements=0)
                                n += 1
                    elif label == R.DUPLICATE_OF:
                        for key, d in self.dups.items():
                            if key not in p["ids"] and d.get("active", True) and not any(key.startswith(h + ":") or ("|" + h + ":") in key for h in p["held"]):
                                d["active"], n = False, n + 1
                    else:
                        for (lab, key), props in self.nodes.items():
                            if lab == label and props.get("project_id") == p["project_id"] and key not in p["ids"] and props.get("active", True) and not held(key):
                                props["active"], n = False, n + 1
                    return Result({"n": n})
        return Result(None)


class Result:
    def __init__(self, record):
        self.record = record

    def single(self):
        return self.record

    def consume(self):
        return None


class Tx:
    def __init__(self, graph, log):
        self.graph, self.log = graph, log

    def run(self, query, **params):
        self.log.append(("tx", query, params))
        return self.graph.run(query, params)


class Session:
    def __init__(self, driver, database):
        self.driver, self.database = driver, database

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query, **params):
        self.driver.log.append(("auto", query, params))
        return Result({"one": 1}) if query.startswith("RETURN 1") else Result(None)

    def execute_write(self, fn, *args):
        if self.driver.fail_write is not None:
            raise self.driver.fail_write
        self.driver.transactions += 1
        return fn(Tx(self.driver.graph, self.driver.log), *args)


class Driver:
    def __init__(self, graph=None, fail_write=None):
        self.graph = graph if graph is not None else Graph()
        self.log, self.transactions, self.closed, self.fail_write = [], 0, 0, fail_write

    def verify_connectivity(self):
        return None

    def get_server_info(self):
        return SimpleNamespace(agent="Neo4j/2026.09.0", address=("db.internal.example", 7687))

    def session(self, database=None):
        return Session(self, database)

    def close(self):
        self.closed += 1


class ServiceUnavailable(Exception):  # same class name as the driver's, so translate() recognises it without the driver installed
    pass


class AuthError(Exception):
    pass


def store_for(db, graph=None, cfg=CFG, **kw):
    """The project (key "demo-project", name "Core Banking Platform") is the one seeded in the workspace: a store has no other source for it."""
    driver = Driver(graph, **kw)
    store = Neo4jStore(db, config_loader=lambda: cfg, driver_factory=lambda c: driver)
    return store, driver


# ------------------------------------------------------------------------------------------------------------------ workspace data
def seed(db, project=True):
    """Two sources, four requirements (one duplicate pair, decisions, drafts), enough rows to build a bundle."""
    if project:
        db.run("INSERT INTO projects (name, created_at) VALUES ('Core Banking Platform', ?)", (now(),))
    for sid, fn, st in ((1, "srs.txt", "srs"), (2, "brd.txt", "brd")):
        db.run("INSERT INTO sources (id, project_id, filename, stored_path, ext, size_bytes, pages, warnings, extracted, created_at, source_type, sha256, analysis_state) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (sid, 1, fn, f"/nowhere/{fn}", ".txt", 10, None, "[]", "{}", "2026-10-01T00:00:00+00:00", st, hashlib.sha256(fn.encode()).hexdigest(), "analyzed"))

    def req(seq, source, text, fr="FR", defect=False, weak=(), security=False, cues=(), risk=("NONE", 0), dups=()):
        db.run("INSERT INTO requirements (uid, project_id, rid, seq, source_id, source_file, text, text_hash, occurrence, fr_nfr, nfr_probability, is_security, security_cue_words,"
               " ambiguity_label, ambiguity_probability, weak_words, duplicate_group, duplicate_matches, conflict_matches, risk_score, risk_level, findings, created_at)"
               " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (f"p1-REQ-{seq:03d}", 1, f"REQ-{seq:03d}", seq, source, "x", text, f"h{seq}", 1, fr, 0.5, int(security), dumps(list(cues)),
                "defect" if defect else "clear", 0.91 if defect else 0.1, dumps(list(weak)), "", dumps(list(dups)), "[]", risk[1], risk[0], "[]", now()))

    req(1, 1, "The system shall respond quickly to login requests.", fr="NFR", defect=True, weak=["quickly"], security=True, cues=["login"], risk=("HIGH", 4),
        dups=[{"id": "REQ-002", "uid": "p1-REQ-002", "similarity": 0.93}])
    req(2, 1, "The system shall respond quickly to every login request.", dups=[{"id": "REQ-001", "uid": "p1-REQ-001", "similarity": 0.93}])
    req(3, 1, "The report shall be easy to read.", risk=("LOW", 1))
    req(4, 2, "The bank shall keep audit logs for seven years.")

    def gen(uid, state, result=None):
        db.run("INSERT INTO generation (uid, state, message, result, attempts, manual_review, updated_at) VALUES (?,?,?,?,?,?,?)",
               (uid, state, "", dumps(result) if result else None, 1, 0, now()))

    gen("p1-REQ-001", "done", {"status": "ok", "user_story": "As a user I want fast login.", "technical_task": "Tune the login path.",
                               "acceptance_criteria": ["Login takes under 2 s.", "Failures are logged."], "rationale": "Role assumed.", "clarification_questions": [],
                               "backend": "ollama", "model": "c1-req", "generated_on": "cloud", "endpoint_host": "gpu.example.com", "generated_from": "original"})
    gen("p1-REQ-003", "needs_clarification", {"status": "needs_clarification", "user_story": "", "technical_task": "", "acceptance_criteria": [], "rationale": "Unclear.",
                                              "clarification_questions": ["Which readers?", "Which format?"], "backend": "ollama", "model": "c1-req",
                                              "generated_on": "device", "endpoint_host": None, "generated_from": "original"})
    gen("p1-REQ-004", "failed")
    db.run("INSERT INTO decisions (uid, decision, edited_text, note, updated_at) VALUES ('p1-REQ-001','accepted',NULL,NULL,'2026-10-02T00:00:00+00:00')")
    db.run("INSERT INTO decisions (uid, decision, edited_text, note, updated_at) VALUES ('p1-REQ-003','edited','The report shall be readable at 100% zoom.',NULL,'2026-10-02T00:00:00+00:00')")
    db.run("INSERT INTO decisions (uid, decision, edited_text, note, updated_at) VALUES ('p1-REQ-004','rejected',NULL,'out of scope','2026-10-02T00:00:00+00:00')")


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    seed(d)
    return d


def node(graph, label, key):
    return graph.nodes[(label, key)]


# ------------------------------------------------------------------------------------------------------------------ config
def test_c1_names_win_over_the_shared_names_and_database_defaults_to_neo4j():
    env = {"NEO4J_URI": "bolt://shared:7687", "NEO4J_USERNAME": "shared", "NEO4J_PASSWORD": "p-shared", "C1_NEO4J_URI": "bolt://own:7687", "C1_NEO4J_PASSWORD": "p-own"}
    c = neo4j_config.load_config(env, [])
    assert (c.uri, c.user, c.password, c.database) == ("bolt://own:7687", "shared", "p-own", "neo4j")
    assert c.configured and c.host == "own"
    assert neo4j_config.load_config({"NEO4J_DATABASE": "other", "NEO4J_URI": "x://h", "NEO4J_USER": "u", "NEO4J_PASSWORD": "p"}, []).database == "other"
    assert not neo4j_config.load_config({}, []).configured


def test_env_file_is_used_only_for_missing_keys_and_only_for_allowed_keys(tmp_path):
    f = tmp_path / ".env"
    f.write_text('# comment\nNEO4J_URI="neo4j://file-host:7687"\nexport NEO4J_USERNAME=fileuser\nNEO4J_PASSWORD=pass#with-hash\nNEO4J_DATABASE=filedb # trailing\n', encoding="utf-8")
    c = neo4j_config.load_config({"NEO4J_USERNAME": "envuser"}, [f])
    assert (c.uri, c.user, c.password, c.database) == ("neo4j://file-host:7687", "envuser", "pass#with-hash", "filedb")  # the environment wins, key by key
    assert neo4j_config.load_config({}, [tmp_path / "missing.env"]).configured is False


def test_env_file_never_yields_llm_or_other_values(tmp_path, monkeypatch):
    llm = "sk-llm-SECRET-ZZZ-111"
    f = tmp_path / ".env"
    f.write_text(f"LLM_API_KEY={llm}\nLLM_MODEL=secret-model-777\nREDIS_URL=redis://:redis-pass-555@h:6379\nEMBEDDING_MODEL=emb-888\n"
                 f"NEO4J_URI=neo4j://h:7687\nNEO4J_USERNAME=u\nNEO4J_PASSWORD={PASSWORD}\nC1_PROJECT_ID=pp\n", encoding="utf-8")
    before = dict(os.environ)
    read = neo4j_config.read_env_file(f)
    assert set(read) == {"NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"}  # the old project-stub keys are no longer read either
    assert set(read) <= neo4j_config.ALLOWED_KEYS
    # the environment may hold them too: they are not looked at either
    env = {"LLM_API_KEY": llm, "LLM_BASE_URL": "http://llm", "REDIS_URL": "redis://x", "NEO4J_URI": "neo4j://h:7687"}
    cfg = neo4j_config.load_config(env, [f])
    everything = repr((read, cfg, neo4j_config._merged(env, [f])))
    for secret in (llm, "secret-model-777", "redis-pass-555", "emb-888", "http://llm", "redis://x"):
        assert secret not in everything
    assert not any(k.startswith(("LLM_", "REDIS_", "EMBEDDING_")) for k in neo4j_config._merged(env, [f]))
    assert dict(os.environ) == before  # nothing was loaded into the process environment
    assert not any(k.startswith("LLM_") for k in os.environ if k not in before)


def test_password_is_not_in_repr_or_str():
    assert PASSWORD not in repr(CFG) and PASSWORD not in str(CFG) and URI not in repr(CFG)
    assert CFG.host == "db.internal.example"


# ------------------------------------------------------------------------------------------------------------------ bundle
def test_ids_follow_the_documented_rule(db):
    b = neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform")
    assert [s.source_id for s in b.sources] == ["demo-project:src1", "demo-project:src2"]
    assert [r["id"] for r in b.sources[0].requirements] == ["demo-project:src1:REQ-001", "demo-project:src1:REQ-002", "demo-project:src1:REQ-003"]
    assert neo4j_store.requirement_graph_id("p", 7, "REQ-012") == "p:src7:REQ-012"


def test_every_node_carries_project_id_produced_by_and_schema_version(db):
    b = neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform")
    props = [b.project_props] + [s.props for s in b.sources] + [x["props"] for s in b.sources for x in s.requirements + s.issues + s.drafts]
    assert len(props) > 10
    for p in props:
        assert p[S.Common.PROJECT_ID] == "demo-project" and p[S.Common.PRODUCED_BY] == "c1" and p[S.Common.SCHEMA_VERSION] == S.SCHEMA_VERSION


def test_sources_carry_type_and_hash_but_not_file_bytes(db):
    b = neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform")
    s1, s2 = b.sources
    assert (s1.props[S.SourceP.SOURCE_TYPE], s2.props[S.SourceP.SOURCE_TYPE]) == ("srs", "brd")
    assert s1.props[S.SourceP.SHA256] == hashlib.sha256(b"srs.txt").hexdigest()
    assert s1.props[S.SourceP.FILENAME] == "srs.txt" and s1.props[S.SourceP.ACTIVE] is True
    assert set(s1.props) == {S.Common.PROJECT_ID, S.Common.PRODUCED_BY, S.Common.SCHEMA_VERSION, S.SourceP.FILENAME, S.SourceP.SOURCE_TYPE, S.SourceP.SHA256,
                             S.SourceP.UPLOADED_AT, S.SourceP.ACTIVE}


def test_requirements_carry_the_human_decision_and_final_text(db):
    reqs = {r["id"].rsplit(":", 1)[1]: r["props"] for s in neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform").sources for r in s.requirements}
    assert reqs["REQ-001"][S.RequirementP.STATUS] == "accepted" and reqs["REQ-001"][S.RequirementP.FINAL_TEXT] == reqs["REQ-001"][S.RequirementP.TEXT]
    assert reqs["REQ-002"][S.RequirementP.STATUS] == "pending"
    assert reqs["REQ-003"][S.RequirementP.STATUS] == "edited" and reqs["REQ-003"][S.RequirementP.FINAL_TEXT] == "The report shall be readable at 100% zoom."
    assert reqs["REQ-003"][S.RequirementP.TEXT] == "The report shall be easy to read."  # the original stays
    assert reqs["REQ-004"][S.RequirementP.STATUS] == "rejected"
    assert reqs["REQ-001"][S.RequirementP.KIND] == "NFR" and reqs["REQ-002"][S.RequirementP.KIND] == "FR"
    assert reqs["REQ-001"][S.RequirementP.SECURITY_FLAG] is True and reqs["REQ-002"][S.RequirementP.SECURITY_FLAG] is False
    assert all(r[S.RequirementP.ACTIVE] is True for r in reqs.values())
    assert all(r[S.RequirementP.STATUS] in S.STATUSES for r in reqs.values())


def test_payload_json_is_the_lossless_v1_record_without_secrets(db):
    b = neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform")
    p = json.loads(b.sources[0].requirements[0]["props"][S.RequirementP.PAYLOAD_JSON])
    assert p["schema_version"] == "c1.clarified_requirements.v1" and p["project"] == {"id": "demo-project", "name": "Core Banking Platform"}
    rec = p["requirement"]
    assert rec["id"] == "REQ-001" and rec["original_text"].startswith("The system shall respond quickly") and rec["decision"]["status"] == "accepted"
    assert rec["draft"]["user_story"] == "As a user I want fast login." and rec["draft"]["acceptance_criteria"] == ["Login takes under 2 s.", "Failures are logged."]
    assert rec["draft"]["provenance"] == {"model": "c1-req", "backend": "ollama", "generated_on": "cloud", "endpoint_host": "gpu.example.com"}
    assert rec["quality"]["weak_words"] == ["quickly"] and rec["quality"]["security_related"] is True
    assert rec["source"]["source_id"] == "demo-project:src1" and rec["source"]["source_type"] == "srs"
    blob = json.dumps(p)
    assert "http" not in blob and "api_key" not in blob.lower() and "/v1" not in blob


def test_properties_are_flat_never_nested_maps(db):
    b = neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform")
    allp = [b.project_props] + [s.props for s in b.sources] + [x["props"] for s in b.sources for x in s.requirements + s.issues + s.drafts]
    for p in allp:
        for k, v in p.items():
            assert v is None or isinstance(v, (str, int, float, bool)) or (isinstance(v, list) and all(isinstance(i, str) for i in v)), (k, v)


def test_issues_cover_part_a_rules_security_risk_and_the_ai(db):
    issues = [i for s in neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform").sources for i in s.issues]
    by = {(i["req_id"].rsplit(":", 1)[1], i["props"][S.IssueP.TYPE], i["props"][S.IssueP.RAISED_BY]) for i in issues}
    assert ("REQ-001", "ambiguity", "part_a") in by and ("REQ-001", "security", "part_a") in by and ("REQ-001", "risk", "rule") in by
    assert ("REQ-001", "vague", "rule") in by  # "quickly"
    assert ("REQ-003", "vague", "rule") in by and ("REQ-003", "risk", "rule") in by  # "easy"
    assert ("REQ-003", "ambiguity", "ai") in by  # the model asked for clarification
    assert ("REQ-004", "risk", "rule") not in by  # risk NONE is not an issue
    assert all(i["props"][S.IssueP.TYPE] in S.ISSUE_TYPES and i["props"][S.IssueP.RAISED_BY] in S.RAISED_BY for i in issues)
    assert len({i["id"] for i in issues}) == len(issues)
    ai = next(i for i in issues if i["props"][S.IssueP.RAISED_BY] == "ai")
    assert "Which readers?" in ai["props"][S.IssueP.DETAIL]


def test_task_drafts_carry_provenance_and_native_string_lists(db):
    drafts = {d["req_id"].rsplit(":", 1)[1]: d["props"] for s in neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform").sources for d in s.drafts}
    assert set(drafts) == {"REQ-001", "REQ-003"}  # failed and not requested have no draft
    d = drafts["REQ-001"]
    assert d[S.DraftP.ACCEPTANCE_CRITERIA] == ["Login takes under 2 s.", "Failures are logged."]
    assert (d[S.DraftP.GENERATED_BY], d[S.DraftP.GENERATED_ON], d[S.DraftP.ENDPOINT_HOST], d[S.DraftP.NEEDS_CLARIFICATION]) == ("c1-req", "cloud", "gpu.example.com", False)
    n = drafts["REQ-003"]
    assert n[S.DraftP.NEEDS_CLARIFICATION] is True and n[S.DraftP.GENERATED_ON] == "device" and n[S.DraftP.ENDPOINT_HOST] is None
    assert n[S.DraftP.CLARIFICATION_QUESTIONS] == ["Which readers?", "Which format?"]


def test_duplicate_link_is_written_once_from_the_later_requirement_to_the_earlier(db):
    b = neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform")
    assert b.duplicates == [{"id": "demo-project:src1:REQ-002|demo-project:src1:REQ-001", "a": "demo-project:src1:REQ-002", "b": "demo-project:src1:REQ-001", "score": 0.93}]


def test_legacy_source_rows_get_their_hash_from_the_file(tmp_path):
    d = Database(tmp_path / "old.db")
    d.run("INSERT INTO projects (name, created_at) VALUES ('P', ?)", (now(),))
    f = tmp_path / "up.txt"
    f.write_bytes(b"hello")
    d.run("INSERT INTO sources (project_id, filename, stored_path, ext, size_bytes, warnings, extracted, created_at, analysis_state) VALUES (1,'up.txt',?, '.txt', 5, '[]', '{}', 't', 'analyzed')", (str(f),))
    b = neo4j_store.build_bundle(d, 1, "p", "P")
    assert b.sources[0].props[S.SourceP.SHA256] == hashlib.sha256(b"hello").hexdigest() and b.sources[0].props[S.SourceP.SOURCE_TYPE] == "srs"
    assert d.one("SELECT sha256 FROM sources")["sha256"] == hashlib.sha256(b"hello").hexdigest()  # stored once


def test_old_database_files_get_source_type_default(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE sources (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, filename TEXT NOT NULL, stored_path TEXT NOT NULL,"
                      " ext TEXT NOT NULL, size_bytes INTEGER NOT NULL, pages INTEGER, warnings TEXT NOT NULL DEFAULT '[]', extracted TEXT NOT NULL, created_at TEXT NOT NULL);"
                      "INSERT INTO sources (project_id, filename, stored_path, ext, size_bytes, extracted, created_at) VALUES (1,'a.txt','p','.txt',1,'{}','t');")
    con.commit()
    con.close()
    d = Database(path)
    assert d.one("SELECT source_type, sha256 FROM sources") == {"source_type": "srs", "sha256": None}


# ------------------------------------------------------------------------------------------------------------------ publish
def test_publish_sends_one_transaction_per_source_then_a_final_one_and_returns_counts(db):
    store, driver = store_for(db)
    out = store.publish(1)
    assert driver.transactions == 3  # two sources + duplicates/deactivation
    assert out["counts"] == {"Project": 1, "SourceDocument": 2, "Requirement": 4, "Issue": 8, "TaskDraft": 2, "DUPLICATE_OF": 1, "Sprint": 1, "PLANNED_IN": 4, "INCLUDES_SOURCE": 2}
    assert out["deactivated"] == {"SourceDocument": 0, "Requirement": 0, "Issue": 0, "TaskDraft": 0, "DUPLICATE_OF": 0, "Sprint": 0, "INCLUDES_SOURCE": 0}
    assert out["project_id"] == "demo-project" and out["seconds"] >= 0 and len(out["content_hash"]) == 64
    assert driver.closed == 1
    auto = [q for kind, q, _ in driver.log if kind == "auto"]
    assert auto[0].startswith("CREATE CONSTRAINT") and sum(q.startswith("CREATE CONSTRAINT") for q in auto) == 6 and sum(q.startswith("CREATE INDEX") for q in auto) == 3
    assert all("IF NOT EXISTS" in q for q in auto)
    assert all(q.count("UNWIND") == 1 for q in driver.graph.statements if q in (neo4j_store.Q_REQUIREMENTS, neo4j_store.Q_ISSUES, neo4j_store.Q_DRAFTS))
    g = driver.graph
    assert ("HAS_SOURCE", "demo-project", "demo-project:src1") in g.rels and ("CONTAINS", "demo-project:src1", "demo-project:src1:REQ-001") in g.rels
    assert ("HAS_ISSUE", "demo-project:src1:REQ-001", "demo-project:src1:REQ-001:risk:rule") in g.rels and ("HAS_DRAFT", "demo-project:src1:REQ-001", "demo-project:src1:REQ-001:draft") in g.rels
    assert node(g, "Requirement", "demo-project:src1:REQ-001")[S.RequirementP.PUBLISHED_AT] == out["published_at"]


def test_queries_merge_by_id_and_nothing_is_ever_deleted(db):
    store, driver = store_for(db)
    store.publish(1)
    for q in driver.graph.statements:
        assert "DELETE" not in q.upper() and "REMOVE" not in q.upper()
    for q in (neo4j_store.Q_PROJECT, neo4j_store.Q_SOURCE, neo4j_store.Q_REQUIREMENTS, neo4j_store.Q_ISSUES, neo4j_store.Q_DRAFTS, neo4j_store.Q_DUPLICATES):
        assert "MERGE" in q
    assert "CREATE (" not in " ".join(driver.graph.statements)


def test_publishing_twice_creates_no_duplicates_and_sends_the_same_data(db):
    graph = Graph()
    store, driver = store_for(db, graph)
    first = store.publish(1)
    snapshot = json.dumps({"nodes": {f"{k}": v for k, v in graph.nodes.items()}, "rels": sorted(graph.rels), "dups": graph.dups}, sort_keys=True, default=str)
    n_nodes, n_rels = len(graph.nodes), len(graph.rels)
    second = store.publish(1)
    assert (len(graph.nodes), len(graph.rels)) == (n_nodes, n_rels)
    again = json.dumps({"nodes": {f"{k}": v for k, v in graph.nodes.items()}, "rels": sorted(graph.rels), "dups": graph.dups}, sort_keys=True, default=str)
    strip = lambda s: json.loads(s.replace(first["published_at"], "T1").replace(second["published_at"], "T1"))  # noqa: E731
    assert strip(snapshot) == strip(again)
    assert first["content_hash"] == second["content_hash"]


def test_removed_requirements_and_sources_become_inactive_but_stay_in_the_graph(db):
    graph = Graph()
    store, _ = store_for(db, graph)
    store.publish(1)
    total = len(graph.nodes)
    # the user deletes source 2 (with its requirement) and re-analysis drops REQ-003
    db.run("DELETE FROM requirements WHERE uid IN ('p1-REQ-004','p1-REQ-003')")
    db.run("DELETE FROM generation WHERE uid IN ('p1-REQ-004','p1-REQ-003')")
    db.run("DELETE FROM sources WHERE id=2")
    out = store.publish(1)
    assert len(graph.nodes) == total  # nothing deleted
    assert node(graph, "SourceDocument", "demo-project:src2")["active"] is False and node(graph, "SourceDocument", "demo-project:src1")["active"] is True
    assert node(graph, "Requirement", "demo-project:src2:REQ-004")["active"] is False
    assert node(graph, "Requirement", "demo-project:src1:REQ-003")["active"] is False and node(graph, "Requirement", "demo-project:src1:REQ-001")["active"] is True
    assert node(graph, "TaskDraft", "demo-project:src1:REQ-003:draft")["active"] is False and node(graph, "TaskDraft", "demo-project:src1:REQ-001:draft")["active"] is True
    assert out["deactivated"]["SourceDocument"] == 1 and out["deactivated"]["Requirement"] == 2 and out["deactivated"]["TaskDraft"] == 1 and out["deactivated"]["Issue"] >= 3
    again = store.publish(1)
    assert again["deactivated"] == {"SourceDocument": 0, "Requirement": 0, "Issue": 0, "TaskDraft": 0, "DUPLICATE_OF": 0, "Sprint": 0, "INCLUDES_SOURCE": 0}  # already inactive: not counted twice


def test_a_removed_duplicate_link_is_deactivated_and_a_returning_item_is_active_again(db):
    graph = Graph()
    store, _ = store_for(db, graph)
    store.publish(1)
    key = "demo-project:src1:REQ-002|demo-project:src1:REQ-001"
    assert graph.dups[key]["active"] is True
    saved = db.one("SELECT duplicate_matches FROM requirements WHERE uid='p1-REQ-002'")["duplicate_matches"]
    db.run("UPDATE requirements SET duplicate_matches='[]' WHERE uid='p1-REQ-002'")
    assert store.publish(1)["deactivated"]["DUPLICATE_OF"] == 1 and graph.dups[key]["active"] is False
    db.run("UPDATE requirements SET duplicate_matches=? WHERE uid='p1-REQ-002'", (saved,))
    store.publish(1)
    assert graph.dups[key]["active"] is True


def test_status_out_of_date_follows_the_content_hash(db):
    store, _ = store_for(db)
    st = store.status(1)
    assert (st["configured"], st["reachable"], st["out_of_date"], st["last_published_at"], st["last_counts"]) == (True, True, True, None, None)
    assert st["server_version"] == "2026.09.0" and st["host"] == "db.internal.example" and st["database"] == "neo4j" and st["error"] is None
    store.publish(1)
    st = store.status(1)
    assert st["out_of_date"] is False and st["last_counts"]["Requirement"] == 4 and st["last_published_at"]
    db.run("UPDATE decisions SET decision='rejected' WHERE uid='p1-REQ-001'")  # a decision changed
    assert store.status(1)["out_of_date"] is True
    store.publish(1)
    assert store.status(1)["out_of_date"] is False
    db.run("UPDATE sources SET source_type='other' WHERE id=2")  # a source type changed
    assert store.status(1)["out_of_date"] is True
    store.publish(1)
    db.run("UPDATE generation SET state='failed', result=NULL WHERE uid='p1-REQ-003'")  # a draft disappeared
    assert store.status(1)["out_of_date"] is True
    store.publish(1)
    assert store.status(1)["out_of_date"] is False


def test_the_hash_ignores_publish_time_but_not_the_project(db):
    a = neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform").digest()
    assert a == neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform").digest()
    assert a != neo4j_store.build_bundle(db, 1, "other-project", "Core Banking Platform").digest()
    store, _ = store_for(db)
    store.publish(1)
    with pytest.raises(ApiError) as e:
        store.status(1, "other-project")  # a project is only ever published under its own key
    assert (e.value.status, e.value.code) == (422, "project_key_mismatch")


def test_failed_publish_leaves_no_log_entry(db):
    store, _ = store_for(db, fail_write=RuntimeError("boom"))
    with pytest.raises(ApiError):
        store.publish(1)
    assert db.one("SELECT COUNT(*) n FROM publish_log")["n"] == 0
    assert store.status(1)["out_of_date"] is True


def test_check_runs_return_1_and_creates_constraints_but_publishes_nothing(db):
    store, driver = store_for(db)
    info = store.check()
    assert (info["return_one"], info["server_version"], info["host"], info["database"]) == (1, "2026.09.0", "db.internal.example", "neo4j")
    assert driver.transactions == 0 and not driver.graph.nodes
    assert PASSWORD not in json.dumps(info)


def test_a_second_publish_at_the_same_time_is_refused(db):
    store, _ = store_for(db)
    assert store._publishing.acquire(blocking=False)
    try:
        with pytest.raises(ApiError) as e:
            store.publish(1)
        assert e.value.status == 409 and e.value.code == "publish_in_progress"
    finally:
        store._publishing.release()


# ------------------------------------------------------------------------------------------------------------------ errors
def raising(exc):
    def factory(cfg):
        raise exc
    return factory


@pytest.mark.parametrize("exc,code", [
    (ServiceUnavailable(f"cannot connect to {URI} as neo4j/{PASSWORD}"), "neo4j_unreachable"),
    (ConnectionRefusedError(f"refused {PASSWORD}"), "neo4j_unreachable"),
    (TimeoutError(PASSWORD), "neo4j_unreachable"),
    (AuthError(f"bad credentials {PASSWORD}"), "neo4j_auth_failed"),
    (RuntimeError(f"surprise {PASSWORD}"), "neo4j_publish_failed"),
])
def test_each_driver_error_becomes_one_calm_code(db, exc, code, caplog):
    store = Neo4jStore(db, config_loader=lambda: CFG, driver_factory=raising(exc))
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ApiError) as e:
            store.publish(1)
    assert (e.value.status, e.value.code) == (503, code)
    assert PASSWORD not in e.value.message and URI not in e.value.message and "db.internal" not in e.value.message and "Traceback" not in e.value.message
    assert PASSWORD not in caplog.text and URI not in caplog.text
    st = store.status(1)
    assert st["reachable"] is False and st["error"] == code and PASSWORD not in json.dumps(st)


def test_error_during_the_write_is_translated_too(db, caplog):
    store, driver = store_for(db, fail_write=AuthError(PASSWORD))
    with caplog.at_level(logging.DEBUG), pytest.raises(ApiError) as e:
        store.publish(1)
    assert e.value.code == "neo4j_auth_failed" and driver.closed == 1 and PASSWORD not in caplog.text


def test_unconfigured_and_driver_missing(db, monkeypatch):
    store = Neo4jStore(db, config_loader=lambda: Neo4jConfig())
    with pytest.raises(ApiError) as e:
        store.publish(1)
    assert (e.value.status, e.value.code) == (503, "neo4j_unconfigured")
    st = store.status(1)
    assert (st["configured"], st["reachable"], st["error"]) == (False, False, "neo4j_unconfigured") and st["out_of_date"] is True
    monkeypatch.setitem(sys.modules, "neo4j", None)  # import neo4j -> ImportError
    store = Neo4jStore(db, config_loader=lambda: CFG)
    with pytest.raises(ApiError) as e:
        store.publish(1)
    assert (e.value.status, e.value.code) == (503, "neo4j_driver_missing") and "pip install neo4j" in e.value.message
    assert store.status(1)["error"] == "neo4j_driver_missing"


def test_the_app_imports_and_runs_without_the_driver(make_client, monkeypatch):
    monkeypatch.setitem(sys.modules, "neo4j", None)
    c = make_client()
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/projects/1/publish/neo4j").json()["error"] == "neo4j_unconfigured"


# ------------------------------------------------------------------------------------------------------------------ API
def wire(c, cfg=CFG, graph=None, **kw):
    """Give the app's store a fake driver; returns the graph."""
    store = c.app.state.neo4j
    driver = Driver(graph, **kw)
    store._load_config = lambda: cfg
    store._driver_factory = lambda cf: driver
    return driver


def test_endpoints_publish_and_status(make_client, caplog):
    c = make_client()
    seed_db = c.app.state.db
    seed(seed_db, project=False)
    st = c.get("/api/projects/1/publish/neo4j")
    assert st.status_code == 200 and st.json()["configured"] is False and st.json()["error"] == "neo4j_unconfigured" and st.json()["out_of_date"] is True
    r = c.post("/api/projects/1/publish/neo4j")
    assert r.status_code == 503 and r.json() == {"error": {"code": "neo4j_unconfigured", "message": neo4j_store.MSG["neo4j_unconfigured"]}}
    driver = wire(c)
    with caplog.at_level(logging.DEBUG):
        r = c.post("/api/projects/1/publish/neo4j")
        st = c.get("/api/projects/1/publish/neo4j")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counts"]["Requirement"] == 4 and body["project_id"] == "demo-project" and set(body) == {"project_id", "published_at", "seconds", "counts", "deactivated", "content_hash"}
    s = st.json()
    assert s["configured"] and s["reachable"] and s["out_of_date"] is False and s["host"] == "db.internal.example" and s["server_version"] == "2026.09.0"
    assert s["last_counts"]["TaskDraft"] == 2
    assert PASSWORD not in r.text and PASSWORD not in st.text and PASSWORD not in caplog.text and URI not in r.text + st.text
    # an id or name in the body may only repeat the project's own key and name
    again = c.post("/api/projects/1/publish/neo4j", json={"project_id": "demo-project", "project_name": "Core Banking Platform"})
    assert again.status_code == 200 and again.json()["project_id"] == "demo-project"
    assert node(driver.graph, "Project", "demo-project")[S.ProjectP.NAME] == "Core Banking Platform"
    assert c.get("/api/projects/1/publish/neo4j", params={"project_id": "demo-project"}).json()["out_of_date"] is False
    assert c.get("/api/projects/1/publish/neo4j", params={"project_id": "bad id!"}).status_code == 422
    assert c.post("/api/projects/99/publish/neo4j").status_code == 404


def test_endpoint_errors_are_503_with_codes_and_other_endpoints_keep_working(make_client):
    c = make_client()
    wire(c)
    c.app.state.neo4j._driver_factory = raising(AuthError(PASSWORD))
    r = c.post("/api/projects/1/publish/neo4j")
    assert r.status_code == 503 and r.json()["error"]["code"] == "neo4j_auth_failed" and PASSWORD not in r.text
    c.app.state.neo4j._driver_factory = raising(ServiceUnavailable(PASSWORD))
    r = c.post("/api/projects/1/publish/neo4j")
    assert r.status_code == 503 and r.json()["error"]["code"] == "neo4j_unreachable" and PASSWORD not in r.text
    assert c.get("/api/health").status_code == 200 and c.get("/api/projects/1/summary").status_code == 200 and c.get("/api/engine").status_code == 200


def test_upload_takes_a_source_type_and_defaults_to_srs(make_client):
    c = make_client()
    ok = c.post("/api/projects/1/sources", files=[("files", ("a.txt", b"The system shall do a thing.", "text/plain"))])
    assert ok.status_code == 201 and ok.json()["accepted"][0]["source_type"] == "srs"
    brd = c.post("/api/projects/1/sources", files=[("files", ("b.txt", b"The bank shall keep logs.", "text/plain"))], data={"source_type": "BRD"})
    assert brd.status_code == 201 and brd.json()["accepted"][0]["source_type"] == "brd"
    bad = c.post("/api/projects/1/sources", files=[("files", ("c.txt", b"x y z.", "text/plain"))], data={"source_type": "wiki"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_parameter"
    listed = {s["filename"]: s["source_type"] for s in c.get("/api/projects/1/sources").json()}
    assert listed == {"a.txt": "srs", "b.txt": "brd"}
    row = c.app.state.db.one("SELECT sha256 FROM sources WHERE filename='a.txt'")
    assert row["sha256"] == hashlib.sha256(b"The system shall do a thing.").hexdigest()


# ------------------------------------------------------------------------------------------------------------------ constants
def test_every_name_comes_from_the_constants_module():
    text = " ".join([neo4j_store.Q_PROJECT, neo4j_store.Q_SOURCE, neo4j_store.Q_REQUIREMENTS, neo4j_store.Q_ISSUES, neo4j_store.Q_DRAFTS, neo4j_store.Q_DUPLICATES]
                    + list(neo4j_store.Q_DEACTIVATE.values()) + neo4j_store.schema_statements())
    for label in (S.Label.PROJECT, S.Label.SOURCE, S.Label.REQUIREMENT, S.Label.ISSUE, S.Label.DRAFT, S.Label.SPRINT):
        assert f":{label}" in text
    for rel in (S.Rel.HAS_SOURCE, S.Rel.CONTAINS, S.Rel.HAS_ISSUE, S.Rel.HAS_DRAFT, S.Rel.DUPLICATE_OF):
        assert rel in text
    assert S.Rel.HAS_SPRINT == "HAS_SPRINT" and S.Rel.PLANNED_IN == "PLANNED_IN" and S.Label.SPRINT == "Sprint"
    assert "RVU" not in text and S.APPROVED_STATUSES == ("accepted", "edited")


# ------------------------------------------------------------------------------------------------------------------ optional integration
URI_IN_ENV = bool(os.environ.get("C1_NEO4J_URI") or os.environ.get("NEO4J_URI"))


@pytest.mark.skipif(not (URI_IN_ENV and os.environ.get("C1_NEO4J_TEST") == "1"), reason="needs a Neo4j URI in the environment and C1_NEO4J_TEST=1")
def test_integration_publish_twice_against_a_real_neo4j(tmp_path, monkeypatch):
    monkeypatch.setattr(neo4j_config, "ENV_FILES", neo4j_config.__dict__.get("_REAL_ENV_FILES", [neo4j_config.REPO_ROOT / ".env", neo4j_config.PROJECT_ROOT / ".env"]))
    db = Database(tmp_path / "it.db")
    seed(db)
    project = ("c1-test-project", "C1 test project")
    db.run("UPDATE projects SET project_key=?, name=? WHERE id=1", project)  # the test publishes under its own key, so it never touches real data
    store = Neo4jStore(db)
    cfg = store.config()
    assert cfg.configured, "set the Neo4j password in the environment or the shared .env"
    driver = store.open(cfg)
    try:
        first = store.publish(1)
        second = store.publish(1)
        assert first["counts"] == second["counts"] and first["content_hash"] == second["content_hash"]
        with driver.session(database=cfg.database) as session:
            n = session.run("MATCH (r:Requirement {project_id: $p}) RETURN count(r) AS n", p=project[0]).single()["n"]
            assert n == 4  # no duplicates after the second publish
            dup = session.run("MATCH (:Requirement {project_id: $p})-[d:DUPLICATE_OF]->() RETURN count(d) AS n", p=project[0]).single()["n"]
            assert dup == 1
    finally:
        with driver.session(database=cfg.database) as session:
            session.run("MATCH (n {project_id: $p}) DETACH DELETE n", p=project[0]).consume()  # only the test project
        driver.close()
