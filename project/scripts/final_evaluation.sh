#!/bin/bash
# Sequential LLM evaluation batch (one CPU LLM server => one request at a time).
# Usage (from the project root):  nohup caffeinate -i bash scripts/final_evaluation.sh &
# Needs: the LLM server reachable (LLM_* in .env) and, for step 1, Neo4j with VERIFIED_TRACE links
# (run `python -m agents.traceability_agent link` first). Logs go to data/runs/_logs/.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
LOGS=data/runs/_logs; mkdir -p "$LOGS"
step() { echo "=== $(date '+%H:%M:%S') $1"; }

step "1/3 decay-injection test on the verified links in Neo4j (target: >= 85% of broken links flagged)"
$PY -W ignore -u -m agents.traceability_agent.decay_injection --neo4j --sample 9 > "$LOGS/1_decay_injection.log" 2>&1
step "2/3 persona ablation: GENERIC prompt on iTrust (10 requirements x top-5); compare with the expert-persona result"
$PY -W ignore -u -m agents.traceability_agent.evaluate --gold data/processed/itrust/gold.json --artifacts data/processed/itrust/artifacts.json \
    --method full --limit-sources 10 --top-k 5 --prompt generic > "$LOGS/2_ablation_generic_itrust.log" 2>&1
step "3/3 full pipeline with the expert prompt on eTour (10 requirements x top-5)"
$PY -W ignore -u -m agents.traceability_agent.evaluate --gold data/processed/etour/gold.json --artifacts data/processed/etour/artifacts.json \
    --method full --limit-sources 10 --top-k 5 --prompt expert > "$LOGS/3_full_etour.log" 2>&1
step "done"
