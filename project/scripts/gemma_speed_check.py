"""Re-run Gemma 2 on the same 120 labelled pairs with the speed options on, and compare with the saved baseline.

Speed options (set only for this run, .env is not changed):
  LLM_FOCUS_CHARS=1500      the LLM sees only the code blocks that match the requirement (agents/traceability_agent/focus.py)
  LLM_SHORT_REASONING=1     one short sentence of reasoning

    .venv/bin/python scripts/gemma_speed_check.py            # writes data/results/llm_gemma_focus_short.json (resumable)
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LLM_FOCUS_CHARS", "1500")
os.environ.setdefault("LLM_SHORT_REASONING", "1")

from agents.traceability_agent import prompts  # noqa: E402
from agents.traceability_agent.agent import TraceabilityAgent  # noqa: E402
from agents.traceability_agent.config import FOCUS_CHARS  # noqa: E402
from shared.llm.client import LLMClient  # noqa: E402
from shared.schemas.traceability import Artifact  # noqa: E402

MODEL = "gemma2-8k"
RESULTS = ROOT / "data" / "results"
OUT = RESULTS / "llm_gemma_focus_short.json"
SETS = {"etour": "llm_compare.json", "itrust": "llm_compare.json", "cm1": "llm_compare.json", "petclinic": "llm_compare_petclinic.json"}

base = json.loads((RESULTS / "llm_compare.json").read_text())["models"]["gemma2-8k:latest"]
base_pc = json.loads((RESULTS / "llm_compare_petclinic.json").read_text())["models"]["gemma2-8k:latest"]
baseline = base + base_pc
pairs = [(r["dataset"], r["source"], r["target"], r["label"]) for r in baseline]

arts = {}
for ds in set(d for d, *_ in pairs):
    arts[ds] = {a["id"]: Artifact(**a) for a in json.loads((ROOT / f"data/processed/{ds}/artifacts.json").read_text())}

llm = LLMClient(model=MODEL, system_prompt=prompts.with_short_reasoning(prompts.SYSTEM_PROMPT),
                user_prompt_template=prompts.USER_PROMPT_TEMPLATE)
agent = TraceabilityAgent(uskg=object(), embedder=object(), llm=llm, focus_chars=FOCUS_CHARS)

result = json.loads(OUT.read_text()) if OUT.exists() else {"config": {"focus_chars": FOCUS_CHARS, "short_reasoning": True, "model": MODEL}, "rows": []}
for i, (ds, s, t, y) in enumerate(pairs):
    if i < len(result["rows"]):
        continue
    t0 = time.time()
    try:
        src, tgt = agent.llm_inputs(arts[ds][s], arts[ds][t])
        v = llm.verify_link(src, tgt)
        linked, conf = v["is_linked"], v["confidence"]
    except Exception as exc:  # noqa: BLE001 - a failed answer counts as "no answer", as in the baseline
        print("error", i, type(exc).__name__, str(exc)[:120], flush=True)
        linked, conf = None, None
    result["rows"].append({"dataset": ds, "source": s, "target": t, "label": y, "linked": linked, "confidence": conf,
                           "seconds": round(time.time() - t0, 1)})
    OUT.write_text(json.dumps(result, indent=1))
    print(i + 1, len(pairs), flush=True)


def prf(rows):
    linked = lambda r: bool(r.get("linked"))  # noqa: E731
    tp = sum(r["label"] == 1 and linked(r) for r in rows)
    fp = sum(r["label"] == 0 and linked(r) for r in rows)
    fn = sum(r["label"] == 1 and not linked(r) for r in rows)
    p, rc = tp / max(1, tp + fp), tp / max(1, tp + fn)
    secs = [r["seconds"] for r in rows if r.get("seconds") is not None]
    return {"P": p, "R": rc, "F1": 2 * p * rc / max(1e-9, p + rc), "sec": sum(secs) / len(secs), "none": sum(r.get("linked") is None for r in rows)}


new = result["rows"]
print(f"\n{'':18s}{'P':>6s}{'R':>6s}{'F1':>6s}{'s/answer':>10s}{'no-answer':>10s}")
for label, rows in (("baseline (120)", baseline), ("focus+short (120)", new)):
    m = prf(rows)
    print(f"{label:18s}{m['P']:6.2f}{m['R']:6.2f}{m['F1']:6.2f}{m['sec']:10.1f}{m['none']:10d}")
