"""Component 1 API: phases and sprints (effective sprint, page ranges, bulk assign, detection), no re-analysis of analysed documents, re-analysis of one
document, the per-document and overview numbers, the migration of older workspace files, and the background sync (fake clock, fake graph store).

No real graph database is touched: the settings are isolated by test_c1_neo4j.py's autouse fixture and the sync worker is off unless a test builds its own.
"""
import json
import sqlite3
from types import SimpleNamespace

import pytest

from agents.requirement_agent.api import analysis, autosync
from agents.requirement_agent.api.db import Database
from agents.requirement_agent.api.errors import ApiError
from tests.test_c1_api import MODELS_PRESENT, CountingBackend, analyze, error_of, make_client, make_pdf, reqs, upload  # noqa: F401  (fixtures)
from tests.test_c1_neo4j import isolated_settings, seed  # noqa: F401  (isolated_settings is autouse there)

needs_models = pytest.mark.skipif(not MODELS_PRESENT, reason="saved models missing in models/component1/part_a_active")


@pytest.fixture
def c(make_client):  # noqa: F811
    """A workspace with four requirements in two documents, seeded without running the models; no sprint exists yet (it is created on first use)."""
    client = make_client()
    seed(client.app.state.db, project=False)
    return client


def sprints(c):
    return {s["name"]: s for s in c.get("/api/projects/1/sprints").json()}


def rows(c, **params):
    return {i["id"]: i for i in c.get("/api/projects/1/requirements", params=params).json()["items"]}


# ------------------------------------------------------------------------------------------------------------------ migration
OLD_FILE = """
CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE sources (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, filename TEXT NOT NULL, stored_path TEXT NOT NULL, ext TEXT NOT NULL,
    size_bytes INTEGER NOT NULL, pages INTEGER, warnings TEXT NOT NULL DEFAULT '[]', extracted TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE requirements (uid TEXT PRIMARY KEY, project_id INTEGER NOT NULL, rid TEXT NOT NULL, seq INTEGER NOT NULL, source_id INTEGER NOT NULL, source_file TEXT NOT NULL,
    text TEXT NOT NULL, text_hash TEXT NOT NULL, occurrence INTEGER NOT NULL, created_at TEXT NOT NULL);
INSERT INTO projects VALUES (1, 'Old project', '2026-01-01T00:00:00+00:00'), (2, 'Second', '2026-01-02T00:00:00+00:00');
INSERT INTO sources VALUES (1, 1, 'a.txt', '/x/a', '.txt', 5, NULL, '[]', '{}', '2026-01-01T00:00:00+00:00'),
                           (2, 1, 'b.txt', '/x/b', '.txt', 5, NULL, '[]', '{}', '2026-01-03T00:00:00+00:00'),
                           (3, 2, 'c.txt', '/x/c', '.txt', 5, NULL, '[]', '{}', '2026-01-03T00:00:00+00:00');
INSERT INTO requirements VALUES ('p1-REQ-001', 1, 'REQ-001', 1, 1, 'a.txt', 'The system shall log in.', 'h', 1, '2026-01-01T01:00:00+00:00');
"""


def test_migration_gives_every_project_sprint_1_and_sets_the_analysis_state(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript(OLD_FILE)
    con.commit()
    con.close()
    for _ in range(2):  # opening it again changes nothing
        db = Database(path)
        assert [(s["project_id"], s["name"], s["origin"], s["confirmed"]) for s in db.all("SELECT * FROM sprints ORDER BY project_id")] == [(1, "Sprint 1", "manual", 1), (2, "Sprint 1", "manual", 1)]
        for p in db.all("SELECT * FROM projects"):
            assert p["current_sprint_id"] == db.one("SELECT id FROM sprints WHERE project_id=?", (p["id"],))["id"]
        assert {s["default_sprint_id"] for s in db.all("SELECT * FROM sources WHERE project_id=1")} == {db.one("SELECT current_sprint_id c FROM projects WHERE id=1")["c"]}
        # a document with requirements counts as analysed; one without does not (it will be analysed by the next run)
        assert [(s["id"], s["analysis_state"]) for s in db.all("SELECT id, analysis_state FROM sources ORDER BY id")] == [(1, "analyzed"), (2, "not_analyzed"), (3, "not_analyzed")]
        assert db.one("SELECT sprint_id FROM requirements")["sprint_id"] is None  # no override


def test_a_project_made_later_also_starts_with_sprint_1(c):
    p = c.post("/api/projects", json={"name": "Another"}).json()
    s = c.get(f"/api/projects/{p['id']}/sprints").json()
    assert [(x["name"], x["is_current"]) for x in s] == [("Sprint 1", True)]


# ------------------------------------------------------------------------------------------------------------------ effective sprint, assignment
def test_a_requirement_follows_its_document_until_it_is_assigned(c):
    s1 = sprints(c)["Sprint 1"]
    assert {r["sprint_id"] for r in rows(c).values()} == {s1["id"]}
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2"}).json()
    r = c.put(f"/api/projects/1/sources/2/sprint", json={"sprint_id": s2["id"]})  # a document may sit in another sprint than the rest
    assert r.status_code == 200 and r.json()["default_sprint_id"] == s2["id"]
    assert [r["sprint_id"] for r in rows(c).values()] == [s1["id"], s1["id"], s1["id"], s2["id"]]
    out = c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-004", "p1-REQ-001"], "sprint_id": s1["id"]})
    assert out.json() == {"assigned": 2, "sprint_id": s1["id"]}
    assert rows(c)["REQ-004"]["sprint_id"] == s1["id"]  # the override wins over the document
    c.put("/api/projects/1/sources/2/sprint", json={"sprint_id": s1["id"]})
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-004"], "sprint_id": s2["id"]})
    assert c.get("/api/requirements/REQ-004").json()["sprint_id"] == s2["id"]
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-004"], "sprint_id": None})  # back to following the document
    assert rows(c)["REQ-004"]["sprint_id"] == s1["id"]
    assert error_of(c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-404"], "sprint_id": s1["id"]}))["code"] == "requirement_not_found"
    assert error_of(c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-001"], "sprint_id": 999}))["code"] == "sprint_not_found"


def test_the_list_can_be_filtered_by_sprint(c):
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2"}).json()
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-002", "REQ-003"], "sprint_id": s2["id"]})
    assert sorted(rows(c, sprint_id=s2["id"])) == ["REQ-002", "REQ-003"]
    assert c.get("/api/projects/1/requirements", params={"sprint_id": s2["id"]}).json()["total"] == 2


def test_page_ranges_set_overrides_and_later_ranges_win(c):
    db = c.app.state.db
    for rid, page in (("REQ-001", 1), ("REQ-002", 2), ("REQ-003", 5)):
        db.run("UPDATE requirements SET page=? WHERE rid=?", (page, rid))
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2"}).json()
    s3 = c.post("/api/projects/1/sprints", json={"name": "Sprint 3"}).json()
    out = c.post("/api/projects/1/sources/1/assign-ranges", json={"ranges": [{"from_page": 1, "to_page": 2, "sprint_id": s2["id"]}, {"from_page": 2, "to_page": 5, "sprint_id": s3["id"]}]})
    assert out.json() == {"assigned": 4, "requirements": 3, "without_page": 0}  # REQ-002 was set twice
    got = {k: v["sprint_id"] for k, v in rows(c).items()}
    assert got == {"REQ-001": s2["id"], "REQ-002": s3["id"], "REQ-003": s3["id"], "REQ-004": sprints(c)["Sprint 1"]["id"]}
    assert c.post("/api/projects/1/sources/2/assign-ranges", json={"ranges": [{"from_page": 1, "to_page": 9, "sprint_id": s2["id"]}]}).json() == {"assigned": 0, "requirements": 1, "without_page": 1}
    assert error_of(c.post("/api/projects/1/sources/1/assign-ranges", json={"ranges": [{"from_page": 3, "to_page": 2, "sprint_id": s2["id"]}]}))["code"] == "validation_error"
    assert error_of(c.post("/api/projects/1/sources/9/assign-ranges", json={"ranges": []}))["code"] == "source_not_found"


# ------------------------------------------------------------------------------------------------------------------ phases and sprints
def test_phases_and_sprints_crud_and_rules(c):
    ph = c.post("/api/projects/1/phases", json={"name": "Discovery"}).json()
    assert error_of(c.post("/api/projects/1/phases", json={"name": " discovery "}))["code"] == "phase_name_taken"  # unique ignoring case and spacing
    sp = c.post("/api/projects/1/sprints", json={"name": "Sprint 2", "phase_id": ph["id"], "start_date": "2026-11-01", "end_date": "2026-11-14", "goal": "Login"}).json()
    assert (sp["phase_id"], sp["goal"], sp["origin"], sp["confirmed"], sp["is_current"]) == (ph["id"], "Login", "manual", True, False)
    assert error_of(c.post("/api/projects/1/sprints", json={"name": "SPRINT 2"}))["code"] == "sprint_name_taken"
    assert error_of(c.post("/api/projects/1/sprints", json={"name": "Bad dates", "start_date": "2026-11-10", "end_date": "2026-11-01"}))["code"] == "validation_error"
    assert error_of(c.post("/api/projects/1/sprints", json={"name": "Bad phase", "phase_id": 99}))["code"] == "phase_not_found"
    assert c.get("/api/projects/1/phases").json() == [dict(ph, sprints=1)]
    # rename, move out of the phase with null
    r = c.patch(f"/api/projects/1/sprints/{sp['id']}", json={"name": "Sprint Two", "phase_id": None})
    assert r.json()["name"] == "Sprint Two" and r.json()["phase_id"] is None
    c.patch(f"/api/projects/1/sprints/{sp['id']}", json={"phase_id": ph["id"]})
    # deleting a phase keeps its sprints
    assert c.delete(f"/api/projects/1/phases/{ph['id']}").status_code == 204
    assert sprints(c)["Sprint Two"]["phase_id"] is None
    # the current sprint
    assert c.put("/api/projects/1/current-sprint", json={"sprint_id": sp["id"]}).json()["is_current"] is True
    assert [s["is_current"] for s in c.get("/api/projects/1/sprints").json()] == [False, True]


def test_deleting_a_sprint_needs_a_target_when_it_holds_something(c):
    s1 = sprints(c)["Sprint 1"]
    assert error_of(c.delete(f"/api/projects/1/sprints/{s1['id']}"))["code"] == "last_sprint"
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2"}).json()
    assert error_of(c.delete(f"/api/projects/1/sprints/{s1['id']}"))["code"] == "reassign_required"  # four requirements, two documents, and it is current
    assert error_of(c.delete(f"/api/projects/1/sprints/{s1['id']}", params={"reassign_to": s1["id"]}))["code"] == "validation_error"
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-001"], "sprint_id": s2["id"]})
    out = c.delete(f"/api/projects/1/sprints/{s1['id']}", params={"reassign_to": s2["id"]})
    assert out.json() == {"deleted": s1["id"], "reassigned_to": s2["id"], "requirements_moved": 3}
    assert {r["sprint_id"] for r in rows(c).values()} == {s2["id"]}
    assert {s["default_sprint_id"] for s in c.get("/api/projects/1/sources").json()} == {s2["id"]}
    assert [s["is_current"] for s in c.get("/api/projects/1/sprints").json()] == [True]
    s3 = c.post("/api/projects/1/sprints", json={"name": "Empty"}).json()
    assert c.delete(f"/api/projects/1/sprints/{s3['id']}").json()["requirements_moved"] == 0  # nothing in it: no target needed


def test_planning_changes_never_start_an_analysis(c):
    db = c.app.state.db
    before = db.all("SELECT id, analysis_state FROM sources ORDER BY id")
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2"}).json()
    c.put("/api/projects/1/sources/1/sprint", json={"sprint_id": s2["id"]})
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-001"], "sprint_id": s2["id"]})
    c.put("/api/projects/1/current-sprint", json={"sprint_id": s2["id"]})
    assert db.one("SELECT COUNT(*) n FROM jobs")["n"] == 0 and db.all("SELECT id, analysis_state FROM sources ORDER BY id") == before
    assert db.one("SELECT COUNT(*) n FROM generation WHERE state IN ('queued','running')")["n"] == 0


# ------------------------------------------------------------------------------------------------------------------ upload
def test_upload_uses_the_current_sprint_a_chosen_one_or_a_detected_one(make_client):  # noqa: F811
    c = make_client()
    s1 = sprints(c)["Sprint 1"]
    out = upload(c, [("plain.txt", b"1.1 The system shall log in.\n", "text/plain")]).json()
    assert out["sprint_detected"] is False and out["detected"] == [] and out["accepted"][0]["default_sprint_id"] == s1["id"]
    assert out["accepted"][0]["analysis_state"] == "not_analyzed"
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2"}).json()
    r = c.post("/api/projects/1/sources", files=[("files", ("x.txt", b"1.1 The system shall log in.\n", "text/plain"))], data={"sprint_id": str(s2["id"])})
    assert r.json()["accepted"][0]["default_sprint_id"] == s2["id"] and r.json()["sprint_detected"] is False
    ph = c.post("/api/projects/1/phases", json={"name": "Build"}).json()
    assert error_of(c.post("/api/projects/1/sources", files=[("files", ("y.txt", b"1.1 The system shall log in.\n", "text/plain"))], data={"phase_id": str(ph["id"])}))["code"] == "validation_error"
    c.patch(f"/api/projects/1/sprints/{s2['id']}", json={"phase_id": ph["id"]})
    r = c.post("/api/projects/1/sources", files=[("files", ("y.txt", b"1.1 The system shall log in.\n", "text/plain"))], data={"phase_id": str(ph["id"])})
    assert r.json()["accepted"][0]["default_sprint_id"] == s2["id"]  # the first sprint of the phase
    assert error_of(c.post("/api/projects/1/sources", files=[("files", ("z.txt", b"1.1 The system shall log in.\n", "text/plain"))], data={"sprint_id": "999"}))["code"] == "sprint_not_found"


def test_a_sprint_named_in_the_file_name_or_first_page_is_proposed(make_client):  # noqa: F811
    c = make_client()
    out = upload(c, [("Sprint_3_requirements.txt", b"1.1 The system shall log in.\n", "text/plain")]).json()
    assert out["sprint_detected"] is True
    d = out["detected"][0]
    assert (d["filename"], d["name"], d["confirmed"]) == ("Sprint_3_requirements.txt", "Sprint 3", False)
    assert out["accepted"][0]["default_sprint_id"] == d["sprint_id"]
    got = sprints(c)["Sprint 3"]
    assert (got["origin"], got["confirmed"], got["is_current"]) == ("detected", False, False)
    again = upload(c, [("notes.txt", b"Iteration 2 - login\n1.1 The system shall log in.\n", "text/plain"), ("sprint 3 more.txt", b"1.1 The system shall log out.\n", "text/plain")]).json()
    assert [d["name"] for d in again["detected"]] == ["Iteration 2", "Sprint 3"]  # first page text, then the existing sprint is reused
    assert len([s for s in c.get("/api/projects/1/sprints").json() if s["name"] == "Sprint 3"]) == 1
    assert c.patch(f"/api/projects/1/sprints/{d['sprint_id']}", json={"confirmed": True}).json()["confirmed"] is True


# ------------------------------------------------------------------------------------------------------------------ numbers
def test_the_document_list_has_state_counts_and_sprint_breakdown(c):
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2"}).json()
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-002"], "sprint_id": s2["id"]})
    s1 = sprints(c)["Sprint 1"]
    first, second = c.get("/api/projects/1/sources").json()
    assert (first["filename"], first["source_type"], first["analysis_state"], first["requirements"], first["ambiguities"]) == ("srs.txt", "srs", "analyzed", 3, 1)
    assert first["drafts"] == {"ready": 1, "needs_clarification": 1, "failed": 0} and second["drafts"] == {"ready": 0, "needs_clarification": 0, "failed": 1}
    assert first["sprints"] == [{"sprint_id": s1["id"], "count": 2}, {"sprint_id": s2["id"], "count": 1}] and second["sprints"] == [{"sprint_id": s1["id"], "count": 1}]
    assert first["uploaded_at"] == first["created_at"] and first["pages"] is None and first["size_bytes"] == 10 and first["analyzed_at"] is None


def test_the_overview_has_the_planning_numbers(c):
    db = c.app.state.db
    ph = c.post("/api/projects/1/phases", json={"name": "Build"}).json()
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2", "phase_id": ph["id"], "goal": "Ship it", "start_date": "2026-11-01"}).json()
    c.put("/api/projects/1/current-sprint", json={"sprint_id": s2["id"]})
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-001", "REQ-004"], "sprint_id": s2["id"]})
    db.run("UPDATE sources SET analysis_state='analyzed', analyzed_at='2026-10-01T00:00:00+00:00' WHERE id=1")  # seeded decisions: REQ-001 accepted, REQ-003 edited, REQ-004 rejected
    o = c.get("/api/projects/1/overview").json()
    assert o["current_sprint"] == {"id": s2["id"], "name": "Sprint 2", "phase_id": ph["id"], "start_date": "2026-11-01", "end_date": None, "goal": "Ship it",
                                   "requirements": 2, "pending": 0, "decided": 2, "percent_decided": 100.0}
    assert o["current_phase"] == {"id": ph["id"], "name": "Build", "sprints": 1, "requirements": 2, "pending": 0, "decided": 2, "percent_decided": 100.0}
    by_sprint = {s["name"]: s for s in o["by_sprint"]}
    assert (by_sprint["Sprint 1"]["total"], by_sprint["Sprint 1"]["pending"], by_sprint["Sprint 2"]["accepted"], by_sprint["Sprint 2"]["is_current"]) == (2, 1, 1, True)
    assert [(p["phase_id"], p["name"], p["total"], p["accepted"], p["pending"], p["sprints"]) for p in o["by_phase"]] == [(ph["id"], "Build", 2, 1, 0, 1), (None, None, 2, 0, 1, 1)]
    assert o["findings_by_type"] == {"ambiguity": 1, "conflict": 0, "duplicate": 1, "security": 1}
    assert o["analysis"] == {"ready": 2, "total": 2}
    assert [s["id"] for s in o["latest_uploads"]] == [2, 1] and o["latest_uploads"][0]["requirements"] == 1
    assert o["sync"]["state"] == "not_configured" and o["sync"]["enabled"] is False  # the sync worker is off in tests and nothing is configured
    assert set(o["sync"]) == {"state", "enabled", "last_synced_at", "counts", "next_attempt_at", "error"}
    assert c.get("/api/projects/1/sync").json() == o["sync"]


# ------------------------------------------------------------------------------------------------------------------ analysis (needs the saved models)
DOC = b"1. Reports\n\n1.1 The system shall export reports as PDF.\n1.2 The system shall list all users in a table.\n"
DOC_2 = b"1. Billing\n\n1.1 The system shall send an invoice by email.\n"


def state_of(c):
    return {s["filename"]: s["analysis_state"] for s in c.get("/api/projects/1/sources").json()}


@needs_models
def test_analysed_documents_are_skipped_completely(make_client):  # noqa: F811
    backend = CountingBackend()
    c = make_client(backend=backend)
    analyze(c, files=(("a.txt", DOC, "text/plain"),))
    assert state_of(c) == {"a.txt": "analyzed"} and len(backend.calls) == 2
    c.put("/api/requirements/REQ-001/decision", json={"decision": "accepted", "note": "ok"})
    before = {i["uid"]: i for i in reqs(c)["items"]}
    stamp = c.app.state.db.one("SELECT created_at, risk_score, ambiguity_probability FROM requirements WHERE rid='REQ-001'")

    j = analyze(c, files=())  # nothing new: no analysis, no drafts
    assert j["part_a_done"] is True and len(backend.calls) == 2
    assert {i["uid"]: i for i in reqs(c)["items"]} == before and c.app.state.db.one("SELECT created_at, risk_score, ambiguity_probability FROM requirements WHERE rid='REQ-001'") == stamp

    analyze(c, files=(("b.txt", DOC_2, "text/plain"),))  # only the new document is analysed and only its requirement gets a draft
    assert state_of(c) == {"a.txt": "analyzed", "b.txt": "analyzed"} and len(backend.calls) == 3
    assert [i["id"] for i in reqs(c)["items"]] == ["REQ-001", "REQ-002", "REQ-003"]
    assert c.get("/api/requirements/REQ-001").json()["decision"]["decision"] == "accepted"
    sources = {s["filename"]: s for s in c.get("/api/projects/1/sources").json()}
    assert sources["a.txt"]["requirements"] == 2 and sources["b.txt"]["requirements"] == 1 and sources["b.txt"]["analyzed_at"]
    assert sources["a.txt"]["drafts"]["ready"] + sources["a.txt"]["drafts"]["needs_clarification"] == 2


@needs_models
def test_a_failed_analysis_is_marked_and_tried_again_next_time(make_client, monkeypatch):  # noqa: F811
    c = make_client(backend=CountingBackend())
    upload(c, [("a.txt", DOC, "text/plain")])
    real = analysis.detect
    monkeypatch.setattr(analysis, "detect", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    try:
        c.post("/api/projects/1/analyze")
    except RuntimeError:
        pass  # the test client re-raises the server error
    assert state_of(c) == {"a.txt": "failed"}
    monkeypatch.setattr(analysis, "detect", real)
    assert c.post("/api/projects/1/analyze", params={"policy": "all"}).status_code == 202
    assert state_of(c) == {"a.txt": "analyzed"}


@needs_models
def test_reanalyze_keeps_decisions_of_unchanged_text_and_audits_the_rest(make_client):  # noqa: F811
    backend = CountingBackend()
    c = make_client(backend=backend)
    analyze(c, files=(("a.txt", DOC, "text/plain"),))
    db = c.app.state.db
    c.put("/api/requirements/REQ-001/decision", json={"decision": "accepted", "note": "pdf is fine"})
    c.put("/api/requirements/REQ-002/decision", json={"decision": "rejected"})
    calls = len(backend.calls)

    r = c.post("/api/projects/1/sources/1/reanalyze", params={"policy": "all"})
    assert r.status_code == 202 and (r.json()["kept"], r.json()["changed"], r.json()["removed"], r.json()["added"], r.json()["queued"]) == (2, 0, 0, 0, 0)
    assert len(backend.calls) == calls and c.get("/api/requirements/REQ-001").json()["decision"]["note"] == "pdf is fine"

    # the second sentence changes, the first is the same, a third is gone
    extracted = json.loads(db.one("SELECT extracted FROM sources WHERE id=1")["extracted"])
    extracted["text"] = extracted["text"].replace("list all users in a table", "list all users in a grid")
    db.run("UPDATE sources SET extracted=? WHERE id=1", (json.dumps(extracted),))
    out = c.post("/api/projects/1/sources/1/reanalyze", params={"policy": "all"}).json()
    assert (out["kept"], out["changed"], out["removed"], out["added"]) == (1, 1, 0, 0) and out["queued"] == 1
    assert c.app.state.manager.wait_idle(60)
    assert c.get("/api/requirements/REQ-001").json()["decision"]["decision"] == "accepted"
    ids = [i["id"] for i in reqs(c)["items"]]
    assert ids == ["REQ-001", "REQ-003"]  # the changed requirement is a new one
    assert c.get("/api/requirements/REQ-003").json()["decision"] is None
    audit = db.all("SELECT uid, decision, reason FROM decision_audit WHERE reason LIKE 'reanalysis%'")
    assert audit == [{"uid": "p1-REQ-002", "decision": "rejected", "reason": "reanalysis_changed"}]
    assert error_of(c.post("/api/projects/1/sources/99/reanalyze"))["code"] == "source_not_found"


# ------------------------------------------------------------------------------------------------------------------ background sync
class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class FakeStore:
    """The part of Neo4jStore the worker uses."""

    def __init__(self, configured=True, out_of_date=True):
        self.configured, self.out_of_date, self.fail, self.published = configured, out_of_date, None, []
        self.on_publish = None

    def config(self):
        return SimpleNamespace(configured=self.configured)

    def publish_info(self, pid):
        return {"out_of_date": self.out_of_date, "last_published_at": None}

    def publish(self, pid, *a):
        if self.fail:
            raise ApiError(503, self.fail, "x")
        self.published.append(pid)
        if self.on_publish:
            self.on_publish()
        return {"published_at": "2026-10-20T00:00:00+00:00", "counts": {"Requirement": 4}}


@pytest.fixture
def worker(c):
    clock, store = Clock(), FakeStore()
    return autosync.AutoSync(c.app.state.db, store, clock=clock), clock, store


def advance(clock, w, seconds):
    clock.t += seconds
    w.tick()


def test_sync_waits_for_quiet_then_runs_once(worker):
    w, clock, store = worker
    w.notify(1)
    assert w.status(1)["state"] == "pending" and w.status(1)["next_attempt_at"]
    advance(clock, w, 9)
    assert store.published == []  # debounce: 10 s after the last change
    w.notify(1)  # another change restarts the wait
    advance(clock, w, 9)
    assert store.published == []
    advance(clock, w, 1)
    assert store.published == [1] and w.status(1)["state"] == "synced" and w.status(1)["last_synced_at"] == "2026-10-20T00:00:00+00:00"
    advance(clock, w, 60)
    assert store.published == [1]  # nothing changed: nothing is sent


def test_at_most_one_sync_per_30_seconds(worker):
    w, clock, store = worker
    w.notify(1)
    advance(clock, w, 10)
    assert store.published == [1]
    w.notify(1)
    advance(clock, w, 10)  # debounce is over, the rate limit is not (20 s after the last sync)
    assert store.published == [1] and w.status(1)["state"] == "pending"
    advance(clock, w, 19)
    assert store.published == [1]
    advance(clock, w, 1)
    assert store.published == [1, 1]


def test_a_sync_runs_while_a_document_is_being_analysed(worker, c):
    """The worker no longer waits for an analysis: the bundle holds the unfinished document back (tests/test_c1_graph_sync.py checks what is sent)."""
    w, clock, store = worker
    c.app.state.db.run("UPDATE sources SET analysis_state='analyzing' WHERE id=1")
    w.notify(1)
    advance(clock, w, 10)
    assert store.published == [1] and w.status(1)["state"] == "synced"


def test_not_configured_is_silent(worker):
    w, clock, store = worker
    store.configured = False
    w.notify(1)
    advance(clock, w, 60)
    st = w.status(1)
    assert store.published == [] and (st["state"], st["error"], st["next_attempt_at"]) == ("not_configured", None, None)
    store.configured = True  # set up later: the next change is synced
    w.notify(1)
    advance(clock, w, 10)
    assert store.published == [1]


def test_failures_back_off_30_60_120_240_300_and_end_in_unreachable(worker):
    w, clock, store = worker
    store.fail = "neo4j_unreachable"
    w.notify(1)
    waited = []
    advance(clock, w, 10)  # first attempt fails
    for _ in range(6):
        st = w.status(1)
        waited.append((st["state"], int(w._p[1]["next_attempt"] - clock.t), st["error"]))
        advance(clock, w, waited[-1][1] - 1)
        assert len(store.published) == 0  # not a second early
        advance(clock, w, 1)  # the next attempt
    assert waited == [("retrying", 30, "neo4j_unreachable"), ("retrying", 60, "neo4j_unreachable"), ("retrying", 120, "neo4j_unreachable"),
                      ("retrying", 240, "neo4j_unreachable"), ("unreachable", 300, "neo4j_unreachable"), ("unreachable", 300, "neo4j_unreachable")]
    store.fail = None
    advance(clock, w, 300)
    st = w.status(1)
    assert store.published == [1] and (st["state"], st["error"]) == ("synced", None) and w._p[1]["failures"] == 0


def test_a_change_made_while_syncing_is_synced_next(worker):
    w, clock, store = worker
    store.on_publish = lambda: w.notify(1)
    w.notify(1)
    advance(clock, w, 10)
    assert store.published == [1] and w.status(1)["state"] == "pending"
    store.on_publish = None
    advance(clock, w, 30)
    assert store.published == [1, 1] and w.status(1)["state"] == "synced"


def test_startup_syncs_a_project_that_is_out_of_date(worker):
    w, clock, store = worker
    w.check_startup()
    w.tick()
    assert store.published == [1]  # no waiting: it changed while the service was off
    store.published.clear()
    store.out_of_date = False
    w.check_startup()
    w.tick()
    assert store.published == []


def test_a_project_that_is_already_in_step_is_not_published_again(worker):
    w, clock, store = worker
    store.out_of_date = False
    w.notify(1)
    advance(clock, w, 10)
    assert store.published == [] and w.status(1)["state"] == "synced"


def test_switched_off_the_worker_does_nothing(c):
    store, clock = FakeStore(), Clock()
    w = autosync.AutoSync(c.app.state.db, store, clock=clock, enabled=False)
    w.notify(1)
    clock.t += 100
    w.tick()
    w.check_startup()
    assert store.published == [] and w.status(1)["enabled"] is False and w.status(1)["next_attempt_at"] is None
    assert autosync.enabled_from_env({"C1_AUTO_SYNC": "0"}) is False and autosync.enabled_from_env({}) is True and autosync.enabled_from_env({"C1_AUTO_SYNC": "1"}) is True


def test_changes_in_the_api_mark_the_project_as_changed(make_client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("C1_AUTO_SYNC", "1")
    client = make_client()
    seed(client.app.state.db, project=False)
    sync = client.app.state.sync
    assert sync.enabled and client.app.state.manager.on_draft is not None
    sync.stop()  # the real thread is not needed: the test looks at what was marked
    for action in (
        lambda: client.put("/api/requirements/REQ-001/decision", json={"decision": "accepted"}),
        lambda: client.delete("/api/requirements/REQ-001/decision"),
        lambda: client.post("/api/projects/1/phases", json={"name": "P"}),
        lambda: client.post("/api/projects/1/sprints", json={"name": "S2"}),
        lambda: client.put("/api/projects/1/current-sprint", json={"sprint_id": sprints(client)["S2"]["id"]}),
        lambda: client.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-001"], "sprint_id": None}),
        lambda: client.delete("/api/projects/1/sources/2"),
        lambda: client.app.state.manager.on_draft("p1-REQ-001"),
    ):
        sync._p.clear()
        action()
        assert sync._p.get(1, {}).get("dirty_at") is not None


# ------------------------------------------------------------------------------------------------------------------ graph: phases, sprints, planned-in
from agents.requirement_agent.api import neo4j_schema as S  # noqa: E402
from agents.requirement_agent.api import neo4j_store  # noqa: E402
from tests.test_c1_neo4j import Graph, Result, store_for  # noqa: E402


class PlanGraph(Graph):
    """The fake graph plus the statements for phases, sprints and the links between them (links carry an `active` flag; none is ever deleted)."""

    def __init__(self):
        super().__init__()
        self.edges = {}

    def run(self, q, p):
        L, R = S.Label, S.Rel
        if q == neo4j_store.Q_SPRINTS:
            for row in p["rows"]:
                self.upsert(L.SPRINT, row["id"], row["props"])
                self.edges[(R.HAS_SPRINT, p["project_id"], row["id"])] = True
        elif q == neo4j_store.Q_PLANNED_CLEAR:
            for row in p["rows"]:
                for (kind, a, b) in list(self.edges):
                    if kind == R.PLANNED_IN and a == row["req_id"] and (row["sprint_id"] is None or b != row["sprint_id"]):
                        self.edges[(kind, a, b)] = False
        elif q == neo4j_store.Q_PLANNED:
            for row in p["rows"]:
                if row["sprint_id"] is not None:
                    self.edges[(R.PLANNED_IN, row["req_id"], row["sprint_id"])] = True
        else:
            return super().run(q, p)
        return Result(None)


def graph_store(c):
    graph = PlanGraph()
    store, driver = store_for(c.app.state.db, graph)
    return store, graph


def active(graph, kind):
    return sorted((a, b) for (k, a, b), on in graph.edges.items() if k == kind and on)


def test_publish_writes_sprints_and_the_planned_in_links_but_no_phases(c):
    ph = c.post("/api/projects/1/phases", json={"name": "Build"}).json()
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2", "phase_id": ph["id"], "start_date": "2026-11-01", "end_date": "2026-11-14", "goal": "Ship"}).json()
    c.put("/api/projects/1/current-sprint", json={"sprint_id": s2["id"]})
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-004"], "sprint_id": s2["id"]})
    store, graph = graph_store(c)
    out = store.publish(1)
    assert "Phase" not in out["counts"] and out["counts"]["Sprint"] == 2 and out["counts"]["PLANNED_IN"] == 4
    s1 = sprints(c)["Sprint 1"]
    n = graph.nodes
    assert not [k for k in n if k[0] == "Phase"] and not [k for k in graph.edges if k[0] == "IN_PHASE"]
    assert not any("phase" in str(v).lower() for v in n[("Sprint", f"demo-project:sprint{s2['id']}")].values())
    sp2 = n[("Sprint", f"demo-project:sprint{s2['id']}")]
    assert (sp2["name"], sp2["start"], sp2["end"], sp2["goal"], sp2["origin"], sp2["is_current"], sp2["active"]) == ("Sprint 2", "2026-11-01", "2026-11-14", "Ship", "manual", True, True)
    assert n[("Sprint", f"demo-project:sprint{s1['id']}")]["is_current"] is False
    assert [b for a, b in active(graph, "PLANNED_IN") if a.endswith("REQ-004")] == [f"demo-project:sprint{s2['id']}"]
    assert [b for a, b in active(graph, "PLANNED_IN") if a.endswith("REQ-001")] == [f"demo-project:sprint{s1['id']}"]
    assert n[("Requirement", "demo-project:src2:REQ-004")]["sprint_id"] == f"demo-project:sprint{s2['id']}"
    assert ("HAS_SPRINT", "demo-project", f"demo-project:sprint{s1['id']}") in graph.edges
    assert store.publish_info(1)["out_of_date"] is False


def test_a_planning_change_makes_the_project_out_of_date_and_the_graph_follows(c):
    store, graph = graph_store(c)
    ph = c.post("/api/projects/1/phases", json={"name": "Build"}).json()
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2", "phase_id": ph["id"]}).json()
    store.publish(1)
    assert store.publish_info(1)["out_of_date"] is False
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-001"], "sprint_id": s2["id"]})
    assert store.publish_info(1)["out_of_date"] is True
    store.publish(1)
    s1 = sprints(c)["Sprint 1"]
    assert [b for a, b in active(graph, "PLANNED_IN") if a.endswith("REQ-001")] == [f"demo-project:sprint{s2['id']}"]  # moved: the old link is switched off, not deleted
    assert graph.edges[("PLANNED_IN", "demo-project:src1:REQ-001", f"demo-project:sprint{s1['id']}")] is False
    # move the sprint out of its phase, and delete a sprint and a phase
    c.patch(f"/api/projects/1/sprints/{s2['id']}", json={"phase_id": None})
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-001"], "sprint_id": None})
    s3 = c.post("/api/projects/1/sprints", json={"name": "Sprint 3"}).json()
    c.delete(f"/api/projects/1/sprints/{s2['id']}", params={"reassign_to": s3["id"]})
    c.delete(f"/api/projects/1/phases/{ph['id']}")
    before = set(graph.nodes)
    out = store.publish(1)
    assert before <= set(graph.nodes)  # nothing deleted
    assert out["deactivated"]["Sprint"] == 1 and "Phase" not in out["deactivated"]
    assert graph.nodes[("Sprint", f"demo-project:sprint{s2['id']}")]["active"] is False and graph.nodes[("Sprint", f"demo-project:sprint{s2['id']}")]["is_current"] is False
    assert store.publish(1)["deactivated"]["Sprint"] == 0  # not counted twice


def test_the_new_names_are_in_the_schema_file_only():
    assert (S.Label.SPRINT, S.Rel.HAS_SPRINT, S.Rel.PLANNED_IN, S.Rel.INCLUDES_SOURCE) == ("Sprint", "HAS_SPRINT", "PLANNED_IN", "INCLUDES_SOURCE")
    assert not hasattr(S.Label, "PHASE") and not hasattr(S.Rel, "IN_PHASE") and not hasattr(neo4j_store, "Q_PHASES")  # phases are not published
    statements = neo4j_store.schema_statements()
    assert not any("Phase" in s for s in statements) and any("FOR (n:Sprint) REQUIRE n.sprint_id IS UNIQUE" in s for s in statements)
    assert all("IF NOT EXISTS" in s for s in statements)
    assert all("DELETE" not in q.upper() for q in (neo4j_store.Q_SPRINTS, neo4j_store.Q_PLANNED_CLEAR, neo4j_store.Q_PLANNED, neo4j_store.Q_INCLUDES, neo4j_store.Q_INCLUDES_DEACTIVATE))
