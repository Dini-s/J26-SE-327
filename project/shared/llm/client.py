"""OpenAI wrapper shared by all agents."""

import json
import os
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from shared.schemas.traceability import Artifact

DEFAULT_SYSTEM_PROMPT = (
    "You judge whether two software artifacts are related. "
    'Reply only with JSON: {"is_linked": bool, "confidence": float 0-1, "reasoning": str}.'
)
DEFAULT_USER_PROMPT_TEMPLATE = (
    "Source ({source_type}) {source_id}:\n{source_text}\n\n"
    "Target ({target_type}) {target_id}:\n{target_text}"
)


class LLMResponseError(ValueError):
    """Raised when the model's reply is not the JSON structure we asked for."""


class VerificationResult(BaseModel):
    """Validated structure of a ``verify_link`` reply."""

    is_linked: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


# "evidence" replies: coverage is a category (small models give a meaningless 0.8 for every float), mapped to a score.
COVERAGE_CONFIDENCE = {"full": 0.9, "partial": 0.6, "none": 0.1}


def _squash(text: str) -> str:
    return "".join(text.split()).lower()


def parse_evidence_reply(data: dict[str, Any], target_text: str) -> dict[str, Any]:
    """Turn an evidence-style reply into the standard verdict, checking the quote against the code.

    A link is only accepted if the model quotes a snippet that really occurs in the target; a made-up or
    missing quote downgrades the verdict to "none". Pieces of a quote joined by ``...`` are checked separately.

    Raises:
        LLMResponseError: If ``coverage`` is not full / partial / none.
    """
    coverage = str(data.get("coverage", "")).strip().lower()
    if coverage not in COVERAGE_CONFIDENCE:
        raise LLMResponseError(f"coverage must be full, partial or none, got {data.get('coverage')!r}")
    quote = str(data.get("evidence") or "").strip()
    pieces = [p for p in (quote.split("...") if quote else []) if len(_squash(p)) >= 8]
    grounded = bool(pieces) and all(_squash(p) in _squash(target_text) for p in pieces)
    reasoning = str(data.get("reasoning") or "").strip()
    if coverage != "none" and not grounded:
        coverage, reasoning = "none", f"Rejected: the quoted evidence is missing or not in the code. {reasoning}"
    elif grounded and coverage != "none":
        reasoning = f'{reasoning} Evidence: "{quote}"'
    return {"is_linked": coverage != "none", "confidence": COVERAGE_CONFIDENCE[coverage], "reasoning": reasoning}


class LLMClient:
    """OpenAI chat wrapper that returns structured (JSON) verdicts, never free text."""

    def __init__(
        self,
        model: Optional[str] = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        user_prompt_template: str = DEFAULT_USER_PROMPT_TEMPLATE,
        temperature: float = 0.0,
        max_retries: int = 3,
        client: Optional[Any] = None,
        max_artifact_chars: Optional[int] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        response_mode: str = "score",
    ) -> None:
        """Create the client.

        Args:
            model: Chat model name; defaults to ``LLM_MODEL``, then ``OPENAI_MODEL``, then
                ``gpt-4o-mini``.
            system_prompt: System message. Agents pass their own persona prompt.
            user_prompt_template: ``str.format`` template with ``source_*`` / ``target_*`` fields.
            temperature: Sampling temperature (0 for reproducible verdicts).
            max_retries: Retries the OpenAI SDK applies to transient errors (429/5xx/timeouts).
            client: Pre-built OpenAI client, mainly for tests. Created lazily if omitted.
            max_artifact_chars: Each artifact's text is cut to this length in the prompt (default
                ``LLM_MAX_ARTIFACT_CHARS`` or 6000; lower it for slow CPU-only servers), so
                huge source files (some are >200k characters) can't blow the context window
                or the latency budget.
            base_url: Any OpenAI-compatible endpoint, e.g. a self-hosted Ollama server
                (``http://host:11434/v1``). Defaults to ``LLM_BASE_URL``; unset means OpenAI.
            api_key: Defaults to ``LLM_API_KEY``, then ``OPENAI_API_KEY``. Self-hosted
                servers that don't check keys get a placeholder.
            response_mode: ``score`` (reply has is_linked / confidence / reasoning) or ``evidence`` (reply has a
                quoted snippet and a full / partial / none coverage; see ``parse_evidence_reply``).
            timeout: Per-request timeout in seconds (default ``LLM_TIMEOUT`` or 120). Raise it for a
                shared CPU server where requests queue behind each other.
        """
        load_dotenv()
        self.model: str = (
            model or os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        )
        self.base_url = base_url or os.getenv("LLM_BASE_URL") or None
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or None
        self.timeout: float = timeout or float(os.getenv("LLM_TIMEOUT") or 120.0)
        if response_mode not in ("score", "evidence"):
            raise ValueError(f"Unknown response_mode: {response_mode!r}")
        self.response_mode = response_mode
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.temperature = temperature
        self.max_retries = max_retries
        self.max_artifact_chars: int = max_artifact_chars or int(
            os.getenv("LLM_MAX_ARTIFACT_CHARS") or 6000
        )
        self._client = client

    @property
    def client(self) -> Any:
        """The OpenAI-compatible client, created on first use."""
        if self._client is None:
            from openai import OpenAI

            api_key = self.api_key or ("not-needed" if self.base_url else None)
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=api_key,
                max_retries=self.max_retries,
                timeout=self.timeout,
            )
        return self._client

    def _clip(self, text: str) -> str:
        """Truncate over-long artifact text, marking the cut."""
        if len(text) <= self.max_artifact_chars:
            return text
        return text[: self.max_artifact_chars] + "\n...[truncated]"

    def verify_link(self, source: Artifact, target: Artifact) -> dict[str, Any]:
        """Ask the model whether ``source`` and ``target`` are traceably related.

        Uses JSON mode so the reply is machine-parseable, then validates it.

        Args:
            source: The source artifact.
            target: The target artifact.

        Returns:
            ``{"is_linked": bool, "confidence": float, "reasoning": str}``.

        Raises:
            LLMResponseError: If the reply is empty, not JSON, or fails validation.
        """
        target_text = self._clip(target.text)
        user_prompt = self.user_prompt_template.format(
            source_type=source.type,
            source_id=source.id,
            source_text=self._clip(source.text),
            target_type=target.type,
            target_id=target.id,
            target_text=target_text,
        )
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise LLMResponseError("Empty response from model.")
        try:
            data = json.loads(content)
            if self.response_mode == "evidence":
                return VerificationResult(**parse_evidence_reply(data, target_text)).model_dump()
            return VerificationResult(**data).model_dump()
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise LLMResponseError(f"Malformed model response: {content!r}") from exc
