"""Meaning-bearing edits that a small LLM tends to overlook: changed numbers, flipped conditions, added negations.

A link is verified once and its texts are later edited. A text hash only says "something changed"; the LLM then
decides whether the link still holds, and an 8B model reading topics misses a threshold going from 3 to 300 or
a condition turning into its opposite. This module keeps a small fingerprint of what carries behaviour
(numbers, negations, boolean literals, comparison operators) when the link is verified and compares it with
the fingerprint of the current text. A difference is reported with the exact change, so a reviewer can see why.
"""

import json
import re
from collections import Counter
from typing import Any, Optional

from shared.schemas.traceability import Artifact

_NUMBER_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                 "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30, "sixty": 60, "hundred": 100}
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])")
_WORD = re.compile(r"[A-Za-z']+")
_NEGATION_WORDS = {"not", "never", "cannot", "without", "neither", "nor"}
_OPERATORS = re.compile(r"(?<=\s)(<=|>=|==|!=|<|>)(?=\s)|&&|\|\|")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"(?m)(?<![:\"'])//.*$")
_SQL_COMMENT = re.compile(r"(?m)^\s*--.*$")
_BANG = re.compile(r"!(?=[\w(])")


def _strip_comments(text: str) -> str:
    """Comments carry years, issue numbers and prose: they are not behaviour."""
    return _SQL_COMMENT.sub("", _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", text)))


def fingerprint(text: str) -> dict[str, Any]:
    """Counts of the things in ``text`` that change what it asks for or does."""
    body = _strip_comments(text)
    numbers = [n.rstrip("0").rstrip(".") if "." in n else n for n in _NUMBER.findall(body)]
    words = [w.lower() for w in _WORD.findall(body)]
    numbers += [str(_NUMBER_WORDS[w]) for w in words if w in _NUMBER_WORDS]
    negations = sum(1 for w in words if w in _NEGATION_WORDS or w.endswith("n't")) + body.count("!=") + len(_BANG.findall(body))
    return {
        "numbers": sorted(numbers),
        "negations": negations,
        "true": sum(1 for w in words if w == "true"),
        "false": sum(1 for w in words if w == "false"),
        "operators": dict(sorted(Counter(m.group(0) for m in _OPERATORS.finditer(body)).items())),
    }


def changes(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Human-readable differences between two fingerprints (empty list: nothing meaning-bearing changed)."""
    out: list[str] = []
    gone = Counter(old.get("numbers", [])) - Counter(new.get("numbers", []))
    came = Counter(new.get("numbers", [])) - Counter(old.get("numbers", []))
    if gone or came:
        out.append(f"numbers changed: {sorted(gone.elements())} -> {sorted(came.elements())}")
    if old.get("negations", 0) != new.get("negations", 0):
        out.append(f"negations changed: {old.get('negations', 0)} -> {new.get('negations', 0)}")
    for word in ("true", "false"):
        if old.get(word, 0) != new.get(word, 0):
            out.append(f"'{word}' count changed: {old.get(word, 0)} -> {new.get(word, 0)}")
    if old.get("operators", {}) != new.get("operators", {}):
        out.append(f"comparison operators changed: {old.get('operators', {})} -> {new.get('operators', {})}")
    return out


def fingerprint_pair(requirement: Artifact, target: Artifact, target_text: Optional[str] = None) -> str:
    """JSON fingerprint of a requirement and its target, stored on the link when it is verified."""
    return json.dumps({"r": fingerprint(requirement.text), "t": fingerprint(target_text if target_text is not None else target.text)}, sort_keys=True)


def pair_changes(stored: Optional[str], requirement: Artifact, target: Artifact, target_text: Optional[str] = None) -> list[str]:
    """Meaning-bearing changes since ``stored`` was taken. No stored fingerprint (an older link): nothing to compare."""
    if not stored:
        return []
    try:
        old = json.loads(stored)
        old_r, old_t = old["r"], old["t"]
    except (ValueError, KeyError, TypeError):
        return []
    found = [f"requirement {c}" for c in changes(old_r, fingerprint(requirement.text))]
    found += [f"code {c}" for c in changes(old_t, fingerprint(target_text if target_text is not None else target.text))]
    return found
