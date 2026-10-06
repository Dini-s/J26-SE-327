"""Start / stop pipeline runs from the dashboard.

A run is ``python -m agents.traceability_agent.evaluate --method full ...`` launched as a
detached child process whose events the dashboard then reads from ``data/runs``. Guards:
parameters are validated and bounded, only one run may be active (including runs started
from a terminal, since they would compete for the same slow LLM server), and only runs
started here can be stopped here.
"""

import os
import signal
import subprocess
import sys
from datetime import datetime
from typing import Any, Optional

from apps.api.sources import PROCESSED_DIR, PROJECT_ROOT, RUNS_DIR, load_dataset

SECONDS_PER_CALL = 52  # measured mean on the CPU-only Ollama server; an estimate for the UI only
RETRIEVALS = ("hybrid", "embeddings", "tfidf")
LOGS_DIR = RUNS_DIR / "_logs"
_state: dict[str, Any] = {"proc": None, "params": None, "started": None, "log": None}


class RunnerError(ValueError):
    """Invalid parameters or a start/stop request that cannot be honoured."""


def list_datasets() -> list[str]:
    """Processed datasets that have artifacts and a gold file."""
    if not PROCESSED_DIR.exists():
        return []
    return sorted(
        d.name for d in PROCESSED_DIR.iterdir() if (d / "artifacts.json").exists() and (d / "gold.json").exists()
    )


def validate(params: dict[str, Any]) -> dict[str, Any]:
    """Check and normalise run parameters.

    Raises:
        RunnerError: On an unknown dataset/retrieval or out-of-range numbers.
    """
    dataset = str(params.get("dataset", "itrust"))
    if dataset not in list_datasets():
        raise RunnerError(f"Unknown dataset {dataset!r}")
    retrieval = str(params.get("retrieval", "hybrid"))
    if retrieval not in RETRIEVALS:
        raise RunnerError(f"retrieval must be one of {RETRIEVALS}")
    try:
        top_k = int(params.get("top_k", 5))
        limit = params.get("limit_sources", 10)
        limit = None if limit in (None, "", 0) else int(limit)
    except (TypeError, ValueError) as exc:
        raise RunnerError("top_k and limit_sources must be integers") from exc
    if not 1 <= top_k <= 50:
        raise RunnerError("top_k must be between 1 and 50")
    if limit is not None and not 1 <= limit <= 500:
        raise RunnerError("limit_sources must be between 1 and 500")
    return {"dataset": dataset, "retrieval": retrieval, "top_k": top_k, "limit_sources": limit}


def estimate(params: dict[str, Any]) -> dict[str, Any]:
    """Expected LLM calls and duration (calls = requirements x top_k)."""
    artifacts = load_dataset(params["dataset"])["artifacts"]
    n_req = sum(1 for a in artifacts.values() if a["type"] == "requirement")
    n = min(params["limit_sources"] or n_req, n_req)
    calls = n * params["top_k"]
    return {"requirements": n, "calls": calls, "minutes": round(calls * SECONDS_PER_CALL / 60)}


def build_command(params: dict[str, Any]) -> list[str]:
    """Argument list for the evaluate script."""
    base = PROCESSED_DIR / params["dataset"]
    cmd = [
        sys.executable, "-W", "ignore", "-u", "-m", "agents.traceability_agent.evaluate",
        "--gold", str(base / "gold.json"), "--artifacts", str(base / "artifacts.json"),
        "--method", "full", "--retrieval", params["retrieval"], "--top-k", str(params["top_k"]),
    ]
    if params["limit_sources"]:
        cmd += ["--limit-sources", str(params["limit_sources"])]
    return cmd


def _external_pids() -> list[int]:
    """PIDs of evaluate runs not started by this dashboard (e.g. from a terminal)."""
    out = subprocess.run(["pgrep", "-f", "agents.traceability_agent.evaluate"], capture_output=True, text=True)
    own = _state["proc"].pid if _state["proc"] is not None and _state["proc"].poll() is None else None
    return [int(p) for p in out.stdout.split() if int(p) != own and int(p) != os.getpid()]


def status() -> dict[str, Any]:
    """``idle``, ``running`` (started here), or ``external`` (a run started elsewhere)."""
    proc = _state["proc"]
    if proc is not None and proc.poll() is None:
        return {"state": "running", "pid": proc.pid, "params": _state["params"], "started": _state["started"]}
    external = _external_pids()
    result: dict[str, Any] = {"state": "external" if external else "idle", "external_pids": external}
    if proc is not None:
        result.update(last_exit_code=proc.returncode, last_params=_state["params"])
    return result


def start(params: dict[str, Any], command: Optional[list[str]] = None) -> dict[str, Any]:
    """Launch a run. ``command`` overrides the real command (used by tests).

    Raises:
        RunnerError: If parameters are invalid or another run is active.
    """
    cleaned = validate(params)
    current = status()
    if current["state"] != "idle":
        raise RunnerError(
            "A run is already in progress"
            + (f" (started outside the dashboard, pid {current['external_pids'][0]})" if current["state"] == "external" else "")
        )
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}.log"
    with open(log_path, "w") as log:
        proc = subprocess.Popen(
            command or build_command(cleaned), cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,  # own process group so Stop can kill python and any children
        )
    _state.update(proc=proc, params=cleaned, started=datetime.now().isoformat(timespec="seconds"), log=log_path)
    return {"pid": proc.pid, "params": cleaned, **estimate(cleaned)}


def stop() -> dict[str, Any]:
    """Terminate the run started by the dashboard.

    Raises:
        RunnerError: If no dashboard-started run is active.
    """
    proc = _state["proc"]
    if proc is None or proc.poll() is not None:
        raise RunnerError("No dashboard-started run is active (runs started elsewhere cannot be stopped here)")
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    return {"stopped": proc.pid}


def log_tail(lines: int = 15) -> str:
    """Last lines of the dashboard-started run's console output (for spotting startup errors)."""
    path = _state["log"]
    if path is None or not path.exists():
        return ""
    return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])
