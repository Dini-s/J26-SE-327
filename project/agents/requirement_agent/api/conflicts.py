"""Candidate conflicts between two requirements: simple rules on top of MiniLM similarity. No new model, no accuracy claim.

Every result is only a CANDIDATE CONFLICT THAT NEEDS A HUMAN DECISION. A pair is considered only when its MiniLM cosine is at least
MIN_COSINE (0.80). Then one of two rules must fire:
  (a) prohibition vs assertion: one text has "shall not / must not / never" (PROHIBITION) and the other does not, and after removing those
      words the two texts share at least MIN_OVERLAP of their content words (a rough "same action" test);
  (b) different numeric limits: both texts state a number with the same unit (seconds, ms, minutes, hours, days, %, MB, GB, users ...)
      and the numbers differ (for example "within 2 seconds" vs "within 5 seconds").
The rules are deliberately small and will miss conflicts and flag harmless pairs; they are a starting point for review.
"""
import re

MIN_COSINE = 0.80
MIN_OVERLAP = 0.5
LABEL = "Candidate conflict, needs human decision"

PROHIBITION = re.compile(r"\b(?:shall|must|will|should)\s+not\b|\bnever\b", re.I)
STOPWORDS = frozenset("a an the of to in on at for and or be is are was were by with as it its this that these those shall must will should may can "
                      "system user users not never any all each every than then from into".split())
UNIT = {"ms": "milliseconds", "millisecond": "milliseconds", "milliseconds": "milliseconds",
        "s": "seconds", "sec": "seconds", "secs": "seconds", "second": "seconds", "seconds": "seconds",
        "min": "minutes", "mins": "minutes", "minute": "minutes", "minutes": "minutes",
        "h": "hours", "hr": "hours", "hrs": "hours", "hour": "hours", "hours": "hours",
        "day": "days", "days": "days", "%": "percent", "percent": "percent",
        "kb": "KB", "mb": "MB", "gb": "GB", "tb": "TB", "users": "users", "characters": "characters", "attempts": "attempts"}
QUANTITY = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(%|ms|milliseconds?|seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|percent|kb|mb|gb|tb|users|characters|attempts|s|h)(?![A-Za-z])", re.I)


def content_words(text):
    stripped = PROHIBITION.sub(" ", text.lower())
    return {w for w in re.findall(r"[a-z][a-z0-9-]+", stripped) if w not in STOPWORDS}


def has_prohibition(text):
    return bool(PROHIBITION.search(text))


def quantities(text):
    """{unit: [numbers]} for every 'number unit' found in the text."""
    found = {}
    for m in QUANTITY.finditer(text):
        unit = UNIT.get(m.group(2).lower())
        if unit:
            found.setdefault(unit, []).append(float(m.group(1).replace(",", ".")))
    return found


def _fmt(x):
    return str(int(x)) if float(x).is_integer() else str(x)


def detect(text_a, text_b, cosine):
    """(kind, reason) when the pair is a candidate conflict, else None."""
    if cosine < MIN_COSINE:
        return None
    pa, pb = has_prohibition(text_a), has_prohibition(text_b)
    if pa != pb:
        wa, wb = content_words(text_a), content_words(text_b)
        overlap = len(wa & wb) / max(1, min(len(wa), len(wb)))
        if overlap >= MIN_OVERLAP:
            who = "first" if pa else "second"
            return ("prohibition", f"{LABEL}: the {who} requirement prohibits an action (shall not / must not / never) that the other appears to require "
                                   f"(similarity {cosine:.2f}, shared wording {overlap:.0%}).")
    qa, qb = quantities(text_a), quantities(text_b)
    for unit in sorted(qa.keys() & qb.keys()):
        a_vals, b_vals = sorted(set(qa[unit])), sorted(set(qb[unit]))
        if a_vals != b_vals:
            return ("numeric_limit", f"{LABEL}: both state a limit in {unit} but with different values "
                                     f"({', '.join(_fmt(v) for v in a_vals)} vs {', '.join(_fmt(v) for v in b_vals)}; similarity {cosine:.2f}).")
    return None


def find_conflicts(texts, pairs):
    """pairs: iterable of (i, j, cosine) index pairs. Returns [{'i','j','cosine','kind','reason'}]."""
    out = []
    for i, j, c in pairs:
        hit = detect(texts[i], texts[j], float(c))
        if hit:
            out.append({"i": int(i), "j": int(j), "cosine": round(float(c), 4), "kind": hit[0], "reason": hit[1]})
    return out
