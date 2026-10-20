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
import threading
from datetime import datetime
from typing import Any, Optional

from apps.api.sources import PROCESSED_DIR, PROJECT_ROOT, RUNS_DIR, load_dataset

RUN_LOCK = threading.RLock()

SECONDS_PER_CALL = 52  # measured mean on the CPU-only Ollama server; an estimate for the UI only
import re

ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,60}")
# Imported repositories use namespaced graph keys, e.g. aspire/bmi-calc.
PROJECT_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*")
RETRIEVALS = ("hybrid", "embeddings", "tfidf")
KINDS = ("evaluate", "link", "monitor", "changed")
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

    ``kind`` is ``evaluate`` (score against a gold file, nothing written), ``link`` (find links in
    Neo4j and write VERIFIED_TRACE edges) or ``monitor`` (one decay pass).

    Raises:
        RunnerError: On an unknown kind/dataset/retrieval or out-of-range numbers.
    """
    kind = str(params.get("kind", "evaluate"))
    if kind not in KINDS:
        raise RunnerError(f"kind must be one of {KINDS}")
    project = params.get("project") or None
    if project is not None and not (isinstance(project, str) and len(project) <= 200 and PROJECT_PATTERN.fullmatch(project)):
        raise RunnerError("project must be a project key (letters, digits, . _ - and / between name segments; max 200 characters)")
    if kind == "monitor":
        out: dict[str, Any] = {"kind": "monitor", "force": bool(params.get("force", False))}
        return {**out, "project": project} if project else out
    if kind == "changed":  # what C2 would report after a commit: validated by the same rules as a real message
        from agents.traceability_agent.changes import ChangeError, parse_change

        try:
            change = parse_change({"project": project, "changed": params.get("code_changed"), "added": params.get("code_added"),
                                   "requirementsAdded": params.get("requirements_added")})
        except ChangeError as exc:
            raise RunnerError(str(exc)) from exc
        return {"kind": "changed", "project": project, "code_changed": list(change.changed), "code_added": list(change.added),
                "requirements_added": list(change.requirements_added), "top_k": 3}
    retrieval = str(params.get("retrieval", "hybrid"))
    if retrieval not in RETRIEVALS:
        raise RunnerError(f"retrieval must be one of {RETRIEVALS}")
    dataset = str(params.get("dataset", "itrust"))
    if kind == "evaluate" and dataset not in list_datasets():
        raise RunnerError(f"Unknown dataset {dataset!r}")
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
    ids = params.get("requirement_ids") or []
    if kind == "link" and ids:
        if not isinstance(ids, list) or len(ids) > 20 or not all(isinstance(i, str) and ID_PATTERN.fullmatch(i) for i in ids):
            raise RunnerError("requirement_ids must be a list of at most 20 simple ids (letters, digits, . _ -)")
    else:
        ids = []
    out = {"kind": kind, "dataset": dataset, "retrieval": retrieval, "top_k": top_k, "limit_sources": limit, "requirement_ids": ids}
    if kind == "link" and params.get("only_unlinked") and not ids:
        out["only_unlinked"] = True
    return {**out, "project": project} if project and kind == "link" else out


def estimate(params: dict[str, Any]) -> dict[str, Any]:
    """Expected LLM calls and duration (calls = requirements x top_k)."""
    if params["kind"] in ("monitor", "changed"):
        return {"requirements": None, "calls": None, "minutes": None, "note": "one call per link that depends on a changed file"}
    if params["kind"] == "link":
        n = len(params["requirement_ids"]) or params["limit_sources"]
        if n is None:
            return {"requirements": None, "calls": None, "minutes": None, "note": "all requirements in Neo4j; set a limit for an estimate"}
    else:
        artifacts = load_dataset(params["dataset"])["artifacts"]
        n_req = sum(1 for a in artifacts.values() if a["type"] == "requirement")
        n = min(params["limit_sources"] or n_req, n_req)
    calls = n * params["top_k"]
    return {"requirements": n, "calls": calls, "minutes": round(calls * SECONDS_PER_CALL / 60)}


def build_command(params: dict[str, Any]) -> list[str]:
    """Argument list for the process that implements this kind of run."""
    base_cmd = [sys.executable, "-W", "ignore", "-u", "-m"]
    project = ["--project", params["project"]] if params.get("project") else []
    if params["kind"] == "monitor":
        return base_cmd + ["agents.traceability_agent", "monitor", "--once"] + (["--force"] if params["force"] else []) + project
    if params["kind"] == "changed":
        cmd = base_cmd + ["agents.traceability_agent", "changed", "--top-k", str(params["top_k"])] + project
        for flag, key in (("--code-changed", "code_changed"), ("--code-added", "code_added"), ("--requirement-added", "requirements_added")):
            for value in params[key]:
                cmd += [flag, value]
        return cmd
    if params["kind"] == "link":
        cmd = base_cmd + ["agents.traceability_agent", "link", "--top-k", str(params["top_k"]), "--retrieval", params["retrieval"],
                          "--prompt", "expert"] + project   # the dashboard always uses the expert prompt (the measured one)
        for rid in params["requirement_ids"]:
            cmd += ["--requirement", rid]
        if params.get("only_unlinked"):
            cmd += ["--only-unlinked"]
        return cmd + (["--limit-sources", str(params["limit_sources"])] if params["limit_sources"] and not params["requirement_ids"] else [])
    base = PROCESSED_DIR / params["dataset"]
    cmd = base_cmd + [
        "agents.traceability_agent.evaluate",
        "--gold", str(base / "gold.json"), "--artifacts", str(base / "artifacts.json"),
        "--method", "full", "--retrieval", params["retrieval"], "--top-k", str(params["top_k"]),
    ]
    if params["limit_sources"]:
        cmd += ["--limit-sources", str(params["limit_sources"])]
    return cmd


def _external_pids() -> list[int]:
    """PIDs of evaluate runs not started by this dashboard (e.g. from a terminal)."""
    out = subprocess.run(["pgrep", "-f", "--", r"-m agents\.traceability_agent"], capture_output=True, text=True)
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


def _start(params: dict[str, Any], command: Optional[list[str]] = None) -> dict[str, Any]:
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


def start(params: dict[str, Any], command: Optional[list[str]] = None) -> dict[str, Any]:
    with RUN_LOCK:
        return _start(params, command)


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

