"""Compare the three local verifier LLMs on one project: 30 true + 30 non-link pairs (fixed seed), expert prompt.

    .venv/bin/python scripts/llm_compare_projects.py petclinic   # writes data/results/llm_compare_<project>.json (resumable)
    .venv/bin/python scripts/llm_compare_projects.py libest

PetClinic labels are the hand-written gold of apps/seed/petclinic_gold.py (not a published benchmark).
"""
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.traceability_agent import prompts  # noqa: E402
from shared.llm.client import LLMClient  # noqa: E402
from shared.schemas.traceability import Artifact  # noqa: E402

MODELS = ["llama3.1-8k:latest", "qwen2.5-coder-8k:latest", "gemma2-8k:latest"]
PROJECT = sys.argv[1] if len(sys.argv) > 1 else "libest"
OUT = ROOT / "data" / "results" / f"llm_compare_{PROJECT}.json"
PER_CLASS, SEED = 30, 7

arts = {a["id"]: Artifact(**a) for a in json.loads((ROOT / f"data/processed/{PROJECT}/artifacts.json").read_text())}
if PROJECT == "petclinic":
    from apps.seed import petclinic_gold  # noqa: E402
    truth = {(r, c) for r, cs in petclinic_gold.gold_pairs().items() for c in cs}
    reqs = sorted((a for a in arts.values() if a.type == "requirement" and any(r == a.id for r, _ in truth)), key=lambda x: x.id)
    gold = [[r.id, c.id, (r.id, c.id) in truth] for r in reqs for c in sorted(arts.values(), key=lambda x: x.id) if c.type == "code"]
else:
    gold = json.loads((ROOT / f"data/processed/{PROJECT}/gold.json").read_text())
rng = random.Random(SEED)
pos = rng.sample([g for g in gold if g[2]], PER_CLASS)
neg = rng.sample([g for g in gold if not g[2]], PER_CLASS)
pairs = pos + neg
rng.shuffle(pairs)

result = json.loads(OUT.read_text()) if OUT.exists() else {"models": {}}
for model in MODELS:
    llm = LLMClient(model=model, system_prompt=prompts.SYSTEM_PROMPT, user_prompt_template=prompts.USER_PROMPT_TEMPLATE)
    rows = result["models"].setdefault(model, [])
    for s, t, y in pairs[len(rows):]:
        t0 = time.time()
        try:
            v = llm.verify_link(arts[s], arts[t]); linked, conf = v["is_linked"], v["confidence"]
        except Exception as exc:  # noqa: BLE001 - a bad answer counts as "no answer"
            linked, conf = None, None
        rows.append({"dataset": PROJECT, "source": s, "target": t, "label": 1 if y else 0, "linked": linked, "confidence": conf, "seconds": round(time.time() - t0, 1)})
        OUT.write_text(json.dumps(result, indent=1))
    print(model, len(rows), "done", flush=True)
