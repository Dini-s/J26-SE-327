# CM-1 Traceability Dataset

Source: https://huggingface.co/datasets/thearod5/CM1 (MIT license)
Domain: NASA science instrument requirements (used as a benchmark in the TraceLLM and NLTrace papers)

## Files
- `artifacts.csv` — 75 requirement artifacts. Columns: `id`, `content` (requirement text), `layer` ("High Level Requirements" or "Low Level Requirements").
- `traces.csv` — 45 ground-truth trace links between artifacts. Columns: `s_id` (source/low-level id), `t_id` (target/high-level id), `label` (1 = true link).

## How to use with your schemas
- Each row of `artifacts.csv` → one `Artifact` (map `layer` to your `type` field, e.g. "requirement").
- Each row of `traces.csv` → one ground-truth `TraceabilityLink` for your `GOLD_STANDARD` set in `evaluate.py`.
- High-level requirements (`SRS...` ids) and low-level requirements (`DPUSDS...` ids) are the two artifact groups being linked — load both groups into your local Neo4j as `:Artifact` nodes, then run `TraceabilityAgent().run(write=False)` and compare its output links against `traces.csv` to compute precision/recall/F1.

Note: `traces.csv` only lists the 45 known TRUE links (label=1). Any pair not listed is assumed to be a non-link (label=0) for scoring purposes.
