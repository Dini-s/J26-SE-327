"""Analytics summary of trace links."""

from apps.api import analytics


def link(r, c, conf, status="verified", at="2026-10-14T10:00:00"):
    return {"requirement": r, "code": f"p:src/{c}", "confidence": conf, "status": status, "verifiedAt": at, "reason": "why"}


PAYLOAD = {
    "project": "p",
    "requirements": 5,
    "links": [link("R1", "A.java", 0.9), link("R1", "B.java", 0.6), link("R2", "A.java", 0.4), link("R3", "C.java", 0.3, "decayed", "2026-10-15T10:00:00")],
    "decayFlags": [{"requirement": "R3", "code": "p:src/C.java", "flaggedAt": "2026-10-16T09:00:00"}],
}


def test_coverage_counts_only_verified_links():
    a = analytics.build(PAYLOAD)
    assert a["linkedRequirements"] == 2 and a["coverage"] == 0.4
    assert a["verifiedLinks"] == 3 and a["decayedLinks"] == 1 and a["decayEvents"] == 1


def test_histograms():
    a = analytics.build(PAYLOAD)
    assert {b["label"]: b["count"] for b in a["linksPerRequirement"]} == {"0": 3, "1": 1, "2": 1, "3": 0, "4+": 0}
    assert {b["label"]: b["count"] for b in a["confidenceHistogram"]}["< 0.5"] == 1


def test_hotspots_weakest_and_unstable():
    a = analytics.build(PAYLOAD)
    assert a["hotspots"][0]["name"] == "A.java" and a["hotspots"][0]["requirements"] == 2
    assert a["weakestLinks"][0]["requirement"] == "R2"
    assert a["unstableFiles"] == [{"code": "p:src/C.java", "name": "C.java", "decays": 1}]


def test_timeline_accumulates_created_links_per_day():
    t = analytics.build(PAYLOAD)["timeline"]
    assert [d["day"] for d in t] == ["2026-10-14", "2026-10-15", "2026-10-16"]
    assert t[-1]["total"] == 4 and t[-1]["decayed"] == 1


def test_empty_project():
    a = analytics.build({"project": "p", "requirements": 0, "links": [], "decayFlags": []})
    assert a["coverage"] == 0.0 and a["timeline"] == []
