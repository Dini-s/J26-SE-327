"""USKGClient Cypher and row mapping, against a mocked Neo4j driver."""

from unittest.mock import MagicMock

from shared.schemas.traceability import TraceabilityLink
from shared.uskg.client import USKGClient


def make_client(rows=None, single=None):
    tx = MagicMock()
    tx.run.return_value = MagicMock()
    tx.run.return_value.__iter__.side_effect = lambda: iter([MagicMock(data=lambda r=r: r) for r in (rows or [])])
    tx.run.return_value.single.return_value = single
    session = MagicMock()
    session.execute_read.side_effect = lambda fn: fn(tx)
    session.execute_write.side_effect = lambda fn: fn(tx)
    driver = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    return USKGClient(driver=driver), tx


LINK = TraceabilityLink(
    source_id="R1", target_id="C1", link_type="requirement_to_code",
    confidence=0.9, justification="implements it", text_hash="abc",
)


def test_get_requirements_reads_requirement_nodes_only():
    client, tx = make_client(rows=[{"id": "R1", "type": "requirement", "text": "t", "props": {"id": "R1", "text": "t", "owner": "x"}}])
    (a,) = client.get_artifacts("requirement")
    query = tx.run.call_args[0][0]
    assert ":Requirement" in query and "CREATE" not in query and "MERGE" not in query
    assert (a.id, a.type, a.text, a.metadata) == ("R1", "requirement", "t", {"owner": "x"})


def test_get_code_entities_filters_by_kind():
    client, tx = make_client(rows=[{"id": "D1", "type": "design", "text": "d", "props": {}}])
    (a,) = client.get_artifacts("design")
    assert ":CodeEntity" in tx.run.call_args[0][0]
    assert tx.run.call_args[1] == {"type": "design"} and a.type == "design"


def test_rows_without_id_or_text_are_handled():
    client, _ = make_client(rows=[
        {"id": None, "type": "code", "text": "x", "props": {}},
        {"id": "C2", "type": "code", "text": None, "props": {}},
    ])
    assert [(a.id, a.text) for a in client.get_artifacts("code")] == [("C2", "")]


def test_write_link_merges_verified_trace_idempotently():
    client, tx = make_client(single={"written": 1})
    assert client.write_link(LINK) is True
    query, params = tx.run.call_args[0][0], tx.run.call_args[1]
    assert "MERGE (r)-[v:VERIFIED_TRACE]->(c)" in query
    assert "MATCH (r:Requirement" in query and "MATCH (r:Requirement {id: $source_id}), (c:CodeEntity" in query
    assert params["justification"] == "implements it" and params["status"] == "verified"


def test_write_link_returns_false_when_an_endpoint_is_missing():
    client, _ = make_client(single={"written": 0})
    assert client.write_link(LINK) is False


def test_mark_decayed_keeps_edge_and_creates_flag():
    client, tx = make_client(single={"flagged": 1})
    assert client.mark_decayed(LINK, 0.4, "no longer matches") is True
    query = tx.run.call_args[0][0]
    assert "status = 'decayed'" in query and "DecayFlag" in query and "HAS_DECAY" in query
    assert "DELETE" not in query


def test_get_traces_maps_properties():
    client, tx = make_client(rows=[{
        "source_id": "R1", "target_id": "C1",
        "props": {"confidence": 0.8, "justification": "j", "status": "decayed", "textHash": "h", "linkType": "requirement_to_code"},
    }])
    (link,) = client.get_traces(status="decayed")
    assert tx.run.call_args[1] == {"status": "decayed"}
    assert (link.status, link.confidence, link.text_hash) == ("decayed", 0.8, "h")
