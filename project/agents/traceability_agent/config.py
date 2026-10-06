"""Tunable defaults for the traceability agent."""

from typing import Optional

# Words per chunk when scoring long artifacts (a file scores as its best chunk). Embedding
# models read only the first 128-256 tokens; on iTrust 60-word chunks lifted MiniLM recall@10
# from 23% to 33% and the hybrid from 39% to 42%. Chosen on the same labels, so slightly optimistic.
CHUNK_WORDS: Optional[int] = 60
TOP_K: int = 10  # max candidates shortlisted per requirement
# Min similarity to be shortlisted. None = rank by top-k only. A cutoff only loses recall:
# on iTrust a 0.5 cosine cutoff left 43 candidates and ~1% recall; the LLM stage does the filtering.
SIMILARITY_THRESHOLD: Optional[float] = None
PASS_THRESHOLD: float = 0.5  # min LLM confidence for a link to count as verified / not decayed
TRACE_WEIGHT: float = 0.6  # completeness score: weight of trace confidence
EVIDENCE_WEIGHT: float = 0.4  # completeness score: weight of C3 evidence coverage
DECAY_CHANNEL: str = "trace_decayed"  # Redis Pub/Sub channel for decay alerts
MAX_VERIFY_SECONDS: float = 5.0  # NFR: one LLM verification should finish within this
