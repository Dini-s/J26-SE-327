"""Which requirements get a task draft first.

The generation model is slow on a laptop GPU, so drafts are written in priority order and the less important ones only on request.

    P1  Part A ambiguity label is `defect`, OR the security flag is set, OR the text contains a rule-based vague term (api/vague.py), OR it is an NFR
    P2  every other requirement that is not a secondary member of a duplicate group (in practice: plain FRs)
    P3  a secondary member of a duplicate group: every member of a group except the first one in document order

A requirement that fits P1 is P1 even if it is a duplicate secondary (the P1 reasons come first). These classes only decide the ORDER and which
requirements the "smart" policy queues by itself; they are not a quality judgement and no model or threshold is involved.
"""
from . import vague

P1, P2, P3 = 1, 2, 3
LABEL = {P1: "P1", P2: "P2", P3: "P3"}
POLICIES = ("smart", "all", "manual")
DEFAULT_POLICY = "smart"


def classify(row, is_duplicate_secondary):
    if row["ambiguity_label"] == "defect" or row["is_security"] or row["fr_nfr"] == "NFR" or vague.vague_term_spans(row["text"]):
        return P1
    return P3 if is_duplicate_secondary else P2


def classes(db, pid):
    """{uid: 1|2|3} for every requirement of the project, in document order (dicts keep insertion order)."""
    rows = db.all("SELECT uid, text, fr_nfr, is_security, ambiguity_label, duplicate_group FROM requirements WHERE project_id=? ORDER BY seq", (pid,))
    first_of_group = {}
    secondary = set()
    for r in rows:
        g = r["duplicate_group"]
        if not g:
            continue
        if g in first_of_group:
            secondary.add(r["uid"])
        else:
            first_of_group[g] = r["uid"]
    return {r["uid"]: classify(r, r["uid"] in secondary) for r in rows}


def selected(policy, cls):
    """Does this policy queue a requirement of class `cls` on its own?"""
    return policy == "all" or (policy == "smart" and cls == P1)
