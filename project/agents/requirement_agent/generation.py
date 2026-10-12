"""Optional Part B step: turn one requirement into a user story, technical task and acceptance criteria with a language model.

Off by default: nothing in this module runs unless agent.py is called with --generate. No model weights are loaded here; a backend only
returns text.

    Backend.generate(system, user) -> str
      ReplayBackend   returns the stored output of a JSON list of {id, requirement_text, output} (e.g. evaluation/component1/generation/ft_outputs.json)
      OllamaBackend   OpenAI-compatible chat endpoint (LLM_BASE_URL / LLM_MODEL / LLM_API_KEY, see config.py), standard-library HTTP, no extra package
      MockBackend     scripted replies, for tests

The prompt is the training prompt: system = prompts.SYSTEM_PROMPT, user = "Requirement: <text>". `generate_structured` parses each reply
(first "{" to last "}"), checks it with schemas.validate_output, retries invalid replies (3 attempts in total) and, if all fail, sets
manual_review=True and keeps the last raw reply.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config, schemas
from .prompts import SYSTEM_PROMPT, USER_PREFIX, user_message

MAX_ATTEMPTS = 3
GENERATION_COLUMNS = ["gen_status", "user_story", "technical_task", "acceptance_criteria", "rationale", "clarification_questions",
                      "gen_attempts", "gen_manual_review", "gen_raw_output"]
INVALID = "invalid"


class BackendError(Exception):
    """A backend could not produce a reply (not an invalid reply). Never retried."""


class ReplayMiss(BackendError):
    """The replay file has no stored output for this requirement text."""


def _key(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


class Backend:
    def generate(self, system, user):
        raise NotImplementedError


class MockBackend(Backend):
    """Returns scripted replies in order (the last one repeats); a callable (system, user) -> str is also accepted. Records the calls."""

    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    def generate(self, system, user):
        self.calls.append((system, user))
        if callable(self.replies):
            return self.replies(system, user)
        return self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]


class ReplayBackend(Backend):
    """Looks the requirement text up in a stored list of outputs. A miss raises ReplayMiss (never a guess)."""

    def __init__(self, source):
        records = source
        if not isinstance(source, list):
            path = Path(source)
            if not path.exists():
                raise BackendError(f"replay file not found: {path}")
            try:
                records = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise BackendError(f"replay file is not valid JSON: {path} ({exc.msg})") from exc
        if not isinstance(records, list) or not all(isinstance(r, dict) and "requirement_text" in r and "output" in r for r in records):
            raise BackendError("replay file must be a JSON list of {id, requirement_text, output}")
        self.exact, self.loose = {}, {}
        for r in records:
            self.exact.setdefault(r["requirement_text"], r["output"])
            self.loose.setdefault(_key(r["requirement_text"]), r["output"])

    def generate(self, system, user):
        text = user[len(USER_PREFIX):] if user.startswith(USER_PREFIX) else user
        if text in self.exact:
            return self.exact[text]
        if _key(text) in self.loose:
            return self.loose[_key(text)]
        raise ReplayMiss(f"no stored output for requirement text: {text[:120]!r}")


class OllamaBackend(Backend):
    """POST {LLM_BASE_URL}/chat/completions with the system and user messages. The HTTP client is imported on first use."""

    def __init__(self, settings=None):
        self.settings = settings or config.llm_settings()
        self._seen = {}

    def generate(self, system, user):
        import urllib.error
        import urllib.request

        s = self.settings
        if not s["model"]:
            raise BackendError("LLM_MODEL is not set: set it to the model name served by the Ollama/OpenAI-compatible endpoint")
        repeat = self._seen.get((system, user), 0)
        self._seen[(system, user)] = repeat + 1
        body = {"model": s["model"], "temperature": 0.0 if repeat == 0 else 0.3, "stream": False,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        headers = {"Content-Type": "application/json"}
        if s["api_key"]:
            headers["Authorization"] = f"Bearer {s['api_key']}"
        url = s["base_url"] + "/chat/completions"
        request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=s["timeout"]) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise BackendError(f"could not get a reply from {url}: {exc}") from exc
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise BackendError(f"unexpected reply format from {url}") from exc


@dataclass
class GenerationResult:
    status: str = INVALID
    user_story: str = ""
    technical_task: str = ""
    acceptance_criteria: list = field(default_factory=list)
    rationale: str = ""
    clarification_questions: list = field(default_factory=list)
    attempts: int = 0
    manual_review: bool = False
    raw_output: str = ""
    problems: list = field(default_factory=list)

    def as_columns(self):
        """Values for GENERATION_COLUMNS. Lists are JSON strings; gen_raw_output is filled only when the reply needs manual review."""
        return {
            "gen_status": self.status,
            "user_story": self.user_story,
            "technical_task": self.technical_task,
            "acceptance_criteria": json.dumps(self.acceptance_criteria, ensure_ascii=False),
            "rationale": self.rationale,
            "clarification_questions": json.dumps(self.clarification_questions, ensure_ascii=False),
            "gen_attempts": self.attempts,
            "gen_manual_review": self.manual_review,
            "gen_raw_output": self.raw_output if self.manual_review else "",
        }


def generate_structured(backend, requirement_text, max_attempts=MAX_ATTEMPTS):
    """Ask the backend until it returns a valid reply or the attempts run out. BackendError (including ReplayMiss) propagates."""
    user = user_message(requirement_text)
    result = GenerationResult()
    for attempt in range(1, max_attempts + 1):
        raw = backend.generate(SYSTEM_PROMPT, user)
        result.attempts, result.raw_output = attempt, raw if isinstance(raw, str) else str(raw)
        obj, error = schemas.extract_json(raw)
        problems = [error] if error else schemas.validate_output(obj)
        if not problems:
            result.status = obj["status"]
            result.problems, result.manual_review = [], False
            if obj["status"] == "ok":
                result.user_story, result.technical_task = obj["user_story"].strip(), obj["technical_task"].strip()
                result.acceptance_criteria = [c.strip() for c in obj["acceptance_criteria"]]
            else:
                result.clarification_questions = [q.strip() for q in obj["clarification_questions"]]
            result.rationale = obj["rationale"].strip()
            return result
        result.problems = problems
    result.status, result.manual_review = INVALID, True
    return result


def make_backend(name, replay_file=None):
    if name == "replay":
        if not replay_file:
            raise BackendError("--replay-file is required with --generation-backend replay")
        return ReplayBackend(replay_file)
    if name == "ollama":
        return OllamaBackend()
    raise BackendError(f"unknown generation backend {name!r}: use replay or ollama")
