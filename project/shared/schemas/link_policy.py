"""Shared approval policy. AI confidence is a routing signal, not measured accuracy."""
AUTO_APPROVE_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.5


def approval_status(confidence, is_linked=True):
    if not is_linked or confidence < REVIEW_THRESHOLD:
        return "rejected"
    return "verified" if confidence >= AUTO_APPROVE_THRESHOLD else "pending_review"
