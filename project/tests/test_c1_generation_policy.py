"""Component 1: draft generation policy (smart / all / manual), priority classes, pause/resume, ETA, restart, clarified-text regeneration, decision checks.

Backends are scripted (no model server). The priority-class tests need no models; the API tests are skipped if the saved Part A models are missing.
"""
import json
import sqlite3
import threading
from pathlib import Path

import pytest

from agents.requirement_agent.api import priority
from agents.requirement_agent.api.db import Database, now
from agents.requirement_agent.api.gen_worker import ETA_MIN_SAMPLES, mock_reply
from agents.requirement_agent.generation import MockBackend
from tests.test_c1_api import MODELS_PRESENT, SAMPLE, analyze, client, error_of, make_client, reqs, upload  # noqa: F401  (fixtures)

api = pytest.mark.skipif(not MODELS_PRESENT, reason="saved models missing in models/component1/part_a_active")


def post_analyze(c, policy=None, pid=1, upload_sample=True):
    if upload_sample:
        assert upload(c, [("sample_srs.txt", SAMPLE, "text/plain")], pid).status_code == 201
    r = c.post(f"/api/projects/{pid}/analyze", params={"policy": policy} if policy else {})
    assert r.status_code == 202, r.text
    return r.json()


def states(c):
    return {i["uid"]: i["generation_state"] for i in reqs(c)["items"]}


def drafts(c):
    return c.get("/api/projects/1/summary").json()["task_drafts"]


def sample_classes(c):
    return priority.classes(c.app.state.db, 1)


# ------------------------------------------------------------------------------------------------------------------ priority classes (no models)
ROW = {"uid": "u", "text": "The system shall export the report.", "fr_nfr": "FR", "is_security": 0, "ambiguity_label": "ok", "duplicate_group": ""}


def test_classify_p1_reasons_p2_and_p3():
    assert priority.classify(ROW, False) == priority.P2
    assert priority.classify(dict(ROW, ambiguity_label="defect"), False) == priority.P1
    assert priority.classify(dict(ROW, is_security=1), False) == priority.P1
    assert priority.classify(dict(ROW, fr_nfr="NFR"), False) == priority.P1
    assert priority.classify(dict(ROW, text="The system shall export the report quickly."), False) == priority.P1  # a vague term
    assert priority.classify(ROW, True) == priority.P3  # secondary duplicate member of an otherwise plain FR
    assert priority.classify(dict(ROW, fr_nfr="NFR"), True) == priority.P1  # the P1 reasons come first


def test_selected_by_policy():
    for cls in (1, 2, 3):
        assert priority.selected("all", cls) is True and priority.selected("manual", cls) is False
    assert [priority.selected("smart", c) for c in (1, 2, 3)] == [True, False, False]
    assert priority.POLICIES == ("smart", "all", "manual") and priority.DEFAULT_POLICY == "smart"


def insert_requirement(db, seq, text, fr_nfr="FR", defect=False, security=False, group=""):
    db.run("INSERT INTO requirements (uid, project_id, rid, seq, source_id, source_file, text, text_hash, occurrence, fr_nfr, is_security, ambiguity_label, duplicate_group, created_at) "
           "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
           (f"p1-REQ-{seq:03d}", 1, f"REQ-{seq:03d}", seq, 1, "a.txt", text, f"h{seq}", 1, fr_nfr, int(security), "defect" if defect else "ok", group, now()))


def test_classes_marks_every_duplicate_member_after_the_first_as_secondary(tmp_path):
    db = Database(tmp_path / "t.db")
    insert_requirement(db, 1, "The system shall print invoices.", group="DUP0001")
    insert_requirement(db, 2, "The system shall print the invoices.", group="DUP0001")
    insert_requirement(db, 3, "The system shall print each invoice.", group="DUP0001")
    insert_requirement(db, 4, "The system shall archive old data.")
    insert_requirement(db, 5, "The system shall encrypt data.", security=True)
    insert_requirement(db, 6, "Pages shall load fast.", fr_nfr="NFR")
    assert priority.classes(db, 1) == {"p1-REQ-001": 2, "p1-REQ-002": 3, "p1-REQ-003": 3, "p1-REQ-004": 2, "p1-REQ-005": 1, "p1-REQ-006": 1}


def test_old_database_files_get_the_new_columns(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE generation (uid TEXT PRIMARY KEY, state TEXT NOT NULL, message TEXT NOT NULL DEFAULT '', result TEXT, attempts INTEGER NOT NULL DEFAULT 0,"
                      " manual_review INTEGER NOT NULL DEFAULT 0, cache_key TEXT, updated_at TEXT NOT NULL);"
                      "CREATE TABLE jobs (id TEXT PRIMARY KEY, project_id INTEGER NOT NULL, stage TEXT NOT NULL, part_a_done INTEGER NOT NULL DEFAULT 0, error TEXT,"
                      " created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
                      "INSERT INTO generation (uid, state, updated_at) VALUES ('x', 'queued', 't');")
    con.commit()
    con.close()
    db = Database(path)
    assert db.one("SELECT priority FROM generation WHERE uid='x'")["priority"] == 1
    db.run("INSERT INTO jobs (id, project_id, stage, created_at, updated_at) VALUES ('j',1,'collect','t','t')")
    assert db.one("SELECT policy FROM jobs WHERE id='j'")["policy"] == "smart"


# ------------------------------------------------------------------------------------------------------------------ policies through the API
@api
def test_smart_is_the_default_and_queues_only_p1(make_client):
    backend = MockBackend(mock_reply)
    c = make_client(backend=backend)
    job = post_analyze(c)  # no policy parameter
    assert job["policy"] == "smart"
    assert c.app.state.manager.wait_idle(60)
    cls = sample_classes(c)
    st = states(c)
    for uid, k in cls.items():
        assert st[uid] == ("done" if k == 1 else "not_requested"), (uid, k, st[uid])
    d = drafts(c)
    assert d["generated"] == sum(1 for k in cls.values() if k == 1) and d["not_generated"] == sum(1 for k in cls.values() if k != 1)
    assert d["generated"] + d["not_generated"] == d["total"] == 3 and d["in_progress"] == 0
    assert len(backend.calls) == d["generated"]


@api
def test_all_queues_everything_ordered_p1_p2_p3(make_client):
    backend = MockBackend(mock_reply)
    c = make_client(backend=backend)
    c.app.state.manager.set_paused(True)  # collect the whole queue first, then let it run
    post_analyze(c, "all")
    cls = sample_classes(c)
    assert drafts(c)["queued"] == 3 and len(backend.calls) == 0
    c.app.state.manager.set_paused(False)
    assert c.app.state.manager.wait_idle(60)
    texts = {i["text"]: i["uid"] for i in reqs(c)["items"]}
    order = [texts[user.split("Requirement: ", 1)[1]] for _, user in backend.calls]
    assert [cls[u] for u in order] == sorted(cls[u] for u in order)  # P1 first, then P2, then P3
    assert set(order) == set(cls) and drafts(c)["not_generated"] == 0


@api
def test_manual_queues_nothing_and_shows_not_generated(make_client):
    backend = MockBackend(mock_reply)
    c = make_client(backend=backend)
    post_analyze(c, "manual")
    assert c.app.state.manager.wait_idle(60)
    assert set(states(c).values()) == {"not_requested"} and not backend.calls
    d = drafts(c)
    assert d["not_generated"] == 3 and d["generated"] == 0 and d["in_progress"] == 0 and d["needs_clarification"] == 0 and d["failed"] == 0


@api
def test_invalid_policy_is_refused_and_the_job_reports_its_policy(make_client):
    c = make_client()
    upload(c, [("sample_srs.txt", SAMPLE, "text/plain")])
    r = c.post("/api/projects/1/analyze", params={"policy": "everything"})
    assert r.status_code == 400 and error_of(r)["code"] == "invalid_parameter"
    assert post_analyze(c, "Manual", upload_sample=False)["policy"] == "manual"


@api
def test_cached_replies_never_run_again_whatever_the_policy(make_client):
    backend = MockBackend(mock_reply)
    c = make_client(backend=backend)
    post_analyze(c, "all")
    assert c.app.state.manager.wait_idle(60)
    n = len(backend.calls)
    assert n == 3
    post_analyze(c, "manual", upload_sample=False)  # same texts: shown from the cache although nothing is queued
    assert c.app.state.manager.wait_idle(60)
    assert len(backend.calls) == n and set(states(c).values()) == {"done"}
    # a requirement without a row but with a cached reply gets it from the "Generate draft" button, without calling the model
    uid = next(iter(states(c)))
    c.app.state.db.run("DELETE FROM generation WHERE uid=?", (uid,))
    assert states(c)[uid] == "not_requested"
    r = c.post(f"/api/requirements/{uid}/generate")
    assert r.status_code == 202 and r.json() == {"uid": uid, "generation_state": "done"}
    assert len(backend.calls) == n
    assert c.get(f"/api/requirements/{uid}").json()["generation"]["message"] == "from cache"


@api
def test_generate_for_one_requirement_and_generate_all_remaining(make_client):
    backend = MockBackend(mock_reply)
    c = make_client(backend=backend)
    post_analyze(c, "manual")
    first = next(iter(states(c)))
    r = c.post(f"/api/requirements/{first}/generate")
    assert r.status_code == 202 and r.json()["generation_state"] == "queued"
    assert c.app.state.manager.wait_idle(60)
    assert states(c)[first] == "done" and len(backend.calls) == 1
    r = c.post("/api/projects/1/generate")
    assert r.status_code == 202 and r.json() == {"queued": 2}  # only the ones without a draft
    assert c.app.state.manager.wait_idle(60)
    assert set(states(c).values()) == {"done"} and len(backend.calls) == 3
    assert c.post("/api/projects/1/generate").json() == {"queued": 0}
    assert error_of(c.post("/api/projects/99/generate"))["code"] == "project_not_found"


@api
def test_summary_counts_generated_clarification_not_generated_and_failed_apart(make_client):
    reply = json.dumps({"status": "needs_clarification", "clarification_questions": ["What do you mean?"], "rationale": "Vague."})
    c = make_client(backend=MockBackend([reply]))
    post_analyze(c, "all")
    assert c.app.state.manager.wait_idle(60)
    d = drafts(c)
    assert d["needs_clarification"] == 3 and d["generated"] == 0 and d["not_generated"] == 0 and d["failed"] == 0 and d["total"] == 3
    c.app.state.db.run("UPDATE generation SET state='failed' WHERE uid='p1-REQ-001'")
    c.app.state.db.run("DELETE FROM generation WHERE uid='p1-REQ-002'")
    d = drafts(c)
    assert (d["needs_clarification"], d["failed"], d["not_generated"], d["generated"]) == (1, 1, 1, 0)


# ------------------------------------------------------------------------------------------------------------------ pause / resume / restart
@api
def test_pause_stops_new_items_but_the_one_in_flight_finishes(make_client):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def slow(system, user):
        calls.append(user)
        entered.set()
        assert release.wait(30)
        return mock_reply(system, user)

    c = make_client(backend=MockBackend(slow))
    post_analyze(c, "all")
    assert entered.wait(30)
    r = c.post("/api/projects/1/generation/pause")
    assert r.status_code == 200 and r.json() == {"paused": True}
    release.set()
    for _ in range(100):  # the in-flight item completes
        if drafts(c)["generated"] == 1:
            break
        threading.Event().wait(0.1)
    d = drafts(c)
    assert d["generated"] == 1 and d["queued"] == 2 and d["paused"] is True and len(calls) == 1
    threading.Event().wait(1.0)
    assert len(calls) == 1 and drafts(c)["queued"] == 2  # nothing new is taken while paused
    assert c.post("/api/projects/1/generation/resume").json() == {"paused": False}
    assert c.app.state.manager.wait_idle(60)
    d = drafts(c)
    assert d["generated"] == 3 and d["queued"] == 0 and d["paused"] is False and len(calls) == 3


@api
def test_a_paused_queue_does_not_block_deleting_sources(make_client):
    c = make_client()
    c.app.state.manager.set_paused(True)
    post_analyze(c, "all")
    assert drafts(c)["queued"] == 3
    assert c.delete("/api/projects/1/sources").status_code == 204  # waiting items are dropped with their requirements
    assert reqs(c)["total"] == 0


@api
def test_pause_flag_and_queue_survive_a_restart(tmp_path, make_client):
    c = make_client(workspace=tmp_path / "wsr")
    c.app.state.manager.set_paused(True)
    post_analyze(c, "all")
    assert drafts(c)["queued"] == 3
    backend = MockBackend(mock_reply)
    c2 = make_client(workspace=tmp_path / "wsr", backend=backend)  # restart on the same workspace
    d = drafts(c2)
    assert d["paused"] is True and d["queued"] == 3 and not backend.calls  # still paused, still waiting
    assert c2.post("/api/projects/1/generation/resume").status_code == 200
    assert c2.app.state.manager.wait_idle(60)
    assert drafts(c2)["generated"] == 3 and drafts(c2)["queued"] == 0 and len(backend.calls) == 3


@api
def test_restart_requeues_with_the_saved_priority(tmp_path, make_client):
    c = make_client(workspace=tmp_path / "wsp")
    c.app.state.manager.set_paused(True)
    post_analyze(c, "all")
    cls = sample_classes(c)
    rows = c.app.state.db.all("SELECT uid, priority FROM generation")
    assert {r["uid"]: r["priority"] for r in rows} == cls
    c2 = make_client(workspace=tmp_path / "wsp")
    queued = []
    while not c2.app.state.manager.queue.empty():
        queued.append(c2.app.state.manager.queue.get_nowait())
    assert [q[0] for q in queued] == sorted(cls.values())


@api
def test_eta_is_hidden_until_three_real_latencies_exist(make_client):
    c = make_client()
    m = c.app.state.manager
    m.set_paused(True)
    post_analyze(c, "all")
    assert drafts(c)["queued"] == 3 and ETA_MIN_SAMPLES == 3
    db = c.app.state.db

    def add(*seconds):
        for s in seconds:
            db.run("INSERT INTO gen_latency (backend, model, seconds, created_at) VALUES (?,?,?,?)", (m.backend_name, m.model_name, s, now()))

    d = drafts(c)
    assert d["eta_seconds"] is None and d["latency_samples"] == 0
    add(10, 20)
    d = drafts(c)
    assert d["eta_seconds"] is None and d["latency_samples"] == 2  # two samples are not enough
    add(30)
    d = drafts(c)
    assert d["latency_samples"] == 3 and d["eta_seconds"] == 60  # mean 20 s x 3 waiting
    db.run("INSERT INTO gen_latency (backend, model, seconds, created_at) VALUES ('other', 'other', 999, ?)", (now(),))  # another model is ignored
    add(*[40] * 10)  # only the last 10 count
    d = drafts(c)
    assert d["latency_samples"] == 10 and d["eta_seconds"] == 120


@api
def test_real_latencies_are_recorded_by_the_worker_and_cache_hits_are_not(make_client):
    c = make_client()
    post_analyze(c, "all")
    assert c.app.state.manager.wait_idle(60)
    n = c.app.state.db.one("SELECT COUNT(*) n FROM gen_latency")["n"]
    assert n == 3
    post_analyze(c, "all", upload_sample=False)  # everything comes from the cache: no new latency
    assert c.app.state.manager.wait_idle(60)
    assert c.app.state.db.one("SELECT COUNT(*) n FROM gen_latency")["n"] == 3
    assert drafts(c)["eta_seconds"] is None  # nothing waiting


# ------------------------------------------------------------------------------------------------------------------ clarification flow
@api
def test_edited_decision_must_change_the_text(client):
    analyze(client)
    uid = "REQ-001"
    original = client.get(f"/api/requirements/{uid}").json()["original_text"]
    r = client.post(f"/api/requirements/{uid}/decision", json={"decision": "edited", "edited_text": original})
    assert r.status_code == 400 and error_of(r)["code"] == "edited_text_unchanged"
    r = client.post(f"/api/requirements/{uid}/decision", json={"decision": "edited", "edited_text": "  " + original.replace(" ", "   ") + " "})
    assert r.status_code == 400 and error_of(r)["code"] == "edited_text_unchanged"  # only spacing differs
    assert client.get(f"/api/requirements/{uid}").json()["decision"] is None  # nothing was recorded
    assert client.post(f"/api/requirements/{uid}/decision", json={"decision": "accepted"}).status_code == 200  # unchanged text is an acceptance
    r = client.post(f"/api/requirements/{uid}/decision", json={"decision": "edited", "edited_text": original + " Response time is 2 seconds."})
    assert r.status_code == 200 and r.json()["decision"] == "edited"


def clarifying_backend(calls):
    """Needs clarification for the original wording; a valid draft for the rewritten one."""
    def reply(system, user):
        calls.append(user)
        if "within 2 seconds" in user:
            return json.dumps({"status": "ok", "user_story": "As a user, I want search to answer within 2 seconds, so that I can keep working.",
                               "technical_task": "Return search results within 2 seconds.",
                               "acceptance_criteria": ["Given a search, when it is run, then results arrive within 2 seconds.", "Given load, when searching, then 2 seconds is kept."],
                               "rationale": "Role assumed: user."})
        return json.dumps({"status": "needs_clarification", "clarification_questions": ["What does quickly mean?"], "rationale": "Not measurable."})
    return MockBackend(reply)


@api
def test_regenerate_uses_the_clarified_text_and_keeps_the_original(make_client):
    calls = []
    c = make_client(backend=clarifying_backend(calls))
    text = "The system shall return search results quickly."
    assert upload(c, [("a.txt", (text + "\n").encode(), "text/plain")]).status_code == 201
    assert c.post("/api/projects/1/analyze", params={"policy": "all"}).status_code == 202
    assert c.app.state.manager.wait_idle(60)
    d = c.get("/api/requirements/REQ-001").json()
    assert d["generation"]["state"] == "needs_clarification" and d["generation"]["generated_from"] == "original"
    clarified = "The system shall return search results within 2 seconds."
    assert c.post("/api/requirements/REQ-001/decision", json={"decision": "edited", "edited_text": clarified}).status_code == 200
    assert c.post("/api/requirements/REQ-001/generate").status_code == 202
    assert c.app.state.manager.wait_idle(60)
    d = c.get("/api/requirements/REQ-001").json()
    g = d["generation"]
    assert g["state"] == "done" and g["generated_from"] == "clarified"
    assert clarified in calls[-1] and text not in calls[-1]  # the model saw the user's wording
    assert d["original_text"] == text and d["decision"]["edited_text"] == clarified and len(d["decision_history"]) == 1  # original and history stay
    assert g["numbers_not_in_source"] == []  # "2" is checked against the clarified text, which contains it
    # a plain regenerate without an edit goes back to the original text
    c.app.state.db.run("DELETE FROM decisions WHERE uid='p1-REQ-001'")
    assert c.post("/api/requirements/REQ-001/generate").status_code == 202
    assert c.app.state.manager.wait_idle(60)
    assert c.get("/api/requirements/REQ-001").json()["generation"]["generated_from"] == "original"


@api
def test_clarified_text_has_its_own_cache_entry(make_client):
    calls = []
    c = make_client(backend=clarifying_backend(calls))
    assert upload(c, [("a.txt", b"The system shall return search results quickly.\n", "text/plain")]).status_code == 201
    c.post("/api/projects/1/analyze", params={"policy": "all"})
    assert c.app.state.manager.wait_idle(60)
    n = len(calls)
    c.post("/api/requirements/REQ-001/decision", json={"decision": "edited", "edited_text": "The system shall return search results within 2 seconds."})
    c.post("/api/requirements/REQ-001/generate")
    assert c.app.state.manager.wait_idle(60)
    assert len(calls) == n + 1  # the clarified wording is a new text: one real call
    c.post("/api/projects/1/analyze", params={"policy": "all"})  # analysing again: both wordings are cached, nothing runs
    assert c.app.state.manager.wait_idle(60)
    assert len(calls) == n + 1 and c.get("/api/requirements/REQ-001").json()["generation"]["generated_from"] == "clarified"
