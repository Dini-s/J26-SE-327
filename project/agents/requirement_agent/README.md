# requirement agent

What this agent does, inputs and outputs.

## Usage

    python -m agents.requirement_agent.agent <document> --out out.csv

Reads .txt, .html, .pdf, .docx or .rtf (legacy binary .doc is not supported: convert it first), segments it into candidate requirements and
adds, per row: FR/NFR type and NFR probability, security flag and cue words, ambiguity label and score with the matched QuRE weak words,
and a duplicate group id. No LLM calls. Needs the models saved by `python -m evaluation.run_baselines --task all`
and `python -m evaluation.duplicates_eval --task seeded`; a missing model stops the run and names the command.

Modules: `ingestion.py` (file -> text), `segmenter.py` (text -> candidate requirements), `features.py`, `classifier.py`, `ambiguity.py`,
`duplicates.py`, `agent.py`. Output rows are unverified candidates (`boundary_status=auto_unverified`).
