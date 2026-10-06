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
        user_prompt = self.user_prompt_template.format(
            source_type=source.type,
            source_id=source.id,
            source_text=self._clip(source.text),
            target_type=target.type,
            target_id=target.id,
            target_text=self._clip(target.text),
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
            return VerificationResult(**json.loads(content)).model_dump()
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise LLMResponseError(f"Malformed model response: {content!r}") from exc
