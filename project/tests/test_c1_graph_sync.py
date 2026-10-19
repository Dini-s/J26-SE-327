"""Component 1 graph shape and sync: every analysed document is published in full (counts per document equal the workspace), Sprint-INCLUDES_SOURCE->SourceDocument
derived on every sync, no Phase in the graph, the project name follows renames, documents that are still being analysed are held back until they are finished,
the overview pipeline, and scripts/c1_graph_counts.py (read-only, counts only).

No real graph database: the fake graph of test_c1_neo4j.py (extended here with the per-document count queries) and the fake clock of test_c1_planning_sync.py.
"""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from agents.requirement_agent.api import autosync, neo4j_store, service
from agents.requirement_agent.api import neo4j_schema as S
from agents.requirement_agent.api.db import dumps, now
from tests.test_c1_neo4j import Graph, Result, isolated_settings, seed, store_for  # noqa: F401  (isolated_settings is autouse there)
from tests.test_c1_planning_sync import Clock, advance, c, make_client, sprints  # noqa: F401  (fixtures)

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "c1_graph_counts.py"
KINDS = ("requirements", "issues", "drafts")


def load_script():
    spec = importlib.util.spec_from_file_location("c1_graph_counts", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CountGraph(Graph):
    """The fake graph plus the read-only per-document count queries."""

    def counts(self, query, project_id):
        kind = next(k for k, q in neo4j_store.Q_COUNT.items() if q == query)
        label = {"requirements": S.Label.REQUIREMENT, "issues": S.Label.ISSUE, "drafts": S.Label.DRAFT}[kind]
        rel = {"requirements": S.Rel.CONTAINS, "issues": S.Rel.HAS_ISSUE, "drafts": S.Rel.HAS_DRAFT}[kind]
        out = {}
        for (lab, sid), props in self.nodes.items():
            if lab != S.Label.SOURCE or props.get("project_id") != project_id or not props.get("active", True):
                continue
            reqs = [b for (r, a, b) in self.rels if r == S.Rel.CONTAINS and a == sid]
            leaves = reqs if kind == "requirements" else [b for (r, a, b) in self.rels if r == rel and a in reqs]
            out[sid] = sum(1 for x in leaves if self.nodes[(label, x)].get("active", True))
        return [{"source_id": k, "n": v} for k, v in out.items()]


def add_third_document(db):
    """A third analysed document with two requirements (one with a finished draft, one vague and risky)."""
    db.run("INSERT INTO sources (id, project_id, filename, stored_path, ext, size_bytes, pages, warnings, extracted, created_at, source_type, sha256, analysis_state)"
           " VALUES (3,1,'third.txt','/nowhere/third.txt','.txt',10,NULL,'[]','{}','2026-10-03T00:00:00+00:00','srs','c3','analyzed')")
    for seq, text, defect in ((5, "The system shall be fast.", True), (6, "The portal shall show the balance.", False)):
        db.run("INSERT INTO requirements (uid, project_id, rid, seq, source_id, source_file, text, text_hash, occurrence, fr_nfr, nfr_probability, is_security, security_cue_words,"
               " ambiguity_label, ambiguity_probability, weak_words, duplicate_group, duplicate_matches, conflict_matches, risk_score, risk_level, findings, created_at)"
               " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (f"p1-REQ-{seq:03d}", 1, f"REQ-{seq:03d}", seq, 3, "x", text, f"h{seq}", 1, "FR", 0.5, 0, "[]", "defect" if defect else "clear", 0.9 if defect else 0.1,
                dumps(["fast"] if defect else []), "", "[]", "[]", 3 if defect else 0, "MEDIUM" if defect else "NONE", "[]", now()))
    db.run("INSERT INTO generation (uid, state, message, result, attempts, manual_review, updated_at) VALUES (?,?,?,?,?,?,?)",
           ("p1-REQ-006", "done", "", dumps({"status": "ok", "user_story": "As a user I want my balance.", "technical_task": "Show it.", "acceptance_criteria": ["It is shown."],
                                              "rationale": "r", "clarification_questions": [], "backend": "ollama", "model": "m", "generated_on": "device",
                                              "endpoint_host": None, "generated_from": "original"}), 1, 0, now()))


def per_document(db, project=1):
    """What the workspace says per document, counted straight from the tables (issues: from the same rule set the bundle uses)."""
    out = {}
    key = service.project_key(db, service.project_or_404(db, project))
    bundle = neo4j_store.build_bundle(db, project, key, "x")
    for sb in bundle.sources:
        sid = int(sb.source_id.rsplit(":src", 1)[1])
        out[sid] = {
            "requirements": db.one("SELECT COUNT(*) n FROM requirements WHERE source_id=?", (sid,))["n"],
            "drafts": db.one("SELECT COUNT(*) n FROM generation g JOIN requirements r ON r.uid=g.uid WHERE r.source_id=? AND g.state IN ('done','needs_clarification')", (sid,))["n"],
            "issues": len(sb.issues)}
    return out


# ------------------------------------------------------------------------------------------------------------------ (1a) every analysed document is published
def test_graph_counts_per_document_equal_the_workspace_counts(c):
    db = c.app.state.db
    add_third_document(db)
    graph = CountGraph()
    store, _ = store_for(db, graph)
    store.publish(1)
    expected = per_document(db)
    assert sorted(expected) == [1, 2, 3] and [expected[i]["requirements"] for i in (1, 2, 3)] == [3, 1, 2] and [expected[i]["drafts"] for i in (1, 2, 3)] == [2, 0, 1]
    assert sum(v["issues"] for v in expected.values()) >= 8
    mod = load_script()
    got = mod.graph_counts(lambda q, **p: graph.counts(q, p["project_id"]), ["demo-project"])
    assert {sid: got[("demo-project", sid)] for sid in (1, 2, 3)} == expected
    # the script's table reports no difference for the same data and shows numbers only
    ws = {("demo-project", sid): dict(v, state="analyzed") for sid, v in expected.items()}
    lines, different = mod.table(ws, got)
    assert different == 0 and all("DIFFERENT" not in line for line in lines)
    got[("demo-project", 3)]["drafts"] -= 1
    assert mod.table(ws, got)[1] == 1


def test_a_second_sync_after_a_change_keeps_the_counts_equal(c):
    db = c.app.state.db
    graph = CountGraph()
    store, _ = store_for(db, graph)
    store.publish(1)
    add_third_document(db)
    store.publish(1)
    mod = load_script()
    got = mod.graph_counts(lambda q, **p: graph.counts(q, p["project_id"]), ["demo-project"])
    assert {sid: got[("demo-project", sid)] for sid in (1, 2, 3)} == per_document(db)


# ------------------------------------------------------------------------------------------------------------------ (1b) Sprint -INCLUDES_SOURCE-> SourceDocument
def includes(graph):
    return {k: (v["requirements"], v["active"]) for k, v in sorted(graph.includes.items())}


def test_includes_source_counts_requirements_per_sprint_and_document(c):
    db = c.app.state.db
    graph = CountGraph()
    store, _ = store_for(db, graph)
    s1 = sprints(c)["Sprint 1"]["id"]
    s2 = c.post("/api/projects/1/sprints", json={"name": "Sprint 2"}).json()["id"]
    g1, g2 = (f"demo-project:sprint{s1}", f"demo-project:sprint{s2}")
    d1, d2 = "demo-project:src1", "demo-project:src2"
    out = store.publish(1)
    assert includes(graph) == {(g1, d1): (3, True), (g1, d2): (1, True)} and out["counts"][S.Rel.INCLUDES_SOURCE] == 2
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-002"], "sprint_id": s2})
    store.publish(1)
    assert includes(graph) == {(g1, d1): (2, True), (g1, d2): (1, True), (g2, d1): (1, True)}
    # the whole document moves to sprint 2: the old pair is switched off (count 0), never deleted
    c.put("/api/projects/1/sources/1/sprint", json={"sprint_id": s2})
    c.post("/api/projects/1/requirements/assign", json={"requirement_ids": ["REQ-001", "REQ-002", "REQ-003"], "sprint_id": None})
    out = store.publish(1)
    assert includes(graph) == {(g1, d1): (0, False), (g1, d2): (1, True), (g2, d1): (3, True)} and out["deactivated"][S.Rel.INCLUDES_SOURCE] == 1
    assert store.publish(1)["deactivated"][S.Rel.INCLUDES_SOURCE] == 0  # not counted twice
    c.put("/api/projects/1/sources/1/sprint", json={"sprint_id": s1})  # and back: the same pair is active again
    store.publish(1)
    assert includes(graph) == {(g1, d1): (3, True), (g1, d2): (1, True), (g2, d1): (0, False)}
    assert all("DELETE" not in q.upper() for q in (neo4j_store.Q_INCLUDES, neo4j_store.Q_INCLUDES_DEACTIVATE))
    assert neo4j_store.Q_INCLUDES.count(S.Rel.INCLUDES_SOURCE) == 1 and f":{S.Rel.INCLUDES_SOURCE}" in neo4j_store.Q_INCLUDES


# ------------------------------------------------------------------------------------------------------------------ (1c) no phases in the graph
def test_phases_are_not_published_even_when_the_workspace_has_them(c):
    ph = c.post("/api/projects/1/phases", json={"name": "Build"}).json()
    c.post("/api/projects/1/sprints", json={"name": "Sprint 2", "phase_id": ph["id"]})
    graph = CountGraph()
    store, driver = store_for(c.app.state.db, graph)
    out = store.publish(1)
    assert "Phase" not in out["counts"] and "Phase" not in out["deactivated"]
    blob = " ".join(graph.statements + [q for _, q, _ in driver.log] + neo4j_store.schema_statements()) + json.dumps(sorted(map(str, graph.nodes)))
    assert "Phase" not in blob and "IN_PHASE" not in blob and "phase" not in json.dumps(neo4j_store.build_bundle(c.app.state.db, 1, "demo-project", "x").as_dict())
    assert c.get("/api/projects/1/phases").json()[0]["name"] == "Build"  # the workspace tables and endpoints still work


# ------------------------------------------------------------------------------------------------------------------ (1d) the project name follows
def test_the_project_name_reaches_the_graph_on_every_sync(c):
    graph = CountGraph()
    store, _ = store_for(c.app.state.db, graph)
    store.publish(1)
    name = graph.nodes[("Project", "demo-project")][S.ProjectP.NAME]
    assert c.patch("/api/projects/1", json={"name": "Retail Banking"}).status_code == 200 and name != "Retail Banking"
    assert store.publish_info(1)["out_of_date"] is True  # a rename alone makes the graph out of date
    store.publish(1)
    assert graph.nodes[("Project", "demo-project")][S.ProjectP.NAME] == "Retail Banking" and graph.nodes[("Project", "demo-project")]["project_id"] == "demo-project"


def test_a_rename_triggers_a_sync(c):
    sync = c.app.state.sync
    sync.enabled, sync._p = True, {}
    c.patch("/api/projects/1", json={"name": "Retail Banking"})
    assert sync._p[1]["dirty_at"] is not None


# ------------------------------------------------------------------------------------------------------------------ (3) documents still being analysed
def test_a_document_that_is_not_analysed_is_held_back_and_its_old_data_stays(c):
    db = c.app.state.db
    graph = CountGraph()
    store, _ = store_for(db, graph)
    db.run("UPDATE sources SET analysis_state='analyzing' WHERE id=2")
    out = store.publish(1)
    assert out["counts"][S.Label.SOURCE] == 1 and out["counts"][S.Label.REQUIREMENT] == 3
    assert ("SourceDocument", "demo-project:src2") not in graph.nodes and ("Requirement", "demo-project:src2:REQ-004") not in graph.nodes
    assert includes(graph) == {k: v for k, v in includes(graph).items() if k[1] == "demo-project:src1"}
    db.run("UPDATE sources SET analysis_state='analyzed' WHERE id=2")
    store.publish(1)
    assert graph.nodes[("Requirement", "demo-project:src2:REQ-004")]["active"] is True
    # a re-analysis of document 2 starts: what was published about it is left as it is (not switched off), the rest is untouched
    db.run("UPDATE sources SET analysis_state='analyzing' WHERE id=2")
    db.run("DELETE FROM requirements WHERE uid='p1-REQ-004'")
    out = store.publish(1)
    assert out["deactivated"] == {k: 0 for k in out["deactivated"]}
    assert graph.nodes[("SourceDocument", "demo-project:src2")]["active"] is True and graph.nodes[("Requirement", "demo-project:src2:REQ-004")]["active"] is True
    assert any(v["active"] for k, v in graph.includes.items() if k[1] == "demo-project:src2")
    # when it is finished its new content is what the graph holds
    db.run("UPDATE sources SET analysis_state='analyzed' WHERE id=2")
    store.publish(1)
    assert graph.nodes[("Requirement", "demo-project:src2:REQ-004")]["active"] is False
    assert not any(v["active"] for k, v in graph.includes.items() if k[1] == "demo-project:src2")


def test_the_digest_ignores_a_document_that_is_held_back(c):
    db = c.app.state.db
    store, _ = store_for(db, CountGraph())
    store.publish(1)
    assert store.publish_info(1)["out_of_date"] is False
    db.run("UPDATE sources SET analysis_state='analyzing' WHERE id=2")  # held: the bundle loses its data, so the graph would change only once it is finished
    assert store.publish_info(1)["out_of_date"] is True
    db.run("UPDATE sources SET analysis_state='analyzed' WHERE id=2")
    assert store.publish_info(1)["out_of_date"] is False


def test_sync_runs_while_documents_analyse_and_the_document_follows_when_it_is_finished(c):
    db = c.app.state.db
    graph = CountGraph()
    store, _ = store_for(db, graph)
    clock = Clock()
    w = autosync.AutoSync(db, store, clock=clock)
    db.run("UPDATE sources SET analysis_state='analyzing' WHERE id=2")  # mixed: document 1 is analysed, document 2 is still being analysed
    w.notify(1)
    advance(clock, w, 10)
    assert w.status(1)["state"] == "synced"
    assert ("SourceDocument", "demo-project:src1") in graph.nodes and ("SourceDocument", "demo-project:src2") not in graph.nodes
    db.run("UPDATE sources SET analysis_state='analyzed' WHERE id=2")  # it finishes: the service notifies the worker
    w.notify(1)
    advance(clock, w, 9)  # debounce and the 30 s rate limit are not over yet
    assert ("SourceDocument", "demo-project:src2") not in graph.nodes and w.status(1)["state"] == "pending"
    advance(clock, w, 25)
    assert graph.nodes[("SourceDocument", "demo-project:src2")]["active"] is True and w.status(1)["state"] == "synced"
    assert w.status(1)["counts"][S.Label.SOURCE] == 2


def test_a_finishing_draft_and_a_decision_trigger_a_debounced_sync(c):
    db = c.app.state.db
    graph = CountGraph()
    store, _ = store_for(db, graph)
    clock = Clock()
    w = autosync.AutoSync(db, store, clock=clock)
    c.app.state.manager.on_draft = w.notify_uid
    c.app.state.sync = w
    w.notify(1)
    advance(clock, w, 10)
    assert graph.nodes[("Requirement", "demo-project:src1:REQ-002")][S.RequirementP.STATUS] == "pending"
    w._p[1]["last_attempt"] = None
    c.app.state.manager.on_draft("p1-REQ-002")  # a draft finished for REQ-002 (the generation row is written by the worker; here the decision changes with it)
    db.run("INSERT INTO decisions (uid, decision, edited_text, note, updated_at) VALUES ('p1-REQ-002','accepted',NULL,NULL,'2026-10-05T00:00:00+00:00')")
    advance(clock, w, 5)
    assert graph.nodes[("Requirement", "demo-project:src1:REQ-002")][S.RequirementP.STATUS] == "pending"  # still inside the debounce
    advance(clock, w, 5)
    assert graph.nodes[("Requirement", "demo-project:src1:REQ-002")][S.RequirementP.STATUS] == "accepted"


# ------------------------------------------------------------------------------------------------------------------ (4) overview
def test_the_overview_has_draft_totals_and_the_pipeline(c):
    o = c.get("/api/projects/1/overview").json()
    assert o["counts"]["drafts"]["ready"] == o["counts"]["drafts"]["done"] == 1
    assert set(o["pipeline"]) == {"collect", "identify", "analyse", "improve", "share"}
    p = o["pipeline"]
    assert p["collect"] == {"state": "done", "documents": 2}
    assert p["identify"] == {"state": "done", "documents": 2, "requirements": 4}
    assert p["analyse"] == {"state": "done", "analysed": 2, "total": 2, "failed": 0}
    assert p["improve"]["requirements"] == 4 and p["improve"]["decided"] == 3 and p["improve"]["drafts_written"] == 2
    assert p["improve"]["drafts"] == {"ready": 1, "needs_clarification": 1, "failed": 1, "waiting": 0} and p["improve"]["state"] == "attention"
    assert p["share"] == {"state": "waiting", "sync_state": "not_configured", "last_synced_at": None}
    assert set(p["improve"]) == {"state", "requirements", "decided", "drafts_written", "drafts"}


def test_pipeline_states_follow_the_documents_and_the_sync(c):
    db = c.app.state.db

    def pipeline(**sync):
        docs = [r["a"] for r in db.all("SELECT analysis_state a FROM sources")]
        td = dict(generated=1, needs_clarification=1, failed=0, in_progress=0)
        base = {"state": "synced", "last_synced_at": "2026-10-20T00:00:00+00:00"}
        return service.pipeline(docs, 4, 4, td, dict(base, **sync))

    p = pipeline()
    assert [p[k]["state"] for k in ("collect", "identify", "analyse", "improve", "share")] == ["done"] * 5
    db.run("UPDATE sources SET analysis_state='analyzing' WHERE id=2")
    p = pipeline()
    assert (p["identify"]["state"], p["analyse"]["state"], p["analyse"]["analysed"]) == ("active", "active", 1)
    db.run("UPDATE sources SET analysis_state='failed' WHERE id=2")
    p = pipeline()
    assert (p["analyse"]["state"], p["analyse"]["failed"]) == ("failed", 1)
    db.run("UPDATE sources SET analysis_state='not_analyzed' WHERE id=2")
    assert pipeline()["analyse"]["state"] == "waiting"
    for state, expect in (("syncing", "active"), ("pending", "waiting"), ("retrying", "waiting"), ("unreachable", "failed"), ("not_configured", "waiting"), ("synced", "done")):
        assert pipeline(state=state)["share"] == {"state": expect, "sync_state": state, "last_synced_at": "2026-10-20T00:00:00+00:00"}
    empty = service.pipeline([], 0, 0, dict(generated=0, needs_clarification=0, failed=0, in_progress=0), {"state": "synced", "last_synced_at": None})
    assert [empty[k]["state"] for k in ("collect", "identify", "analyse", "improve", "share")] == ["waiting"] * 5
    waiting = service.pipeline(["analyzed"], 4, 1, dict(generated=0, needs_clarification=0, failed=0, in_progress=3), {"state": "synced", "last_synced_at": None})
    assert waiting["improve"]["state"] == "active" and waiting["improve"]["drafts"]["waiting"] == 3


# ------------------------------------------------------------------------------------------------------------------ (2) the script
def test_the_script_is_read_only_and_prints_counts_only(c, tmp_path, capsys, monkeypatch):
    db = c.app.state.db
    add_third_document(db)
    mod = load_script()
    before = Path(db.path).read_bytes()
    ws = mod.workspace_counts(db.path, tmp_path)
    assert {k: v["requirements"] for k, v in ws.items()} == {("demo-project", 1): 3, ("demo-project", 2): 1, ("demo-project", 3): 2}
    assert Path(db.path).read_bytes() == before  # the real file is not written
    lines, different = mod.table(ws, None)  # graph unreachable: workspace side only
    text = "\n".join(lines)
    assert different == 0 and "src1" in text and "srs.txt" not in text and "shall" not in text and "-" in text


def test_the_script_says_so_when_the_graph_cannot_be_reached(c, tmp_path, capsys, monkeypatch):
    mod = load_script()
    ws = Path(c.app.state.db.path).parent
    monkeypatch.setattr(mod.neo4j_config, "ENV_FILES", [])
    for k in ("C1_NEO4J_URI", "NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    code = mod.main(["--workspace", str(ws), "--no-env-file"])
    out = capsys.readouterr().out
    assert code == 2 and "cannot be reached" in out and "neo4j_unconfigured" in out and "password" not in out.lower().replace("neo4j_password", "")
    assert mod.main(["--workspace", str(tmp_path / "missing")]) == 1
