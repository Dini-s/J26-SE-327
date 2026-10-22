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
    """Default candidates per requirement for a project with ``code_files`` code files.

    Up to 5 files: check every file. Then grow with the project: 10 up to 30 files, 20 up to 100,
    50 up to 300, and 100 beyond that.
    """
    if code_files <= 5:
        return max(1, code_files)
    if code_files <= 30:
        return 10
    if code_files <= 100:
        return 20
    if code_files <= 300:
        return 50
    return MAX_K


def options_for(code_files: int) -> list[int]:
    """The choices offered in the UI: every ladder value up to the number of files (a value above the files is pointless)."""
    limit = max(1, code_files)
    return [k for k in LADDER if k <= limit] or [1]


def estimate_minutes(requirements: int, top_k: int, seconds_per_call: float) -> int:
    """Rough LLM time for ``requirements`` x ``top_k`` calls, in minutes."""
    return round(requirements * top_k * seconds_per_call / 60)
