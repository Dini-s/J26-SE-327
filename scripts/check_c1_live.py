"""End-to-end check of the RUNNING Component 1 API in live mode (Ollama model), calling it the way the UI does.

    .venv\\Scripts\\python.exe scripts\\check_c1_live.py [--api http://127.0.0.1:8000] [--file PATH] [--timeout 1800] [--keep]

Start the API first with scripts\\run_c1_live.ps1. The script uses its own new project (the UI's existing projects and sources are not touched),
removes the file it uploaded at the end (unless --keep), and exits with 1 and a readable message on any failure. Standard library only
(plus the repo's own pydantic schemas). Nothing is simulated: if Ollama is down the check fails.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "project"))
DEFAULT_FILE = ROOT / "scripts" / "fixtures" / "live_check_srs.txt"
TERMINAL = {"done", "needs_clarification", "failed", "manual_review"}
failures = []
warnings = []
PERCENT = re.compile(r"(\d+(?:[.,]\d+)*)\s*%")


def fail(msg):
    failures.append(msg)
    print(f"  FAIL: {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"  WARN: {msg}")


def call(api, method, path, body=None, files=None, timeout=60):
    headers, data = {}, None
    if files:
        boundary = uuid.uuid4().hex
        parts = []
        for name, content in files:
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\nContent-Type: text/plain\r\n\r\n'.encode() + content + b"\r\n")
        data = b"".join(parts) + f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    req = urllib.request.Request(api + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} -> HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except OSError as e:
        raise SystemExit(f"Cannot reach the API at {api} ({e}). Start it with scripts\\run_c1_live.ps1 and try again.")


def classify_numbers(source_text, extra):
    """Split the numbers a draft added (absent from the source) into (warnings, failures).

    A number that equals 100 minus a percentage written in the source (95% -> 5) is a warning: it is arithmetic on a source figure, but still
    not in the source. Any other absent number is a failure.
    """
    complements = set()
    for p in PERCENT.findall(source_text):
        value = 100 - float(p.replace(",", ""))
        complements.add(str(int(value)) if value == int(value) else str(value))
    warned = [n for n in extra if n in complements]
    return warned, [n for n in extra if n not in complements]


def validate_draft(rid, text, g):
    from agents.requirement_agent import schemas as part_b
    from agents.requirement_agent.api.schemas import GenerationOut
    try:
        GenerationOut.model_validate(g)
    except Exception as exc:
        fail(f"{rid}: API generation block does not match the response schema: {exc}")
    obj = {"status": g["status"], "rationale": g["rationale"]}
    if g["status"] == "ok":
        obj.update(user_story=g["user_story"], technical_task=g["technical_task"], acceptance_criteria=g["acceptance_criteria"])
    else:
        obj["clarification_questions"] = g["clarification_questions"]
    problems = part_b.validate_output(obj)
    if problems:
        fail(f"{rid}: draft fails the Part B output schema: {problems}")
    from agents.requirement_agent import generation
    extra = generation.numbers_not_in_source(text, g)  # the same strict rule the API uses for its numbers_not_in_source field
    if extra != g.get("numbers_not_in_source"):
        fail(f"{rid}: the API field numbers_not_in_source={g.get('numbers_not_in_source')} differs from the strict check {extra}")
    warned, invented = classify_numbers(text, extra)
    if warned:
        warn(f"{rid}: numbers {warned} are not in the requirement text; each is 100 minus a percentage in the source (verify)")
    if invented:
        fail(f"{rid}: numbers {invented} appear in the draft but not in the requirement text")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--file", default=str(DEFAULT_FILE))
    ap.add_argument("--timeout", type=float, default=1800, help="seconds to wait for all drafts (default 1800)")
    ap.add_argument("--keep", action="store_true", help="leave the uploaded file and results in the new project")
    a = ap.parse_args()
    api = a.api.rstrip("/")
    src = Path(a.file)
    if not src.exists():
        raise SystemExit(f"Input file not found: {src}")

    print("1. Health")
    h = call(api, "GET", "/api/health", timeout=10)
    print(f"   {h}")
    if h["generation_backend"] != "ollama":
        raise SystemExit(f"The API runs in '{h['generation_backend']}' mode, not live. Restart it with scripts\\run_c1_live.ps1.")
    if not h["generation_reachable"]:
        raise SystemExit(f"Ollama model '{h['model']}' is not reachable from the API. Start Ollama / create the model (see scripts\\run_c1_live.ps1).")
    if not h["part_a_loaded"]:
        raise SystemExit("Part A models are not loaded by the API.")

    print("2. Upload")
    pid = call(api, "POST", "/api/projects", {"name": f"live-check {time.strftime('%Y-%m-%d %H:%M:%S')}"})["id"]
    up = call(api, "POST", f"/api/projects/{pid}/sources", files=[(src.name, src.read_bytes())])
    if up["rejected"] or not up["accepted"]:
        raise SystemExit(f"Upload rejected: {up['rejected']}")
    sid = up["accepted"][0]["id"]
    print(f"   project {pid}, source {sid} ({src.name})")

    lat = []
    total = 0.0
    try:
        print("3. Analyse (Part A runs now; Part B drafts are queued)")
        t0 = time.time()
        job = call(api, "POST", f"/api/projects/{pid}/analyze?policy=all", timeout=600)  # the check wants a draft for every requirement
        print(f"   Part A done in {time.time() - t0:.1f}s, {job['requirements']} requirements")
        if job["requirements"] == 0:
            raise SystemExit("No requirements were found in the file.")
        seen = {}
        deadline = t0 + a.timeout
        while time.time() < deadline:
            rows = call(api, "GET", f"/api/projects/{pid}/requirements?limit=200")["items"]
            now = time.time()
            for r in rows:
                s = seen.setdefault(r["uid"], {"prev": t0})
                if r["generation_state"] == "running":
                    s.setdefault("start", now)
                if r["generation_state"] in TERMINAL and "end" not in s:
                    s.setdefault("start", s["prev"])
                    s["end"] = now
                if "end" in s:
                    s["prev"] = max(s["prev"], s["end"])
            j = call(api, "GET", f"/api/jobs/{job['job_id']}")
            if j["generation"]["queued"] == 0 and all("end" in seen.get(r["uid"], {}) for r in rows):
                break
            time.sleep(0.5)
        else:
            raise SystemExit(f"Timed out after {a.timeout:.0f}s waiting for drafts: {j['generation']}")
        total = time.time() - t0

        print("4. Results")
        print(f"   {'id':8} {'type':9} {'sec':5} {'amb':7} {'gen':19} {'att':3} {'man':3} {'secs':>6}  text")
        for row in rows:
            d = call(api, "GET", f"/api/requirements/{row['uid']}")
            g, rid = d["generation"], d["id"]
            secs = seen[row["uid"]]["end"] - seen[row["uid"]]["start"]
            lat.append(secs)
            print(f"   {rid:8} {d['classification']['fr_nfr']}:{d['classification']['nfr_probability']:.2f} {str(d['security']['is_security']):5} "
                  f"{d['ambiguity']['label']:7} {g['state']:19} {g['attempts']:<3} {str(g['manual_review'])[0]:3} {secs:6.1f}  {d['original_text'][:70]}")
            print(f"{'':9}weak words: {d['ambiguity']['weak_words'] or '-'}")
            if g["state"] in ("done", "needs_clarification"):
                if g["backend"] != "ollama" or not g["model"].startswith(h["model"].split(":")[0]):
                    fail(f"{rid}: provenance is backend={g['backend']!r} model={g['model']!r}, expected the live Ollama model {h['model']!r}")
                if "from cache" in g["message"]:
                    print(f"{'':9}note: served from the cache of an earlier live run")
                validate_draft(rid, d["original_text"], g)
                if g["state"] == "needs_clarification":
                    print(f"{'':9}asked: {g['clarification_questions']}")
                else:
                    print(f"{'':9}story: {g['user_story']}")
            elif g["state"] == "manual_review":
                fail(f"{rid}: all {g['attempts']} attempts were invalid (manual review): {g['message']}")
            else:
                fail(f"{rid}: generation {g['state']}: {g['message']}")
    finally:
        if not a.keep:
            call(api, "DELETE", f"/api/projects/{pid}/sources/{sid}", timeout=30)

    n = len(lat)
    print(f"\n5. Summary: {n} requirements, {len(failures)} failure(s), {len(warnings)} warning(s). Total {total:.1f}s; per requirement mean {sum(lat) / n:.1f}s, max {max(lat):.1f}s.")
    if failures:
        print("CHECK FAILED:\n  - " + "\n  - ".join(failures))
        return 1
    if warnings:
        print("Warnings (exit code stays 0):\n  - " + "\n  - ".join(warnings))
    print("CHECK PASSED: every draft came from the live model and passed the schema checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
