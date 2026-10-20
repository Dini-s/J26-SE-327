"""Hand-labelling: stable sample, saved labels, precision and interval."""

import pytest

from apps.api import labeling


def link(i, conf=0.9, status="verified"):
    return {"requirement": f"R{i}", "code": f"C{i}", "confidence": conf, "status": status}


def test_sample_is_stable_and_skips_decayed():
    links = [link(i) for i in range(30)] + [link(99, status="decayed")]
    a, b = labeling.sample_links(links, 10), labeling.sample_links(list(reversed(links)), 10)
    assert a == b and len(a) == 10 and all(l["requirement"] != "R99" for l in a)


def test_labels_are_saved_and_cleared(tmp_path):
    labeling.set_label("p", "R1", "C1", "correct", tmp_path)
    assert labeling.load_labels("p", tmp_path)["R1||C1"]["label"] == "correct"
    labeling.set_label("p", "R1", "C1", None, tmp_path)
    assert labeling.load_labels("p", tmp_path) == {}
    with pytest.raises(ValueError):
        labeling.set_label("p", "R1", "C1", "maybe", tmp_path)


def test_precision_ignores_unsure_and_buckets_by_confidence():
    sample = [link(1, 0.9), link(2, 0.9), link(3, 0.6), link(4, 0.8), link(5, 0.9)]
    labels = {"R1||C1": {"label": "correct"}, "R2||C2": {"label": "wrong"}, "R3||C3": {"label": "wrong"}, "R4||C4": {"label": "unsure"}}
    s = labeling.stats(sample, labels)
    assert (s["correct"], s["wrong"], s["unsure"], s["labelled"]) == (1, 2, 1, 4)
    assert s["precision"] == round(1 / 3, 3)
    assert {b["label"]: b["precision"] for b in s["byConfidence"]} == {"< 0.7": 0.0, "0.7 - 0.85": None, ">= 0.85": 0.5}


def test_wilson_interval_is_wide_for_small_samples_and_empty_safe():
    lo, hi = labeling.wilson(3, 4)
    assert lo < 0.75 < hi and hi - lo > 0.4
    assert labeling.wilson(0, 0) == (0.0, 0.0)
    assert labeling.stats([], {})["precision"] is None


def test_license_header_is_stripped_from_code_text():
    from apps.api.sources import strip_license

    code = "/*\n * Copyright 2012 X\n * Licensed under Apache\n */\npackage a;\nclass A {}"
    assert strip_license(code) == "package a;\nclass A {}"
    plain = "/* helper */\nclass B {}"
    assert strip_license(plain) == plain


def test_ab_summary_counts_kept_and_rejected_links():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("ab", Path(__file__).resolve().parents[1] / "scripts" / "ab_evidence_mode.py")
    ab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ab)
    rows = [
        {"label": "correct", "ev_linked": True}, {"label": "correct", "ev_linked": False},
        {"label": "wrong", "ev_linked": False}, {"label": "wrong", "ev_linked": True},
        {"label": "unsure", "ev_linked": True}, {"label": "correct", "ev_linked": None},
    ]
    s = ab.summarise(rows)
    assert s["links_judged"] == 4 and s["standard_precision"] == 0.5
    assert s["evidence_kept"] == 2 and s["evidence_precision"] == 0.5
    assert s["correct_links_kept"] == "1/2" and s["wrong_links_rejected"] == "1/2"


def test_sample_total_excludes_decayed_links_and_keeps_existing_labels(monkeypatch):
    from apps.api import server
    monkeypatch.setattr(server, '_need_neo4j', lambda: None)
    links = [dict(requirement='REQ-1', requirementText='One requirement', code='project:App.java',
                  confidence=0.9, reason='Implementation', status='verified', review='correct', reviewedHash='hash', textHash='hash'),
             dict(requirement='REQ-2', requirementText='Second requirement', code='project:Old.java',
                  confidence=0.0, reason='Deleted', status='decayed')]
    monkeypatch.setattr(server.sources, 'neo4j_links', lambda project: {'links': links})
    from apps.api import labeling
    monkeypatch.setattr(labeling, 'load_labels', lambda project: {'REQ-1||project:App.java': {'label': 'correct'}})
    result = server.get_labeling({'project': 'project'})
    assert result['total'] == 1 and len(result['items']) == 1
    assert result['items'][0]['label'] == 'correct'
    assert result['items'][0]['confidence'] == 0.9


def test_recording_review_updates_uskg_and_returns_status(monkeypatch):
    from apps.api import server
    from shared.uskg.client import USKGClient
    monkeypatch.setattr(server, '_need_neo4j', lambda: None)
    monkeypatch.setattr(server, '_need_idle', lambda: None)
    calls = []
    monkeypatch.setattr(USKGClient, '__init__', lambda self: None)
    monkeypatch.setattr(USKGClient, 'close', lambda self: None)
    monkeypatch.setattr(USKGClient, 'review_link', lambda self, *args: calls.append(args) or {'ok': True, 'status': 'rejected', 'label': 'wrong'})
    result = server.post_label({'project': 'sample', 'requirement': 'REQ-1', 'code': 'sample:App.java', 'label': 'wrong', 'text_hash': 'hash'})
    assert result['status'] == 'rejected'
    assert calls == [('sample', 'REQ-1', 'sample:App.java', 'wrong', 'hash')]


def test_failed_persistence_keeps_previous_review(monkeypatch, tmp_path):
    labeling.set_label('p', 'R1', 'C1', 'correct', tmp_path)
    def fail(*args):
        raise OSError('disk unavailable')
    monkeypatch.setattr(labeling.os, 'replace', fail)
    with pytest.raises(OSError):
        labeling.set_label('p', 'R1', 'C1', 'wrong', tmp_path)
    assert labeling.load_labels('p', tmp_path)['R1||C1']['label'] == 'correct'
    assert len(list(tmp_path.iterdir())) == 1


def test_review_queue_prioritizes_pending_candidates():
    pending = dict(link(99, .6), status='pending_review')
    approved = link(1, .9)
    assert labeling.sample_links([approved,pending],1) == [pending]


def test_legacy_review_migration_requires_current_hash_and_newer_timestamp(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from unittest.mock import MagicMock
    from apps.api.approval import migrate_reviews
    from shared.schemas.traceability import Artifact, TraceabilityLink
    from agents.traceability_agent.utils import content_hash
    req = Artifact(id='R1',type='requirement',text='Requirement text')
    code = Artifact(id='C1',type='code',text='implementation code')
    now = datetime.now(timezone.utc)
    trace = TraceabilityLink(source_id='R1',target_id='C1',link_type='requirement_to_code',confidence=.6,
                             justification='evidence',text_hash=content_hash(req,code),last_checked_at=now)
    graph = MagicMock()
    graph.list_projects.return_value = [{'project':'p'}]
    graph.get_artifacts.side_effect = lambda kind, **kw: [req] if kind=='requirement' else [code] if kind=='code' else []
    graph.get_traces.return_value = [trace]
    monkeypatch.setattr(labeling,'load_labels',lambda key: {'R1||C1':{'label':'wrong','at':(now+timedelta(seconds=1)).isoformat()}})
    assert migrate_reviews(graph) == 1
    graph.review_link.assert_called_once_with('p','R1','C1','wrong',trace.text_hash)
    graph.review_link.reset_mock()
    monkeypatch.setattr(labeling,'load_labels',lambda key: {'R1||C1':{'label':'wrong','at':(now-timedelta(seconds=1)).isoformat()}})
    assert migrate_reviews(graph) == 0
    graph.review_link.assert_not_called()
