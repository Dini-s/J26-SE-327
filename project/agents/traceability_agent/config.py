"""Tunable defaults for the traceability agent."""

TOP_K: int = 10  # max candidates shortlisted per requirement
SIMILARITY_THRESHOLD: float = 0.5  # min cosine similarity to be shortlisted (recall stage)
PASS_THRESHOLD: float = 0.5  # min LLM confidence for a link to count as verified / not decayed
TRACE_WEIGHT: float = 0.6  # completeness score: weight of trace confidence
EVIDENCE_WEIGHT: float = 0.4  # completeness score: weight of C3 evidence coverage
DECAY_CHANNEL: str = "trace_decayed"  # Redis Pub/Sub channel for decay alerts
MAX_VERIFY_SECONDS: float = 5.0  # NFR: one LLM verification should finish within this
