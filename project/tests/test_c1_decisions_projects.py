"""Component 1 API: one current decision per requirement (upsert, delete, alias, audit), the migration of older workspaces, projects (keys, rename, archive),
publishing under the project's own key, the one-call overview, and neutral wording.

The graph is always a fake driver (see test_c1_neo4j.py) and the Neo4j settings are isolated by its autouse fixture: no real database is touched.
"""
import json
import sqlite3

import pytest

from agents.requirement_agent.api.db import Database
from tests.test_c1_api import make_client  # noqa: F401  (fixture)
from tests.test_c1_neo4j import Driver, ServiceUnavailable, isolated_settings, raising, seed, wire  # noqa: F401  (isolated_settings is autouse there)
from agents.requirement_agent.api import neo4j_store

EDITED = "The report shall be readable at 100% zoom."


def err(r):
    body = r.json()
    assert set(body) == {"error"}, body
    return body["error"]["code"]


@pytest.fixture
def c(make_client):  # noqa: F811
    """A client whose project 1 holds the seeded workspace (4 requirements, 2 sources, 3 decisions, drafts) without running the models."""
    client = make_client()
    db = client.app.state.db
    seed(db, project=False)
    db.run("DELETE FROM decisions")  # the tests set their own
    return client


# ------------------------------------------------------------------------------------------------------------------ decisions
def test_put_creates_and_replaces_the_one_decision(c):
    assert c.get("/api/requirements/REQ-003/decision").json() == {"uid": "p1-REQ-003", "decision": "pending", "edited_text": None, "note": None, "updated_at": None}
    r = c.put("/api/requirements/REQ-003/decision", json={"decision": "accepted", "note": "first"})
    assert r.status_code == 200 and r.json()["decision"] == "accepted" and [h["decision"] for h in r.json()["history"]] == ["accepted"]
    r = c.put("/api/requirements/REQ-003/decision", json={"decision": "edited", "edited_text": f"  {EDITED} ", "note": "second"})
    assert r.status_code == 200 and r.json()["decision"] == "edited" and r.json()["edited_text"] == EDITED
    assert [h["decision"] for h in r.json()["history"]] == ["edited"]  # the deprecated field holds the current decision only
    got = c.get("/api/requirements/REQ-003/decision").json()
    assert (got["decision"], got["edited_text"], got["note"]) == ("edited", EDITED, "second")
    d = c.get("/api/requirements/REQ-003").json()
    assert d["decision"]["decision"] == "edited" and len(d["decision_history"]) == 1 and d["text"] == "The report shall be easy to read."
    assert c.app.state.db.one("SELECT COUNT(*) n FROM decisions WHERE uid='p1-REQ-003'")["n"] == 1
    rows = {i["id"]: i["decision"] for i in c.get("/api/projects/1/requirements").json()["items"]}
    assert rows["REQ-003"] == "edited" and rows["REQ-001"] is None
    assert c.get("/api/projects/1/summary").json()["decided"] == 1


def test_edited_needs_a_real_change(c):
    assert err(c.put("/api/requirements/REQ-003/decision", json={"decision": "edited"})) == "edited_text_required"
    assert err(c.put("/api/requirements/REQ-003/decision", json={"decision": "edited", "edited_text": "   "})) == "edited_text_required"
    assert err(c.put("/api/requirements/REQ-003/decision", json={"decision": "edited", "edited_text": "The report   shall be easy to read. "})) == "edited_text_unchanged"
    assert c.put("/api/requirements/REQ-003/decision", json={"decision": "maybe"}).status_code == 422
    assert c.put("/api/requirements/NOPE/decision", json={"decision": "accepted"}).status_code == 404
    assert c.get("/api/requirements/REQ-003/decision").json()["decision"] == "pending"  # nothing was stored by the refused calls


def test_delete_returns_to_pending_and_can_be_repeated(c):
    c.put("/api/requirements/REQ-001/decision", json={"decision": "rejected", "note": "n"})
    assert c.delete("/api/requirements/REQ-001/decision").status_code == 204
    assert c.get("/api/requirements/REQ-001/decision").json()["decision"] == "pending"
    d = c.get("/api/requirements/REQ-001").json()
    assert d["decision"] is None and d["decision_history"] == []
    assert c.get("/api/projects/1/summary").json()["decided"] == 0
    assert c.delete("/api/requirements/REQ-001/decision").status_code == 204  # already pending: same result
    assert c.delete("/api/requirements/NOPE/decision").status_code == 404


def test_post_is_an_alias_of_put_and_is_marked_deprecated(c):
    a = c.post("/api/requirements/REQ-001/decision", json={"decision": "accepted", "note": "via post"})
    b = c.post("/api/requirements/REQ-001/decision", json={"decision": "rejected"})
    assert a.status_code == b.status_code == 200 and b.json()["decision"] == "rejected" and len(b.json()["history"]) == 1
    assert c.get("/api/requirements/REQ-001/decision").json()["decision"] == "rejected"
    assert c.app.state.db.one("SELECT COUNT(*) n FROM decisions WHERE uid='p1-REQ-001'")["n"] == 1
    paths = c.app.openapi()["paths"]["/api/requirements/{rid}/decision"]
    assert paths["post"].get("deprecated") is True and set(paths) == {"get", "put", "delete", "post"}
    schemas = c.app.openapi()["components"]["schemas"]
    assert schemas["DecisionOut"]["properties"]["history"].get("deprecated") is True
    assert schemas["RequirementDetail"]["properties"]["decision_history"].get("deprecated") is True


def test_replaced_and_removed_decisions_go_to_the_audit_table_and_nowhere_else(c):
    secret = "OLD-NOTE-never-returned"
    c.put("/api/requirements/REQ-003/decision", json={"decision": "accepted", "note": secret})
    c.put("/api/requirements/REQ-003/decision", json={"decision": "rejected", "note": "second"})
    c.put("/api/requirements/REQ-003/decision", json={"decision": "edited", "edited_text": EDITED, "note": "third"})
    c.delete("/api/requirements/REQ-003/decision")
    db = c.app.state.db
    audit = db.all("SELECT decision, note, reason FROM decision_audit WHERE uid='p1-REQ-003' ORDER BY id")
    assert [(a["decision"], a["reason"]) for a in audit] == [("accepted", "replaced"), ("rejected", "replaced"), ("edited", "removed")] and audit[0]["note"] == secret
    c.put("/api/requirements/REQ-003/decision", json={"decision": "accepted", "note": "current"})
    seen = [
        c.get("/api/requirements/REQ-003").text, c.get("/api/requirements/REQ-003/decision").text, c.get("/api/projects/1/requirements").text,
        c.get("/api/projects/1/summary").text, c.get("/api/projects/1/overview").text, c.get("/api/projects").text,
        c.get("/api/projects/1/export", params={"format": "json"}).text, c.get("/api/projects/1/export", params={"format": "csv"}).text,
        json.dumps(neo4j_store.build_bundle(db, 1, "demo-project", "Core Banking Platform").as_dict()),
    ]
    for text in seen:
        assert secret not in text and "decision_audit" not in text and "superseded" not in text
    assert not [p for p in c.app.openapi()["paths"] if "audit" in p]


def test_exports_progress_and_publish_read_the_single_decision(c):
    c.put("/api/requirements/REQ-003/decision", json={"decision": "accepted"})
    c.put("/api/requirements/REQ-003/decision", json={"decision": "edited", "edited_text": EDITED})
    export = {r["id"]: r for r in c.get("/api/projects/1/export", params={"format": "json"}).json()["requirements"]}
    assert export["REQ-003"]["decision"]["status"] == "edited" and export["REQ-003"]["final_text"] == EDITED
    assert c.get("/api/projects/1/summary").json()["decided"] == 1
    bundle = neo4j_store.build_bundle(c.app.state.db, 1, "demo-project", "x")
    req = {r["id"]: r["props"] for s in bundle.sources for r in s.requirements}["demo-project:src1:REQ-003"]
    assert req["status"] == "edited" and req["final_text"] == EDITED


def test_an_older_workspace_keeps_the_latest_decision_and_moves_the_rest_to_audit(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TEXT NOT NULL);"
        "INSERT INTO projects (name, created_at) VALUES ('Core Banking Platform','t'), ('Core Banking Platform','t'), ('!!!','t');"
        "CREATE TABLE decisions (uid TEXT PRIMARY KEY, decision TEXT NOT NULL, edited_text TEXT, note TEXT, updated_at TEXT NOT NULL);"
        "CREATE TABLE decision_history (id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT NOT NULL, decision TEXT NOT NULL, edited_text TEXT, note TEXT, created_at TEXT NOT NULL);"
        "INSERT INTO decisions VALUES ('u1','edited','new text','n3','t3'), ('u2','accepted',NULL,NULL,'t1');"
        "INSERT INTO decision_history (uid, decision, edited_text, note, created_at) VALUES "
        "('u1','accepted',NULL,'n1','t1'), ('u1','rejected',NULL,'n2','t2'), ('u1','edited','new text','n3','t3'), ('u2','accepted',NULL,NULL,'t1'),"
        "('u3','rejected',NULL,'only history','t5'), ('u3','accepted',NULL,'latest of u3','t6');")
    con.commit()
    con.close()
    for _ in range(2):  # the second start changes nothing
        db = Database(path)
        assert {d["uid"]: (d["decision"], d["note"]) for d in db.all("SELECT * FROM decisions")} == {"u1": ("edited", "n3"), "u2": ("accepted", None), "u3": ("accepted", "latest of u3")}
        assert [(a["uid"], a["decision"], a["reason"]) for a in db.all("SELECT * FROM decision_audit ORDER BY id")] == \
            [("u1", "accepted", "migrated"), ("u1", "rejected", "migrated"), ("u3", "rejected", "migrated")]
        assert not db.one("SELECT name FROM sqlite_master WHERE name='decision_history'")
        keys = [p["project_key"] for p in db.all("SELECT * FROM projects ORDER BY id")]
        assert keys == ["demo-project", "core-banking-platform", "project-3"]
        assert [p["archived"] for p in db.all("SELECT * FROM projects")] == [0, 0, 0]


# ------------------------------------------------------------------------------------------------------------------ projects
def test_the_default_project_has_the_demo_key_and_counts(c):
    p = c.get("/api/projects").json()
    assert len(p) == 1 and p[0]["project_key"] == "demo-project" and p[0]["archived"] is False and p[0]["id"] == 1
    assert (p[0]["sources"], p[0]["requirements"]) == (2, 4)
    assert p[0]["decisions"] == {"accepted": 0, "edited": 0, "rejected": 0, "pending": 4}
    assert p[0]["last_analysis_at"] is None and p[0]["last_published_at"] is None and p[0]["out_of_date"] is True


def test_project_counts_follow_decisions_analysis_and_publish(c):
    db = c.app.state.db
    db.run("INSERT INTO jobs (id, project_id, stage, part_a_done, created_at, updated_at, policy) VALUES ('j1',1,'share',1,'2026-10-01T00:00:00+00:00','2026-10-01T00:05:00+00:00','smart')")
    db.run("INSERT INTO jobs (id, project_id, stage, part_a_done, created_at, updated_at, policy) VALUES ('j2',1,'collect',0,'2026-10-02T00:00:00+00:00','2026-10-02T00:05:00+00:00','smart')")
    c.put("/api/requirements/REQ-001/decision", json={"decision": "accepted"})
    c.put("/api/requirements/REQ-002/decision", json={"decision": "rejected"})
    wire(c)
    p = c.get("/api/projects").json()[0]
    assert p["decisions"] == {"accepted": 1, "edited": 0, "rejected": 1, "pending": 2} and p["last_analysis_at"] == "2026-10-01T00:05:00+00:00"  # a job that did not finish does not count
    assert c.post("/api/projects/1/publish/neo4j").status_code == 200
    p = c.get("/api/projects").json()[0]
    assert p["out_of_date"] is False and p["last_published_at"]
    c.put("/api/requirements/REQ-004/decision", json={"decision": "accepted"})
    assert c.get("/api/projects").json()[0]["out_of_date"] is True


def test_create_a_project_gets_a_unique_immutable_key(c):
    r = c.post("/api/projects", json={"name": "  Second   Project "})
    assert r.status_code == 201
    second = r.json()
    assert (second["name"], second["project_key"], second["archived"], second["requirements"]) == ("Second Project", "second-project", False, 0)
    assert second["decisions"] == {"accepted": 0, "edited": 0, "rejected": 0, "pending": 0} and second["out_of_date"] is True
    assert err(c.post("/api/projects", json={"name": "second project"})) == "project_name_taken"  # unique among active projects, ignoring case
    other = c.post("/api/projects", json={"name": "Second-Project!"}).json()  # another name with the same slug
    assert other["project_key"] == "second-project-2"
    for bad in ("a", " a ", "x" * 81, "   "):
        r = c.post("/api/projects", json={"name": bad})
        assert r.status_code == 422 and err(r) == "validation_error", bad
    assert c.post("/api/projects", json={"name": "ab"}).status_code == 201 and c.post("/api/projects", json={"name": "y" * 80}).status_code == 201
    keys = [p["project_key"] for p in c.get("/api/projects").json()]
    assert len(keys) == len(set(keys))
    with pytest.raises(sqlite3.IntegrityError):  # the database itself refuses a duplicate key
        c.app.state.db.run("INSERT INTO projects (name, created_at, project_key, archived) VALUES ('dup','t','demo-project',0)")


def test_rename_changes_the_name_never_the_key(c):
    second = c.post("/api/projects", json={"name": "Second Project"}).json()
    r = c.patch(f"/api/projects/{second['id']}", json={"name": "Renamed One", "project_key": "hacked"})
    assert r.status_code == 200 and (r.json()["name"], r.json()["project_key"]) == ("Renamed One", "second-project")
    assert c.patch(f"/api/projects/{second['id']}", json={"name": "Renamed One"}).status_code == 200  # the same name again is fine
    assert err(c.patch(f"/api/projects/{second['id']}", json={"name": "core banking platform"})) == "project_name_taken"
    assert c.patch(f"/api/projects/{second['id']}", json={"name": "x"}).status_code == 422
    assert c.patch("/api/projects/99", json={"name": "Whatever"}).status_code == 404
    assert [p["name"] for p in c.get("/api/projects").json()] == ["Core Banking Platform", "Renamed One"]


def test_archive_is_soft_and_a_name_is_free_again_while_archived(c):
    second = c.post("/api/projects", json={"name": "Second Project"}).json()
    a = c.post(f"/api/projects/{second['id']}/archive")
    assert a.status_code == 200 and a.json()["archived"] is True and a.json()["project_key"] == "second-project"
    assert [p["id"] for p in c.get("/api/projects").json()] == [1]
    listed = c.get("/api/projects", params={"include_archived": "true"}).json()
    assert [(p["id"], p["archived"]) for p in listed] == [(1, False), (second["id"], True)]
    assert c.get(f"/api/projects/{second['id']}/summary").status_code == 200  # nothing was deleted
    again = c.post("/api/projects", json={"name": "Second Project"}).json()  # the name is free while the first is archived
    assert again["project_key"] == "second-project-2"
    assert err(c.post(f"/api/projects/{second['id']}/unarchive")) == "project_name_taken"
    assert c.post(f"/api/projects/{again['id']}/archive").status_code == 200
    u = c.post(f"/api/projects/{second['id']}/unarchive")
    assert u.status_code == 200 and u.json()["archived"] is False
    assert c.post("/api/projects/99/archive").status_code == 404 and c.post("/api/projects/99/unarchive").status_code == 404


# ------------------------------------------------------------------------------------------------------------------ publish under the project's key
def test_publish_uses_the_project_key_and_name_and_refuses_another_id(c):
    driver = wire(c)
    r = c.post("/api/projects/1/publish/neo4j")
    assert r.status_code == 200 and r.json()["project_id"] == "demo-project"
    writes = len(driver.log)
    for body in ({"project_id": "made-up"}, {"project_id": "Demo-Project"}, {"project_id": "demo-project", "project_name": "Another name"}, {"project_name": "Other"}):
        r = c.post("/api/projects/1/publish/neo4j", json=body)
        assert r.status_code == 422, body
        assert err(r) in ("project_key_mismatch", "project_name_mismatch")
    assert len(driver.log) == writes  # nothing was sent for the refused requests
    assert c.post("/api/projects/1/publish/neo4j", json={"project_id": "demo-project", "project_name": "Core  Banking Platform"}).status_code == 200
    assert err(c.get("/api/projects/1/publish/neo4j", params={"project_id": "made-up"})) == "project_key_mismatch"
    assert c.get("/api/projects/1/publish/neo4j", params={"project_id": "demo-project"}).json()["project_id"] == "demo-project"
    # another project publishes under its own key; renaming it does not change the key
    second = c.post("/api/projects", json={"name": "Second Project"}).json()
    r = c.post(f"/api/projects/{second['id']}/publish/neo4j")
    assert r.status_code == 200 and r.json()["project_id"] == "second-project"
    c.patch(f"/api/projects/{second['id']}", json={"name": "Second Renamed"})
    assert c.get(f"/api/projects/{second['id']}/publish/neo4j").json()["project_id"] == "second-project"
    assert c.get(f"/api/projects/{second['id']}/publish/neo4j").json()["out_of_date"] is True  # the name is part of what is published
    assert err(c.post(f"/api/projects/{second['id']}/publish/neo4j", json={"project_id": "demo-project"})) == "project_key_mismatch"


# ------------------------------------------------------------------------------------------------------------------ overview
def test_overview_in_one_call(c):
    db = c.app.state.db
    db.run("INSERT INTO jobs (id, project_id, stage, part_a_done, created_at, updated_at, policy) VALUES ('j1',1,'share',1,'2026-10-01T00:00:00+00:00','2026-10-01T00:05:00+00:00','smart')")
    c.put("/api/requirements/REQ-001/decision", json={"decision": "accepted"})
    db.run("INSERT INTO decisions (uid, decision, edited_text, note, updated_at) VALUES ('p1-REQ-003','edited',?,NULL,'2026-10-01T00:06:00+00:00')", (EDITED,))  # stored directly: saving it would queue a new draft
    c.put("/api/requirements/REQ-004/decision", json={"decision": "rejected"})
    o = c.get("/api/projects/1/overview")
    assert o.status_code == 200
    o = o.json()
    assert o["project"] == {"id": 1, "project_key": "demo-project", "name": "Core Banking Platform", "archived": False}
    assert o["counts"]["requirements"] == 4 and o["counts"]["conflicts"] == 0 and o["counts"]["duplicates"] == 1
    assert o["counts"]["ambiguities"] == {"total": 2, "detected": 1, "asked_by_ai": 1}
    assert o["counts"]["drafts"] == {"total": 4, "done": 1, "ready": 1, "needs_clarification": 1, "waiting": 0, "failed": 1, "not_generated": 1, "manual_review": 0}
    assert o["decisions"] == {"accepted": 1, "edited": 1, "rejected": 1, "pending": 1, "decided": 3, "percent_decided": 75.0}
    assert o["sources"] == {"count": 2, "by_type": {"srs": 1, "brd": 1}, "total_size_bytes": 20, "latest_upload_at": "2026-10-01T00:00:00+00:00"}
    assert o["last_analysis_at"] == "2026-10-01T00:05:00+00:00"
    assert o["generation"]["state"] == "idle" and o["generation"]["target"] == "device" and o["generation"]["in_progress"] == 0
    assert o["neo4j"]["configured"] is False and o["neo4j"]["reachable"] is False and o["neo4j"]["error"] == "neo4j_unconfigured" and o["neo4j"]["project_id"] == "demo-project"
    assert c.get("/api/projects/99/overview").status_code == 404
    c.post("/api/projects/1/generation/pause")
    assert c.get("/api/projects/1/overview").json()["generation"]["state"] == "paused"


def test_overview_reports_the_graph_and_never_fails_when_it_is_down(c):
    wire(c)
    assert c.post("/api/projects/1/publish/neo4j").status_code == 200
    g = c.get("/api/projects/1/overview").json()["neo4j"]
    assert (g["configured"], g["reachable"], g["out_of_date"], g["error"]) == (True, True, False, None) and g["last_published_at"]
    c.put("/api/requirements/REQ-002/decision", json={"decision": "accepted"})
    assert c.get("/api/projects/1/overview").json()["neo4j"]["out_of_date"] is True
    c.app.state.neo4j._driver_factory = raising(ServiceUnavailable("db.internal.example down"))
    r = c.get("/api/projects/1/overview")
    g = r.json()["neo4j"]
    assert r.status_code == 200 and g["reachable"] is False and g["error"] == "neo4j_unreachable" and "db.internal.example" not in r.text
    assert r.json()["counts"]["requirements"] == 4  # the rest of the overview is intact

    def boom(*a, **k):
        raise RuntimeError("unexpected")
    c.app.state.neo4j.status = boom
    r = c.get("/api/projects/1/overview")
    assert r.status_code == 200 and r.json()["neo4j"]["reachable"] is False and r.json()["neo4j"]["error"] == "neo4j_status_failed"


def test_overview_of_an_empty_project(make_client):  # noqa: F811
    c = make_client()
    o = c.get("/api/projects/1/overview").json()
    assert o["counts"]["requirements"] == 0 and o["decisions"]["percent_decided"] == 0.0 and o["sources"]["count"] == 0 and o["sources"]["latest_upload_at"] is None
    assert o["last_analysis_at"] is None and o["counts"]["drafts"]["total"] == 0


# ------------------------------------------------------------------------------------------------------------------ wording
def test_user_visible_text_is_in_neutral_product_language(c):
    banned = ("Part A", "Part B", "c1-req", "ollama", "Ollama", "RVU", "detector", "Component 1", "the API")
    d = c.get("/api/requirements/REQ-003").json()
    texts = [d["explanation"], c.get("/api/projects/1/export", params={"format": "json"}).json()["note"],
             c.post("/api/engine/test", json={"target": "device"}).json()["detail"]]
    for text in texts:
        for word in banned:
            assert word not in text, (word, text)
    assert "automatic checks" in d["explanation"] or d["findings"]
    paths = c.app.openapi()["paths"]
    for path in ("/api/projects/{pid}/overview", "/api/projects/{pid}/archive", "/api/projects/{pid}/unarchive"):
        assert path in paths and "patch" in paths["/api/projects/{pid}"]
