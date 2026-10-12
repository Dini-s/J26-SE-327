"""Settings for the optional Part B generation step, read from environment variables (see .env.example).

LLM_BASE_URL   OpenAI-compatible base URL, default http://localhost:11434/v1 (a local Ollama server)
LLM_MODEL      model name sent to the server (no default: the Ollama backend stops with a clear message if it is empty)
LLM_API_KEY    optional bearer token (Ollama ignores it)
LLM_TIMEOUT    seconds to wait for one reply, default 120

Values are read when `llm_settings()` is called, not at import, so tests can set them. Nothing here is used unless --generate is on.
"""
import os

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_TIMEOUT = 120.0


def llm_settings(env=None):
    env = os.environ if env is None else env
    try:
        timeout = float(env.get("LLM_TIMEOUT") or DEFAULT_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    return {
        "base_url": (env.get("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
        "model": env.get("LLM_MODEL") or "",
        "api_key": env.get("LLM_API_KEY") or "",
        "timeout": timeout,
    }
