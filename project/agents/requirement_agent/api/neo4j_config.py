"""Neo4j and project-stub settings from the environment, with a small, strict reader for the shared .env file.

The shared .env also holds values that belong to other people (LLM_*, REDIS_*, ...). It is therefore NOT loaded into os.environ: `read_env_file`
looks at one line at a time and keeps a value only when the key is on ALLOWED_KEYS; every other line is dropped on the spot, so no LLM_* (or any other)
value is ever read into a variable, stored, logged or returned. The password is never printed: Neo4jConfig hides it in repr().
"""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # project/
REPO_ROOT = PROJECT_ROOT.parent

# the only keys ever taken from an .env file
ALLOWED_KEYS = frozenset({
    "C1_NEO4J_URI", "C1_NEO4J_USER", "C1_NEO4J_PASSWORD", "C1_NEO4J_DATABASE",
    "NEO4J_URI", "NEO4J_USERNAME", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE",
    "C1_PROJECT_ID", "C1_PROJECT_NAME",
})

# files searched in this order; the first one that exists is used (tests replace this list)
ENV_FILES = [REPO_ROOT / ".env", PROJECT_ROOT / ".env"]

DEFAULT_DATABASE = "neo4j"
DEFAULT_PROJECT_ID = "demo-project"
DEFAULT_PROJECT_NAME = "Core Banking Platform"


def read_env_file(path, allowed=ALLOWED_KEYS):
    """{key: value} for the allowed keys of one .env file; a missing or unreadable file gives {}. Other lines are skipped without keeping their value."""
    found = {}
    try:
        handle = open(path, encoding="utf-8-sig")
    except OSError:
        return found
    with handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            if key not in allowed:
                continue  # not ours: the value is never looked at again
            value = value.strip()
            if value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) >= 2:
                value = value[1:-1]
            elif " #" in value:
                value = value.split(" #", 1)[0].rstrip()
            found[key] = value
    return found


def _merged(environ, env_files):
    """Allowed keys only: the environment wins over the file, key by key."""
    env = os.environ if environ is None else environ
    values = {}
    for path in (ENV_FILES if env_files is None else env_files):
        if Path(path).is_file():
            values.update(read_env_file(path))
            break
    values.update({k: env[k] for k in ALLOWED_KEYS if env.get(k)})
    return values


def _first(values, *names):
    for n in names:
        if values.get(n):
            return values[n]
    return ""


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str = ""
    user: str = ""
    password: str = ""
    database: str = DEFAULT_DATABASE

    @property
    def configured(self):
        return bool(self.uri and self.user and self.password)

    @property
    def host(self):
        """Host name only (no port, no credentials, no path)."""
        try:
            return urlparse(self.uri).hostname or ""
        except ValueError:
            return ""

    def __repr__(self):
        return f"Neo4jConfig(host={self.host!r}, database={self.database!r}, user_set={bool(self.user)}, password_set={bool(self.password)})"

    __str__ = __repr__


def load_config(environ=None, env_files=None):
    """C1_NEO4J_* first, then the team's NEO4J_* names; the database defaults to "neo4j"."""
    v = _merged(environ, env_files)
    return Neo4jConfig(
        uri=_first(v, "C1_NEO4J_URI", "NEO4J_URI"),
        user=_first(v, "C1_NEO4J_USER", "NEO4J_USERNAME", "NEO4J_USER"),
        password=_first(v, "C1_NEO4J_PASSWORD", "NEO4J_PASSWORD"),
        database=_first(v, "C1_NEO4J_DATABASE", "NEO4J_DATABASE") or DEFAULT_DATABASE,
    )


def project_stub(environ=None, env_files=None):
    """(project_id, project_name) of the platform project. The platform owns login and projects; until it is connected C1 uses a stub."""
    v = _merged(environ, env_files)
    return v.get("C1_PROJECT_ID") or DEFAULT_PROJECT_ID, v.get("C1_PROJECT_NAME") or DEFAULT_PROJECT_NAME
