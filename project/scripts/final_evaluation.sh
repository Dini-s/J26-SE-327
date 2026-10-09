#!/bin/bash
# Sequential LLM evaluation batch (one CPU LLM server => one request at a time).
# Usage (from the project root):  nohup caffeinate -i bash scripts/final_evaluation.sh &
# Each step logs to data/runs/_logs/; steps 1 and 2 also stream live into the dashboard.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
LOGS=data/runs/_logs; mkdir -p "$LOGS"
G=data/processed/itrust/gold.json; A=data/processed/itrust/artifacts.json
step() { echo "=== $(date '+%H:%M:%S') $1"; }

step "1/3 persona ablation: GENERIC prompt on iTrust (10 requirements x top-5), compare with the expert-persona run"
$PY -W ignore -u -m agents.traceability_agent.evaluate --gold $G --artifacts $A --method full \
    --limit-sources 10 --top-k 5 --prompt generic > "$LOGS/1_ablation_generic.log" 2>&1
step "2/3 link CM-1 into Neo4j (10 requirements x top-4), writing VERIFIED_TRACE edges"
$PY -W ignore -u -m agents.traceability_agent link --limit-sources 10 --top-k 4 > "$LOGS/2_link_cm1.log" 2>&1
step "3/3 decay-injection test on the verified links now in Neo4j"
$PY -W ignore -u -m agents.traceability_agent.decay_injection --neo4j --sample 8 > "$LOGS/3_decay_injection.log" 2>&1
step "done"
