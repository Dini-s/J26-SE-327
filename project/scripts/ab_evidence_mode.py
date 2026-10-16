"""A/B test on hand-labelled links: does the evidence-first prompt reject the wrong links the standard prompt accepted?

Re-checks the labelled sample (verified links only) with ``--prompt evidence`` (the model must quote code that
satisfies the requirement; the quote is checked against the code). The standard prompt already accepted every
one of these links, so what matters is: of the links the evidence prompt keeps, how many are correct, and how
many correct links it throws away.

    python scripts/ab_evidence_mode.py --project spring-petclinic --labels spring-petclinic_claude
Results are appended to data/results/evidence_ab_<project>.json after every call, so it can be stopped and resumed.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def summarise(rows: list[dict]) -> dict:
    """Standard prompt (accepted all) versus evidence prompt, on the links labelled correct / wrong."""
    judged = [r for r in rows if r["label"] in ("correct", "wrong") and r.get("ev_linked") is not None]
    correct = [r for r in judged if r["label"] == "correct"]
    kept = [r for r in judged if r["ev_linked"]]
    kept_correct = [r for r in kept if r["label"] == "correct"]
    wrong = [r for r in judged if r["label"] == "wrong"]
    return {
        "links_judged": len(judged),
        "standard_precision": round(len(correct) / len(judged), 3) if judged else None,
        "evidence_kept": len(kept),
        "evidence_precision": round(len(kept_correct) / len(kept), 3) if kept else None,
        "correct_links_kept": f"{len(kept_correct)}/{len(correct)}",
        "wrong_links_rejected": f"{sum(1 for r in wrong if not r['ev_linked'])}/{len(wrong)}",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", default="spring-petclinic")
    ap.add_argument("--labels", default="spring-petclinic_claude", help="label file name in data/labels (without .json)")
    ap.add_argument("--n", type=int, default=40)
    args = ap.parse_args()

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from agents.traceability_agent import prompts
    from agents.traceability_agent.preprocess import llm_text
    from apps.api import labeling, sources
    from shared.llm.client import LLMClient
    from shared.uskg.client import USKGClient

    labels = json.loads((ROOT / "data" / "labels" / f"{args.labels}.json").read_text())["labels"]
    sample = labeling.sample_links(sources.neo4j_links(args.project)["links"], args.n)
    with USKGClient() as uskg:
        reqs = {a.id: a for a in uskg.get_artifacts("requirement", project=args.project)}
        targets = {a.id: a for t in ("code", "test", "design") for a in uskg.get_artifacts(t, project=args.project)}

    out = ROOT / "data" / "results" / f"evidence_ab_{args.project}.json"
    rows = json.loads(out.read_text())["rows"] if out.exists() else []
    done = {(r["requirement"], r["code"]) for r in rows}
    llm = LLMClient(system_prompt=prompts.EVIDENCE_SYSTEM_PROMPT, response_mode="evidence")

    for n, link in enumerate(sample, 1):
        key = (link["requirement"], link["code"])
        if key in done:
            continue
        req, tgt = reqs[link["requirement"]], targets[link["code"]]
        t0 = time.time()
        try:
            v = llm.verify_link(req.model_copy(update={"text": llm_text(req)}), tgt.model_copy(update={"text": llm_text(tgt)}))
            row = {"ev_linked": bool(v["is_linked"]) and float(v["confidence"]) >= 0.5, "ev_confidence": v["confidence"], "ev_reason": v["reasoning"]}
        except Exception as exc:  # keep going; a failed call is recorded, not counted
            row = {"ev_linked": None, "ev_confidence": None, "ev_reason": f"error: {type(exc).__name__}: {exc}"[:300]}
        rows.append({
            "requirement": link["requirement"], "code": link["code"], "std_confidence": link["confidence"],
            "label": labels.get(f"{link['requirement']}||{link['code']}", {}).get("label"), "seconds": round(time.time() - t0, 1), **row,
        })
        out.write_text(json.dumps({"project": args.project, "labels": args.labels, "summary": summarise(rows), "rows": rows}, indent=1))
        print(f"{n}/{len(sample)} {link['requirement']} label={rows[-1]['label']} evidence_linked={row['ev_linked']} ({rows[-1]['seconds']} s)", flush=True)
    print(json.dumps(summarise(rows), indent=1))


if __name__ == "__main__":
    main()
