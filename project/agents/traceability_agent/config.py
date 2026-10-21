"""Tunable defaults for the traceability agent."""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # so LLM_FOCUS_CHARS in .env is seen when this module is imported

# Words per chunk when scoring long artifacts (a file scores as its best chunk). Embedding
# models read only the first 128-256 tokens; on iTrust 60-word chunks lifted MiniLM recall@10
# from 23% to 33% and the hybrid from 39% to 42%. Chosen on the same labels, so slightly optimistic.
CHUNK_WORDS: Optional[int] = 60
TOP_K: int = 10  # max candidates shortlisted per requirement
# Min similarity to be shortlisted. None = rank by top-k only. A cutoff only loses recall:
# on iTrust a 0.5 cosine cutoff left 43 candidates and ~1% recall; the LLM stage does the filtering.
SIMILARITY_THRESHOLD: Optional[float] = None
PASS_THRESHOLD: float = 0.5  # minimum positive AI verdict to retain a candidate; auto-approval uses shared.schemas.link_policy
DECAY_MIN_DROP: float = 0.2  # a still-"linked" re-check only decays a link if confidence fell by at least this much (LLM noise)
TRACE_WEIGHT: float = 0.6  # completeness score: weight of trace confidence
EVIDENCE_WEIGHT: float = 0.4  # completeness score: weight of C3 evidence coverage
DECAY_CHANNEL: str = "trace_decayed"  # Redis Pub/Sub channel for decay alerts
# Channel C2 is expected to publish repository changes on. ASSUMED name and message shape: confirm with C2.
CHANGE_CHANNEL: str = "code_changed"
MAX_VERIFY_SECONDS: float = 5.0  # NFR: one LLM verification should finish within this
# Characters of code shown to the LLM per candidate: the blocks of the file that match the requirement (0 = the whole file,
# as measured so far). Shorter prompts are faster on a CPU server; see agents/traceability_agent/focus.py.
FOCUS_CHARS: int = int(os.getenv("LLM_FOCUS_CHARS") or 0)
