"""Rule-based "vague term" highlighting for the UI.

This is a plain word list, separate from Part A: it is NOT the QuRE weak-word list, it is not a trained model, and it never changes
`ambiguity.label`, the ambiguity probability, `weak_words` or any Part A count. It only tells the UI which words to mark in the text, so a reader
can see why a requirement might need a follow-up question. No accuracy is claimed for the list: a term in it is a hint, not a finding.

Matching is case-insensitive and whole word / whole phrase only ("fast" does not match "fastener" or "faster"). The list can be changed here
without touching any model file.
"""
import re

VAGUE_TERMS = (
    "quickly", "fast", "rapidly", "promptly",
    "user-friendly", "easy", "easily",
    "efficient", "efficiently",
    "intuitive", "flexible", "robust", "seamless",
    "as appropriate", "as needed", "etc.", "and so on",
    "minimal", "adequate", "reasonable",
)

# longest first, so a phrase is preferred over a shorter term that starts the same way
_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(t) for t in sorted(VAGUE_TERMS, key=len, reverse=True)) + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def vague_term_spans(text):
    """[{term, start, end}] in text order; `term` is the text as written, `start`/`end` are character offsets."""
    return [{"term": m.group(0), "start": m.start(), "end": m.end()} for m in _PATTERN.finditer(text or "")]
