"""Component 1: publishing by document (T2).

The user publishes analysed documents, one by one, a selection, or a whole sprint; only published documents are active in the graph. No real database and no
real graph: the fake graph and driver of test_c1_neo4j.py, and a workspace seeded with two analysed documents (srs.txt with REQ-001..003, brd.txt with REQ-004).
"""
import sqlite3

import pytest

from agents.requirement_agent.api import neo4j_store
from agents.requirement_agent.api import neo4j_schema as S
from agents.requirement_agent.api.db import Database
from tests.test_c1_neo4j import CFG, isolated_settings, node, seed, wire  # noqa: F401  (isolated_settings is autouse there)
from tests.test_c1_api import make_client  # noqa: F401  (fixture)

SRS, BRD = 1, 2


def unpublish_all(db):
    db.run("UPDATE sources SET published=0, published_at=NULL")


@pytest.fixture
def c(make_client):
    """A client on a seeded workspace where nothing is published yet, wired to a fake graph."""
    client = make_client()
    db = client.app.state.db
    seed(db, project=False)
    db.ensure_planning(1)
    unpublish_all(db)
    client.driver = wire(client)
    return client


def active(graph, label):
    return sorted(k for (lab, k), p in graph.nodes.items() if lab == label and p.get("active", True))


def post(c, path, **body):
    return c.post(f"/api/projects/1/{path}", json=body)


# ------------------------------------------------------------------------------------------------------------------ the migration
def test_migration_keeps_the_analysed_documents_of_an_already_synced_project_published(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("""
CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE sources (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, filename TEXT NOT NULL, stored_path TEXT NOT NULL, ext TEXT NOT NULL,
    size_bytes INTEGER NOT NULL, pages INTEGER, warnings TEXT NOT NULL DEFAULT '[]', extracted TEXT NOT NULL, created_at TEXT NOT NULL, analysis_state TEXT NOT NULL DEFAULT 'not_analyzed');
CREATE TABLE publish_log (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, graph_project_id TEXT NOT NULL, graph_project_name TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL, published_at TEXT NOT NULL, seconds REAL NOT NULL, counts TEXT NOT NULL);
INSERT INTO projects VALUES (1, 'Synced', 't'), (2, 'Never synced', 't');
INSERT INTO sources (project_id, filename, stored_path, ext, size_bytes, extracted, created_at, analysis_state) VALUES
  (1, 'a.txt', '/x', '.txt', 1, '{}', 't', 'analyzed'), (1, 'b.txt', '/x', '.txt', 1, '{}', 't', 'not_analyzed'), (2, 'c.txt', '/x', '.txt', 1, '{}', 't', 'analyzed');
INSERT INTO publish_log (project_id, graph_project_id, content_hash, published_at, seconds, counts) VALUES (1, 'old', 'h', '2026-10-01T00:00:00+00:00', 0.1, '{}');
""")
    con.commit()
    con.close()
    db = Database(path)
    rows = {r["filename"]: (r["published"], r["published_at"]) for r in db.all("SELECT filename, published, published_at FROM sources")}
    assert rows == {"a.txt": (1, "2026-10-01T00:00:00+00:00"), "b.txt": (0, None), "c.txt": (0, None)}
    db.run("UPDATE sources SET published=0")
    assert Database(path).one("SELECT SUM(published) n FROM sources")["n"] == 0  # opened again: the backfill runs once, it does not publish again


def test_a_new_workspace_publishes_nothing_by_itself(c):
    assert [(s["published"], s["published_at"]) for s in c.get("/api/projects/1/sources").json()] == [(False, None)] * 2


# ------------------------------------------------------------------------------------------------------------------ publish and unpublish
def test_publish_one_document_syncs_it_and_unpublish_switches_it_off_without_deleting(c):
    g = c.driver.graph
    r = post(c, "publish", document_ids=[SRS])
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["action"] == "publish" and out["changed"] == [{"document_id": SRS, "name": "srs.txt"}] and out["skipped"] == []
    assert (out["published_documents"], out["total_documents"]) == (1, 2) and out["sync"] == {"state": "synced", "error": None}
    assert active(g, S.Label.SOURCE) == ["demo-project:src1"]
    assert len(active(g, S.Label.REQUIREMENT)) == 3 and all(k.startswith("demo-project:src1:") for k in active(g, S.Label.REQUIREMENT))
    shown = {s["id"]: s for s in c.get("/api/projects/1/sources").json()}
    assert shown[SRS]["published"] is True and shown[SRS]["published_at"] and shown[BRD]["published"] is False

    r = post(c, "unpublish", document_ids=[SRS])
    assert r.json()["changed"] == [{"document_id": SRS, "name": "srs.txt"}] and r.json()["published_documents"] == 0
    assert active(g, S.Label.SOURCE) == [] and active(g, S.Label.REQUIREMENT) == [] and active(g, S.Label.DRAFT) == [] and active(g, S.Label.ISSUE) == []
    assert len([k for (lab, k) in g.nodes if lab == S.Label.REQUIREMENT]) == 3  # still in the graph, as inactive nodes: never deleted
    assert node(g, S.Label.PROJECT, "demo-project")[S.ProjectP.NAME]  # the project node is always there
    assert not any(e["active"] for e in g.includes.values())


def test_publishing_again_makes_the_same_nodes_active_again(c):
    g = c.driver.graph
    post(c, "publish", document_ids=[SRS])
    post(c, "unpublish", document_ids=[SRS])
    post(c, "publish", document_ids=[SRS])
    assert len(active(g, S.Label.REQUIREMENT)) == 3 and len([k for (lab, k) in g.nodes if lab == S.Label.REQUIREMENT]) == 3


def test_only_published_documents_are_in_the_graph_and_in_includes_source(c):
    g = c.driver.graph
    post(c, "publish", document_ids=[BRD])
    assert active(g, S.Label.SOURCE) == ["demo-project:src2"] and active(g, S.Label.REQUIREMENT) == ["demo-project:src2:REQ-004"]
    assert {(sprint, src) for (sprint, src), e in g.includes.items() if e["active"]} == {("demo-project:sprint1", "demo-project:src2")}
    bundle = neo4j_store.build_bundle(c.app.state.db, 1, "demo-project", "Core Banking Platform")
    assert [sp["id"] for sp in bundle.sprints] == ["demo-project:sprint1"]  # sprints are always synced
    assert [s.source_id for s in bundle.sources] == ["demo-project:src2"] and bundle.held == []
    assert bundle.counts()[S.Rel.INCLUDES_SOURCE] == 1


def test_a_duplicate_link_to_an_unpublished_document_is_not_sent(c):
    post(c, "publish", document_ids=[SRS])  # REQ-001 and REQ-002 repeat each other, both in this document
    assert len(c.driver.graph.dups) == 1
    c.app.state.db.run("UPDATE requirements SET duplicate_matches=? WHERE uid='p1-REQ-004'", ('[{"id": "REQ-001", "uid": "p1-REQ-001", "similarity": 0.9}]',))
    bundle = neo4j_store.build_bundle(c.app.state.db, 1, "demo-project", "Core Banking Platform")
    assert len(bundle.duplicates) == 1  # REQ-004 is in a document that is not published


def test_skipped_documents_come_back_with_a_reason_and_nothing_else_changes(c):
    db = c.app.state.db
    db.run("INSERT INTO sources (id, project_id, filename, stored_path, ext, size_bytes, extracted, created_at, analysis_state) VALUES (3,1,'new.txt','/x','.txt',1,'{}','t','not_analyzed')")
    db.run("INSERT INTO sources (id, project_id, filename, stored_path, ext, size_bytes, extracted, created_at, analysis_state) VALUES (4,1,'busy.txt','/x','.txt',1,'{}','t','analyzing')")
    db.run("INSERT INTO sources (id, project_id, filename, stored_path, ext, size_bytes, extracted, created_at, analysis_state) VALUES (5,1,'bad.txt','/x','.txt',1,'{}','t','failed')")
    db.run("INSERT INTO sources (id, project_id, filename, stored_path, ext, size_bytes, extracted, created_at, analysis_state) VALUES (6,1,'empty.txt','/x','.txt',1,'{}','t','analyzed')")
    out = post(c, "publish", document_ids=[SRS, 3, 4, 5, 6, 99, SRS]).json()
    assert [d["document_id"] for d in out["changed"]] == [SRS]
    assert {d["document_id"]: d["reason"] for d in out["skipped"]} == {3: "not_analyzed", 4: "analyzing", 5: "failed", 6: "no_requirements", 99: "not_found"}
    assert all(d["message"] for d in out["skipped"]) and out["published_documents"] == 1
    again = post(c, "publish", document_ids=[SRS]).json()
    assert again["changed"] == [] and again["skipped"][0]["reason"] == "already_published"
    nothing = post(c, "unpublish", document_ids=[BRD]).json()
    assert nothing["changed"] == [] and nothing["skipped"][0]["reason"] == "not_published"


def test_publishing_a_whole_sprint_takes_its_analysed_documents_and_skips_the_rest(c):
    db = c.app.state.db
    db.run("INSERT INTO sprints (project_id, name, origin, confirmed, position, created_at) VALUES (1, 'Sprint 2', 'manual', 1, 2, 't')")
    db.run("INSERT INTO sources (id, project_id, filename, stored_path, ext, size_bytes, extracted, created_at, analysis_state, default_sprint_id) VALUES (3,1,'later.txt','/x','.txt',1,'{}','t','not_analyzed',2)")
    db.run("UPDATE sources SET default_sprint_id=2 WHERE id=?", (BRD,))
    out = post(c, "publish", sprint_id=2).json()
    assert [d["document_id"] for d in out["changed"]] == [BRD] and [(d["document_id"], d["reason"]) for d in out["skipped"]] == [(3, "not_analyzed")]
    assert active(c.driver.graph, S.Label.SOURCE) == ["demo-project:src2"]
    whole = post(c, "publish", sprint_id=1).json()
    assert [d["document_id"] for d in whole["changed"]] == [SRS] and whole["skipped"] == [] and whole["published_documents"] == 2
    gone = post(c, "unpublish", sprint_id=2).json()
    assert [d["document_id"] for d in gone["changed"]] == [BRD] and gone["skipped"][0]["reason"] == "not_published"


def test_bad_requests(c):
    assert post(c, "publish").status_code == 400 and post(c, "unpublish", document_ids=[]).status_code == 400
    assert post(c, "publish", sprint_id=99).status_code == 404 and c.post("/api/projects/99/publish", json={"document_ids": [1]}).status_code == 404
    assert post(c, "publish", sprint_id="x").status_code == 422


def test_the_change_is_audit_logged(c):
    post(c, "publish", document_ids=[SRS, 3])
    post(c, "unpublish", sprint_id=1)
    rows = c.app.state.db.all("SELECT action, scope, sprint_id, document_ids, skipped FROM publish_audit ORDER BY id")
    assert [(r["action"], r["scope"], r["sprint_id"]) for r in rows] == [("publish", "documents", None), ("unpublish", "sprint", 1)]
    assert rows[0]["document_ids"] == "[1]" and '"not_found"' in rows[0]["skipped"]


def test_an_unconfigured_graph_still_publishes_in_the_workspace_and_says_so(c):
    c.app.state.neo4j._load_config = lambda: type("Cfg", (), {"configured": False})()
    out = post(c, "publish", document_ids=[SRS]).json()
    assert out["changed"] and out["sync"] == {"state": "not_configured", "error": "neo4j_unconfigured"}
    assert c.get("/api/projects/1/sources").json()[0]["published"] is True
    c.app.state.neo4j._load_config = lambda: CFG
    c.driver.fail_write = Exception("boom")
    failed = post(c, "unpublish", document_ids=[SRS]).json()
    assert failed["changed"] and failed["sync"]["state"] == "retrying" and failed["sync"]["error"] == "neo4j_publish_failed"


def test_sync_now_sends_only_published_documents(c):
    post(c, "publish", document_ids=[SRS])
    c.driver.graph.nodes.clear()
    r = c.post("/api/projects/1/publish/neo4j")
    assert r.status_code == 200 and r.json()["counts"]["Requirement"] == 3 and r.json()["counts"]["SourceDocument"] == 1


# ------------------------------------------------------------------------------------------------------------------ keeping published documents up to date
def test_decisions_and_renames_reach_a_published_document_and_never_an_unpublished_one(c):
    g = c.driver.graph
    post(c, "publish", document_ids=[SRS])
    assert c.put("/api/requirements/p1-REQ-002/decision", json={"decision": "accepted"}).status_code == 200
    store = c.app.state.neo4j
    assert store.publish_info(1)["out_of_date"] is True  # the background sync sees the change
    store.publish(1)
    assert node(g, S.Label.REQUIREMENT, "demo-project:src1:REQ-002")[S.RequirementP.STATUS] == "accepted"
    c.put("/api/requirements/p1-REQ-004/decision", json={"decision": "accepted"})
    assert store.publish_info(1)["out_of_date"] is False  # REQ-004 is in a document that is not published: nothing to send
    assert (S.Label.REQUIREMENT, "demo-project:src2:REQ-004") not in g.nodes or node(g, S.Label.REQUIREMENT, "demo-project:src2:REQ-004").get("active") is False
    c.patch("/api/projects/1", json={"name": "Core Banking 2"})
    store.publish(1)
    assert node(g, S.Label.PROJECT, "demo-project")[S.ProjectP.NAME] == "Core Banking 2"


def test_analysing_again_holds_a_published_document_as_it_is(c):
    g = c.driver.graph
    post(c, "publish", document_ids=[SRS])
    c.app.state.db.run("UPDATE sources SET analysis_state='analyzing' WHERE id=?", (SRS,))
    c.app.state.neo4j.publish(1)
    assert len(active(g, S.Label.REQUIREMENT)) == 3  # held: neither switched off nor changed while it is analysed
    assert c.get("/api/projects/1/sources").json()[0]["published"] is True


# ------------------------------------------------------------------------------------------------------------------ the sprint summary
def test_the_sprint_summary_has_totals_and_one_row_per_document(c):
    c.app.state.db.run("INSERT INTO jira_issues (project_id, issue_key, jira_project, source_id, text, text_hash, updated_at) VALUES (1,'ABC-1','ABC',2,'t','h','t')")
    post(c, "publish", document_ids=[SRS])
    r = c.get("/api/projects/1/sprints/1/summary")
    assert r.status_code == 200, r.text
    s = r.json()
    assert (s["sprint_id"], s["name"], s["is_current"], s["documents"], s["published"]) == (1, "Sprint 1", True, 2, 1)
    assert (s["requirements"], s["fr"], s["nfr"]) == (4, 3, 1)
    assert (s["ready"], s["needs_clarification"], s["failed"], s["not_written"]) == (1, 1, 1, 1)
    assert s["decided"] == {"accepted": 1, "edited": 1, "rejected": 1, "pending": 1}
    srs, brd = s["rows"]
    assert (srs["document_id"], srs["name"], srs["source"], srs["requirements"], srs["fr"], srs["nfr"], srs["unclassified"]) == (1, "srs.txt", "file", 3, 2, 1, 0)
    assert (srs["ready"], srs["needs_clarification"], srs["failed"], srs["not_written"]) == (1, 1, 0, 1)
    assert srs["decided"] == {"accepted": 1, "edited": 1, "rejected": 0, "pending": 1}
    assert srs["findings"] == {"ambiguity": 1, "conflict": 0, "duplicate": 2, "security": 1}
    assert (srs["analysis_state"], srs["publish_state"]) == ("analyzed", "published") and srs["published_at"]
    assert (brd["source"], brd["failed"], brd["publish_state"], brd["published_at"]) == ("jira", 1, "not_published", None)
    assert brd["decided"]["rejected"] == 1


def test_the_summary_counts_only_the_requirements_that_are_in_the_sprint(c):
    db = c.app.state.db
    db.run("INSERT INTO sprints (project_id, name, origin, confirmed, position, created_at) VALUES (1, 'Sprint 2', 'manual', 1, 2, 't')")
    db.run("UPDATE requirements SET sprint_id=2 WHERE uid='p1-REQ-003'")
    one, two = (c.get(f"/api/projects/1/sprints/{i}/summary").json() for i in (1, 2))
    assert [r["requirements"] for r in one["rows"]] == [2, 1] and [r["requirements"] for r in two["rows"]] == [1]
    assert (two["name"], two["is_current"], two["documents"], two["requirements"]) == ("Sprint 2", False, 1, 1)
    assert c.get("/api/projects/1/sprints/99/summary").status_code == 404 and c.get("/api/projects/99/sprints/1/summary").status_code == 404


def test_the_summary_shows_the_sync_state_of_published_documents(c):
    post(c, "publish", document_ids=[SRS])
    sync = c.app.state.sync
    for state, expect in (("synced", "published"), ("syncing", "syncing"), ("pending", "syncing"), ("retrying", "sync_error"), ("unreachable", "sync_error")):
        sync.status = lambda pid, state=state: {"state": state}
        rows = c.get("/api/projects/1/sprints/1/summary").json()["rows"]
        assert (rows[0]["publish_state"], rows[1]["publish_state"]) == (expect, "not_published"), state


# ------------------------------------------------------------------------------------------------------------------ the overview
def test_the_overview_share_stage_counts_published_documents(c):
    share = c.get("/api/projects/1/overview").json()["pipeline"]["share"]
    assert (share["state"], share["published"], share["documents"]) == ("waiting", 0, 2)
    post(c, "publish", document_ids=[SRS])
    share = c.get("/api/projects/1/overview").json()["pipeline"]["share"]
    assert (share["published"], share["documents"]) == (1, 2)
