"""Risk level of one requirement: a transparent scoring rule over the Part A detector outputs.

THIS IS AN UNVALIDATED HEURISTIC, NOT A TRAINED MODEL. The weights below were chosen by hand to make the screen sortable; nobody has checked
them against real project outcomes, so a "HIGH" is a prompt for a human to look, not a measured probability of a defect.

Score (all inputs come from the detectors, nothing else):
    ambiguity label is `defect`        +2   (AMBIGUOUS_POINTS)
    each weak word found               +1   (WEAK_WORD_POINTS), at most +2 in total (WEAK_WORD_MAX)
    security-related                   +1   (SECURITY_POINTS)
    has a duplicate                    +1   (DUPLICATE_POINTS)
    is in a candidate conflict         +1   (CONFLICT_POINTS)
Level: score >= 4 HIGH, 2-3 MEDIUM, 1 LOW, 0 NONE.
"""
AMBIGUOUS_POINTS = 2
WEAK_WORD_POINTS = 1
WEAK_WORD_MAX = 2
SECURITY_POINTS = 1
DUPLICATE_POINTS = 1
CONFLICT_POINTS = 1
HIGH_AT = 4
MEDIUM_AT = 2
LOW_AT = 1
LEVELS = ("HIGH", "MEDIUM", "LOW", "NONE")


def risk_score(ambiguous, weak_word_count, security, has_duplicate, has_conflict):
    score = AMBIGUOUS_POINTS if ambiguous else 0
    score += min(max(int(weak_word_count), 0) * WEAK_WORD_POINTS, WEAK_WORD_MAX)
    score += SECURITY_POINTS if security else 0
    score += DUPLICATE_POINTS if has_duplicate else 0
    score += CONFLICT_POINTS if has_conflict else 0
    return score


def risk_level(score):
    if score >= HIGH_AT:
        return "HIGH"
    if score >= MEDIUM_AT:
        return "MEDIUM"
    if score >= LOW_AT:
        return "LOW"
    return "NONE"


def assess(ambiguous, weak_word_count, security, has_duplicate, has_conflict):
    """(score, level)."""
    score = risk_score(ambiguous, weak_word_count, security, has_duplicate, has_conflict)
    return score, risk_level(score)
