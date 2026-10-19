"""Paths and environment settings for the API (read when the app is created, so tests can override them)."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WORKSPACE = PROJECT_ROOT / "outputs" / "c1_workspace"
DEFAULT_REPLAY_FILE = PROJECT_ROOT / "evaluation" / "component1" / "generation" / "ft_outputs.json"

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = (".txt", ".md", ".pdf", ".docx")
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]  # the web app's dev server (apps/web) and the old standalone UI use port 5173


def cors_origins(environ=None):
    """The default origins plus the comma-separated list in C1_CORS_ORIGINS (for another dev port or host); '*' is not accepted."""
    raw = (os.environ if environ is None else environ).get("C1_CORS_ORIGINS", "")
    extra = [o.strip().rstrip("/") for o in raw.split(",") if o.strip() and o.strip() != "*"]
    return CORS_ORIGINS + [o for o in extra if o not in CORS_ORIGINS]
DEFAULT_PROJECT_NAME = "Core Banking Platform"
BACKENDS = ("replay", "ollama", "mock")


def workspace_dir(override=None):
    return Path(override or os.environ.get("C1_WORKSPACE") or DEFAULT_WORKSPACE)


def generation_backend_name(override=None):
    name = (override or os.environ.get("C1_GENERATION_BACKEND") or "replay").strip().lower()
    if name not in BACKENDS:
        raise ValueError(f"C1_GENERATION_BACKEND must be one of {list(BACKENDS)}, got {name!r}")
    return name


def replay_file(override=None):
    return Path(override or os.environ.get("C1_REPLAY_FILE") or DEFAULT_REPLAY_FILE)


def configure_embedding_cache(workspace):
    """Keep the API's embedding cache inside the workspace, so running the API never rewrites models/component1/.
    Set C1_USE_MODEL_CACHE=1 to use the cache next to the models instead."""
    from agents.requirement_agent import features
    if os.environ.get("C1_USE_MODEL_CACHE") == "1":
        return
    features.CACHE_DIR = Path(workspace) / "embedding_cache"
    features.CACHE_FILE = features.CACHE_DIR / "all-MiniLM-L6-v2.joblib"
    features._CACHE = None
