"""How many code candidates per requirement the LLM should check, suggested from the size of the project.

Stage 1 shortlists the top-k code files of each requirement; Stage 2 (the LLM) checks only those. A small project
has few files, so checking all of them is cheap and recall is free. A large project needs a larger k, but each step
up costs LLM time (about SECONDS_PER_CALL per requirement and candidate). The ladder below is the set of values the
user can pick; the suggestion is a rule of thumb, not a measured optimum (see docs/c4_reranker_and_stage1_analysis.md).
"""

from __future__ import annotations

LADDER: tuple[int, ...] = (1, 3, 5, 10, 20, 50, 100)
MAX_K = LADDER[-1]


def suggest_top_k(code_files: int) -> int:
    """Default candidates per requirement for a project with ``code_files`` code, test or design elements.

    Up to 5 elements: check every one (cheap). Up to 30: 10. Larger projects get 20, not more: with the current
    CPU LLM server each candidate costs about a minute per 2 requirements, so a larger default would take days.
    The user can still pick 50 or 100 from the list, and the page shows the estimated time for the choice.
    """
    if code_files <= 5:
        return max(1, code_files)
    if code_files <= 30:
        return 10
    return 20


def options_for(code_files: int) -> list[int]:
    """The choices offered in the UI: every ladder value up to the number of files (a value above the files is pointless)."""
    limit = max(1, code_files)
    return [k for k in LADDER if k <= limit] or [1]


def estimate_minutes(requirements: int, top_k: int, seconds_per_call: float) -> int:
    """Rough LLM time for ``requirements`` x ``top_k`` calls, in minutes."""
    return round(requirements * top_k * seconds_per_call / 60)
