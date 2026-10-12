"""App data layer: run-log parsing, health checks and the demo stand-ins (no server needed)."""

import json

from apps.api import sources

def ev(type_, **kw):
    return {"type": type_, "ts": "2026-01-01T00:00:00+00:00", **kw}


EVENTS = [
    ev("run_start", dataset="d", retrieval="hybrid", top_k=3, sources=["R1", "R2"], n_targets=10),
    ev("shortlist", source_id="R1", targets=[{"id": "C1", "score": 2.0}, {"id": "C2", "score": 1.0}, {"id": "C3", "score": 0.5}]),
    ev("shortlist", source_id="R2", targets=[{"id": "C4", "score": 1.5}]),
    ev("verify_start", total=4),
    ev("verdict", index=1, source_id="R1", target_id="C1", similarity=2.0, is_linked=True, confidence=0.9, reasoning="a", latency=40.0, kept=True),
    ev("verdict", index=2, source_id="R1", target_id="C2", similarity=1.0, is_linked=False, confidence=0.2, reasoning="b", latency=60.0, kept=False),
    ev("verdict", index=3, source_id="R1", target_id="C3", similarity=0.5, is_linked=True, confidence=0.8, reasoning="c", latency=50.0, kept=True),
]


def test_read_events_ignores_a_half_written_last_line(tmp_path):
    (tmp_path / "events.jsonl").write_text(json.dumps(EVENTS[0]) + "\n" + '{"type": "shortl')
    assert len(sources.read_events(tmp_path)) == 1


def test_neo4j_status_reports_offline_without_raising(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://127.0.0.1:1")
    sources._neo_cache.update(at=0.0, value=None)
    status = sources.neo4j_status(ttl=0)
    assert status["connected"] is False and "error" in status


def test_llm_status_not_configured(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert sources.llm_status() == {"configured": False}


def test_vetted_write_statements_pass_the_ownership_guard():
    import pytest as _pytest

    from shared.uskg import client

    for query in client._WRITE_QUERIES:
        client.validate_write_query(query)
    for bad in ("MATCH (n) DETACH DELETE n", "MERGE (n:CodeEntity {id: 'x'})", "CREATE (n:Requirement)"):
        with _pytest.raises(PermissionError):
            client.validate_write_query(bad)


# ---------- pipeline stages, run summaries, offline graph, demo guard ----------
def test_demo_is_refused_for_a_non_local_database_and_when_disabled(monkeypatch):
    from apps.api import demo

    monkeypatch.setenv("NEO4J_URI", "bolt://db.example.com:7687")
    assert not demo.allowed()["allowed"] and "not local" in demo.allowed()["reason"]
    with __import__("pytest").raises(demo.DemoError):
        demo.reset()
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    assert demo.allowed()["allowed"]
    monkeypatch.setenv("DASHBOARD_ALLOW_DEMO", "0")
    assert not demo.allowed()["allowed"]


def test_demo_reset_only_touches_c4_types_and_demo_nodes(monkeypatch):
    from unittest.mock import MagicMock

    from apps.api import demo

    queries = []
    driver = MagicMock()
    driver.__enter__.return_value = driver

    def run(query, **kw):
        queries.append(query)
        summary = MagicMock()
        summary.counters.relationships_deleted = 3
        summary.counters.nodes_deleted = 2
        summary.counters.properties_set = 4
        return [], summary, []

    driver.execute_query.side_effect = run
    monkeypatch.setattr(demo, "_neo4j_driver", lambda: driver)
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    result = demo.reset()
    assert result == {"deleted_links": 3, "deleted_flags": 2, "restored_texts": 2}
    joined = " ".join(queries)
    assert "DELETE v" in joined and "DETACH DELETE d" in joined
    assert "dataset IS NOT NULL" in joined  # text restore only on demo nodes
    assert not any(q.strip().startswith("MATCH (n:Requirement") for q in queries)


def test_add_requirement_validates_text_and_id(monkeypatch):
    import pytest as _pytest

    from apps.api import demo

    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    with _pytest.raises(demo.DemoError, match="full sentence"):
        demo.add_requirement("too short")
    with _pytest.raises(demo.DemoError, match="id may only"):
        demo.add_requirement("The system shall do something useful for the user.", "bad id;")
    monkeypatch.setenv("NEO4J_URI", "bolt://db.example.com:7687")
    with _pytest.raises(demo.DemoError, match="not local"):
        demo.add_requirement("The system shall do something useful for the user.")


def test_demo_undo_restores_texts_and_undecays_only_c4_data(monkeypatch):
    from unittest.mock import MagicMock

    from apps.api import demo

    queries = []
    driver = MagicMock()
    driver.__enter__.return_value = driver

    def run(query, **kw):
        queries.append(query)
        summary = MagicMock()
        summary.counters.properties_set = 4
        summary.counters.nodes_deleted = 1
        return [], summary, []

    driver.execute_query.side_effect = run
    monkeypatch.setattr(demo, "_neo4j_driver", lambda: driver)
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    assert demo.undo_changes() == {"restored_texts": 2, "flags_removed": 1}
    joined = " ".join(queries)
    assert "dataset IS NOT NULL" in joined and "original_text" in joined
    assert "SET v.status = 'verified'" in joined and "DETACH DELETE f" in joined
    assert "DELETE v" not in joined.replace("DETACH DELETE f", "")  # never deletes links
    assert "Requirement)" not in joined.split("DETACH DELETE f")[-1]
