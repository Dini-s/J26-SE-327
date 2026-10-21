"""Show the LLM only the parts of a long code file that match the requirement (optional, off by default).

On a CPU server the LLM spends most of its time *reading* the prompt (about 27 tokens/s measured), so a shorter
prompt is the biggest saving. The file is cut into blocks of whole lines; the first block (usually the class
declaration) and the blocks most similar to the requirement are kept, in their original order, within a budget.
A file that already fits the budget is returned unchanged.
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer

from agents.traceability_agent.preprocess import split_identifiers

GAP = "\n// ... (other parts of the file omitted) ...\n"


def _blocks(code: str, block_chars: int) -> list[str]:
    blocks, current, size = [], [], 0
    for line in code.splitlines():
        current.append(line)
        size += len(line) + 1
        if size >= block_chars:
            blocks.append("\n".join(current))
            current, size = [], 0
    if current:
        blocks.append("\n".join(current))
    return blocks


def focus_code(code: str, requirement: str, max_chars: int, block_chars: int = 400) -> str:
    """The first block plus the blocks most similar to ``requirement``, at most about ``max_chars`` characters."""
    if max_chars <= 0 or len(code) <= max_chars:
        return code
    blocks = _blocks(code, block_chars)
    if len(blocks) <= 1:
        return code[:max_chars]
    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform([split_identifiers(requirement)] + [split_identifiers(b) for b in blocks])
        scores = (matrix[1:] @ matrix[0].T).toarray().ravel()
    except ValueError:  # nothing left after stop-word removal: keep the start of the file
        return code[:max_chars]
    chosen, used = {0}, len(blocks[0])
    for index in sorted(range(1, len(blocks)), key=lambda i: -scores[i]):
        if used + len(blocks[index]) > max_chars:
            continue
        chosen.add(index)
        used += len(blocks[index])
    out, previous = [], -1
    for index in sorted(chosen):
        if previous != -1 and index != previous + 1:
            out.append(GAP)
        out.append(blocks[index])
        previous = index
    if previous != len(blocks) - 1:
        out.append(GAP)
    return "\n".join(out).replace("\n" + GAP + "\n", GAP)
