"""Suggested decision for one requirement: a fixed rule over results that already exist. No model call, nothing stored, exported or published.

    reject  the LATER item of a duplicate pair (the reason names the earlier one)
    accept  no ambiguity, no follow-up questions, risk NONE or LOW, no conflict, not a duplicate
    edit    everything else (unclear wording, follow-up questions, conflict, high risk, the earlier item of a duplicate pair)

A suggestion is a hint for the reviewer; only a decision the user makes is recorded.
"""
ACCEPT_RISK_LEVELS = ("NONE", "LOW")  # a higher risk level always needs a look
ACCEPT_MAX_FOLLOW_UP_QUESTIONS = 0  # any question from the draft step means the wording is not clear enough yet

ACCEPT, EDIT, REJECT = "accept", "edit", "reject"
ACTIONS = (ACCEPT, EDIT, REJECT)


def suggest(row, earlier_duplicates, later_duplicates, follow_up_questions):
    """{"action", "reasons"} for one requirement row.

    earlier_duplicates / later_duplicates = display ids of duplicate partners that come before / after this requirement in the document order.
    follow_up_questions = how many follow-up questions the draft step asked for it (0 when it has not been asked)."""
    if earlier_duplicates:
        return {"action": REJECT, "reasons": [f"Repeats {earlier_duplicates[0]}, which comes earlier; keep the first and drop this copy."]}
    reasons = []
    if row["ambiguity_label"] == "defect":
        reasons.append("The wording is unclear.")
    if follow_up_questions > ACCEPT_MAX_FOLLOW_UP_QUESTIONS:
        reasons.append(f"{follow_up_questions} follow-up question{'s' if follow_up_questions != 1 else ''} to answer.")
    if row["conflict_matches"] and row["conflict_matches"] != "[]":
        reasons.append("May conflict with another requirement.")
    if later_duplicates:
        reasons.append(f"Repeated later as {later_duplicates[0]}; decide which wording to keep.")
    if row["risk_level"] not in ACCEPT_RISK_LEVELS:
        reasons.append(f"Risk level is {row['risk_level'].lower()}.")
    if reasons:
        return {"action": EDIT, "reasons": reasons}
    return {"action": ACCEPT, "reasons": ["Clear wording, no open questions, low risk, no conflict or duplicate."]}
