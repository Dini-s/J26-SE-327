"""The review-queue predicates must treat a link with no human label (humanReview = null) as 'needs review'.

Cypher's three-valued logic makes `NOT (null = 'unsure' AND ...)` null, which silently hid every unlabelled
link from the queue (the iTrust queue showed 0 while 103 links waited). These tests pin the null-safe form.
"""
from apps.api import sources


def test_needs_review_keeps_links_without_a_human_label():
    import inspect
    text = inspect.getsource(sources.neo4j_review_queue)
    assert "coalesce(v.humanReview,'') = 'unsure'" in text
    assert "v.humanReview = 'unsure'" not in text


def test_every_review_predicate_is_null_safe():
    import inspect
    text = inspect.getsource(sources)
    assert text.count("coalesce(v.humanReview,'') = 'unsure' AND v.reviewedHash IS NOT NULL") >= 4


class _FakeDriver:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute_query(self, query, **params):
        return ([dict(r) for r in self.rows], None, None) if "RETURN r.id AS requirement" in query else ([{"total": len(self.rows)}], None, None)


def _row(uskg_status, review=None):
    return {"requirement": "R1", "requirementText": "t", "code": "C1", "codeKind": "code", "uskgStatus": uskg_status, "confidence": 0.8,
            "reason": "r", "textHash": "h", "review": review, "reviewedHash": "h" if review else None, "lastCheckedAt": None}


def test_queue_items_keep_their_real_status(monkeypatch):
    """A pending link must show as Needs review in the Link review page, not as Approved (status used to default to verified)."""
    rows = [_row("pending_review"), _row("pending_review", review="unsure"), _row("verified", review="correct"), _row("rejected"), _row("decayed")]
    monkeypatch.setattr(sources, "_neo4j_driver", lambda: _FakeDriver(rows))
    got = sources.neo4j_review_queue("p", "all")
    assert [i["status"] for i in got["items"]] == ["pending_review", "deferred", "verified", "rejected", "decayed"]
