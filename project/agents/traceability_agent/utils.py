"""Small helpers for the traceability agent."""

import hashlib

from shared.schemas.traceability import Artifact


def content_hash(source: Artifact, target: Artifact) -> str:
    """Hash the whitespace-normalised texts of a linked pair.

    Stored on the VERIFIED_TRACE edge so the decay monitor can tell cheaply
    whether either side changed since verification (and skip the LLM if not).

    Args:
        source: The requirement side of the link.
        target: The code/design side of the link.

    Returns:
        A hex SHA-256 digest.
    """
    normalised = "\x00".join(" ".join(a.text.split()) for a in (source, target))
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
