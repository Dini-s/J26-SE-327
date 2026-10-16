"""Analytics over a project's trace links: distributions, hotspots, weakest links and a timeline.

Pure functions over the payload of ``sources.neo4j_links`` so they can be tested without Neo4j.
"""

from collections import Counter, defaultdict
from typing import Any

BUCKETS = [(0.0, 0.5, "< 0.5"), (0.5, 0.7, "0.5 - 0.7"), (0.7, 0.85, "0.7 - 0.85"), (0.85, 1.01, ">= 0.85")]


def _day(value: Any) -> str:
    return str(value)[:10] if value else ""


def _name(path: str) -> str:
    return str(path).split("/")[-1].split(":")[-1]


def build(payload: dict[str, Any], top: int = 10) -> dict[str, Any]:
    """Summarise ``neo4j_links`` output.

    Returns coverage, a confidence histogram, links-per-requirement histogram, the files that the most
    requirements depend on (change hotspots), files that decayed most, the weakest verified links,
    and per-day counts of links created and links that decayed.
    """
    links = payload.get("links", [])
    flags = payload.get("decayFlags", [])
    total_req = payload.get("requirements", 0)
    verified = [l for l in links if l.get("status") != "decayed"]

    linked_reqs = {l["requirement"] for l in verified}
    per_req = Counter(l["requirement"] for l in verified)
    histogram = Counter(per_req[r] for r in linked_reqs)
    never = max(0, total_req - len(linked_reqs))
    links_per_req = [{"label": "0", "count": never}] + [
        {"label": str(n) if n < 4 else "4+", "count": sum(c for k, c in histogram.items() if (k == n if n < 4 else k >= 4))} for n in (1, 2, 3, 4)
    ]

    confidence = [
        {"label": label, "count": sum(1 for l in verified if lo <= (l.get("confidence") or 0) < hi)} for lo, hi, label in BUCKETS
    ]

    by_code: dict[str, set[str]] = defaultdict(set)
    for l in verified:
        by_code[l["code"]].add(l["requirement"])
    hotspots = sorted(
        ({"code": c, "name": _name(c), "requirements": len(r)} for c, r in by_code.items()), key=lambda x: (-x["requirements"], x["name"])
    )[:top]

    decay_by_code = Counter(f["code"] for f in flags)
    unstable = [{"code": c, "name": _name(c), "decays": n} for c, n in decay_by_code.most_common(top)]

    weakest = sorted(verified, key=lambda l: (l.get("confidence") or 0, l["requirement"]))[:top]
    weakest = [
        {"requirement": l["requirement"], "code": l["code"], "name": _name(l["code"]), "confidence": l.get("confidence"), "reason": l.get("reason", "")[:240]}
        for l in weakest
    ]

    created = Counter(_day(l.get("verifiedAt")) for l in links if l.get("verifiedAt"))
    decayed = Counter(_day(f.get("flaggedAt")) for f in flags if f.get("flaggedAt"))
    days = sorted(set(created) | set(decayed))
    timeline, running = [], 0
    for d in days:
        running += created.get(d, 0)
        timeline.append({"day": d, "created": created.get(d, 0), "decayed": decayed.get(d, 0), "total": running})

    confs = [l.get("confidence") or 0 for l in verified]
    return {
        "project": payload.get("project"),
        "requirements": total_req,
        "linkedRequirements": len(linked_reqs),
        "coverage": round(len(linked_reqs) / total_req, 3) if total_req else 0.0,
        "verifiedLinks": len(verified),
        "decayedLinks": len(links) - len(verified),
        "decayEvents": len(flags),
        "meanConfidence": round(sum(confs) / len(confs), 3) if confs else 0.0,
        "confidenceHistogram": confidence,
        "linksPerRequirement": links_per_req,
        "hotspots": hotspots,
        "unstableFiles": unstable,
        "weakestLinks": weakest,
        "timeline": timeline,
    }
