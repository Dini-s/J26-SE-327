# Component 4: Traceability Agent: how to run it

This guide only covers running the component on your computer. Setup is done once; the "Run" section is what you do each time.

---

## 1. Before you start

Install and check these:

| Need | Check |
|---|---|
| Python 3.9+ | `python3 --version` |
| Neo4j Desktop, database started | http://localhost:7474 opens |
| Redis (only for decay messages to C3) | `redis-cli ping` → `PONG` (install with `brew install redis` if missing) |
| LLM server | it answers at `LLM_BASE_URL` in `.env` |

## 2. Setup (once)

From the `project/` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in NEO4J_PASSWORD, LLM_BASE_URL, LLM_MODEL, LLM_API_KEY
python -m agents.traceability_agent setup   # creates the Neo4j indexes
```

`.env` holds your secrets. Keep it private; it is git-ignored.

Then save the embedding model once (needs internet): open `scripts/download_model.ipynb` in VS Code, choose the Python kernel of `.venv`, and run all cells. It saves the model to `models/` (git-ignored), and the project then runs offline.

## 3. Run

Every time, in this order:

1. Start Neo4j Desktop and its database.
2. Start Redis in its own terminal. Redis only needs to run once per start-up; it keeps running until you stop it:
   ```bash
   redis-server
   ```
   To check it is up, open another terminal and run `redis-cli ping`. It answers `PONG`.
3. Start the web app:
   ```bash  

   cd /Users/habbglobal/Desktop/J26-SE-327/project && source .venv/bin/activate
   python -m apps.api.server
   ```
4. Open **http://127.0.0.1:8000**

Keep the terminal of step 3 open. Closing it stops the app.

## 4. See the Redis messages (what C3 receives)

When a link breaks, C4 sends a `trace_decayed` message to Redis. C3 listens to the same channel. To see the messages yourself:

1. Make sure Redis is running (`redis-cli ping` → `PONG`).
2. Open a **new terminal tab** (not the one running `redis-server`) and start listening. It waits for messages:
   ```bash
   redis-cli subscribe trace_decayed
   ```
   It prints `subscribe` and `trace_decayed` and then waits. Leave it open.
3. In the web app, open **Code changes**, pick a linked file, and press **Commit the change**.
4. In the listening terminal, the message appears:
   ```
   message
   trace_decayed
   {"event": "trace_decayed", "requirementId": "...", "codeEntityId": "...", "previousConfidence": 0.8, "newConfidence": 0.0, "timestamp": "..."}
   ```
   A link that still holds sends no message.

Notes:
- Redis does not store messages. Start listening **before** you commit; a message sent while nobody listens is lost.
- The message can take up to a minute, because C4 re-checks the link with the AI first. An empty file is reported at once.
- To stop listening, press `Ctrl+C`. If the terminal shows `quote>`, a quote was not closed: press `Ctrl+C` and type the command again.
- There must be only **one** Redis server. Check with `lsof -nP -iTCP:6379 -sTCP:LISTEN`: it should list one process. If two appear, stop the extra one (for example `redis-cli -h 127.0.0.1 shutdown nosave`) and start `redis-server` again.

## 5. Load a dataset

The graph starts empty. A dataset becomes a **project** when it is loaded into Neo4j. This is done in a notebook:

1. Open `scripts/load_to_neo4j.ipynb` in VS Code and choose the Python kernel of `.venv`.
2. In the **Settings** cell set `DATASET` to `itrust`, `etour`, `cm1` or `libest`.
3. Run the cells top to bottom. The settings cell prints which database it will write to; check that it is your local Neo4j (`127.0.0.1`).

Running it again is safe. Only run it against your own local Neo4j, never the team's shared graph.

### Spring PetClinic (code structure like C2, requirements like C1)

A ready-made demo project that follows the graph structures C2 and C1 proposed. Only against your own local Neo4j.

```bash
git clone https://github.com/spring-projects/spring-petclinic data/seed/spring-petclinic   # once, about 14 MB
python -m apps.seed.petclinic --dry-run     # analyze and print a summary, writes nothing
python -m apps.seed.petclinic               # write project "spring-petclinic" to Neo4j (safe to repeat)
python -m apps.seed.petclinic --reset       # remove what the seed wrote, then write again
```

It writes `Repository` → `Package` → `CodeFile` (each code file also carries the label `CodeEntity`, which C4 reads) with package metrics (fan-in/out, coupling, instability), file metrics (lines, complexity, maintainability), `DEPENDS_ON` edges and git-history evolution features; and 26 synthetic requirements in C1's shape (`Requirement` with `Document`, `UserStory`, `AcceptanceCriterion`, `TechnicalTask`, `AnalysisFinding`, `Risk`, `SIMILAR_TO`). Three requirements describe features PetClinic does not have, so orphan detection has something to find. C2's machine-learning outputs (embeddings, risk model, SHAP evidence) are not invented. The code is only read, never run. `--reset` also removes links C4 wrote for those seeded nodes.

### Notebooks

These steps are notebooks, not scripts. Each notebook explains its own steps in the cells above the code.

| Notebook | What it does | When |
|---|---|---|
| `scripts/download_model.ipynb` | Saves the embedding model into `models/` so the project works offline | Once, during setup |
| `scripts/load_dataset.ipynb` | Turns a raw dataset into `data/processed/` (artifacts, traces, gold labels) | Only when the processed files must be rebuilt from the raw downloads |
| `scripts/load_to_neo4j.ipynb` | Loads a processed dataset into Neo4j as a project | After setup, and for each dataset you want in the graph |
| `scripts/replay_repo.ipynb` | Replays a real repository's commits (the jbehave demo) | Optional demo |

(The PetClinic seed above is a Python module, `apps/seed/petclinic.py`, not a notebook.)

To use one: open it in VS Code, choose the Python kernel of `.venv`, and run the cells top to bottom. `ipykernel` comes with `requirements.txt`, so nothing extra is needed.

## 6. Use the web app

Choose the **project** at the top, then:

| Tab | Steps | You see |
|---|---|---|
| **Link** | Type a requirement → choose 3 code files → **Find the code** | Candidate files, LINKED / NOT LINKED with the AI's reason. Links are saved to Neo4j |
| **Code change** | Pick a linked file → pick a change → **Commit the change** → **Undo my changes** to restore | Broken links are marked decayed; a message goes to C3 over Redis |
| **Graph** | Look at the project's graph; click a node | Requirements (R), code (C), links, decay records (!) |
| **Results** | Read the measured numbers | Precision, recall, decay detection and the targets |

The bar under the header shows what is running, with progress. A link takes about a minute per code file on the CPU LLM server, so run one at a time.

## 7. Command line

From `project/`, with `.venv` active:

| What | Command |
|---|---|
| Link all requirements of a project | `python -m agents.traceability_agent link --project iTrust --top-k 3` |
| Link chosen requirements only | `python -m agents.traceability_agent link --project iTrust --requirement UC1 --requirement UC10` |
| React to one commit | `python -m agents.traceability_agent changed --project iTrust --code-changed LoginFailureAction` |
| Listen for commits from C2 on Redis | `python -m agents.traceability_agent listen` |
| One decay check of all links | `python -m agents.traceability_agent monitor --once --project iTrust` |
| Completeness and orphans | `python -m agents.traceability_agent score --project iTrust` |
| Run the tests | `python -m pytest -q` |

## 8. Stop

- Web app: press `Ctrl+C` in its terminal.
- Redis: `Ctrl+C` in its terminal.
- Neo4j: stop the database in Neo4j Desktop.

## 9. Problems

| Message | What to do |
|---|---|
| `No such file or directory: .venv/bin/python` | Run step 2 again |
| Port 8000 already in use | A copy is already running. Open http://127.0.0.1:8000, or stop it with `lsof -ti tcp:8000 \| xargs kill` |
| "Neo4j is not reachable" | Start the database in Neo4j Desktop, then reload the page |
| "AI model unreachable" | The LLM server is off, or `LLM_BASE_URL` in `.env` is wrong |
| "Messages to C3 (Redis)" is orange | `redis-server` is not running. Links still work; only the message to C3 is recorded |
| "Something is already running" | Wait for the bar under the header to finish |

## Exports (matrix and reports)

```bash
python -m agents.traceability_agent report --project spring-petclinic --out data/results/trace_report
```

Writes `trace_matrix.csv` (requirement x code; `x0.30` = decayed link), `trace_links.csv` and `trace_report.json` (orphans = never linked, broken = every link decayed, weak = best link under 0.7, plus the decayed-link list). The dashboard's Overview page has the same three downloads.

## Which prompt is used

`link` uses `--prompt evidence` by default: the model must quote code that satisfies the requirement and the quote is checked, which gave 82% precision against 58% for `--prompt expert` on 36 hand-checked PetClinic links, at the cost of missing about a third of the correct links (see `docs/c4_reranker_and_stage1_analysis.md`, section 5.y). Re-checking existing links (`monitor`, `changed`) keeps the more lenient expert prompt so older links do not decay by accident.

## Connection with Component 3 (RVUs and evidence)

C3 stores, per requirement: `(Requirement)-[:HAS_RVU]->(RVU)`, `(RVU)-[:MATCHED_BY]->(ValidationEvidence)`, an `AdequacySummary` (RVC, RVES, adequate / validated RVUs), `QAGap`, `Recommendation`, and `RevalidationCase` linked with `IMPACTED_BY`. C4 does not link code to RVUs directly: the chain is **code file -> (C4 VERIFIED_TRACE) -> requirement -> (C3 HAS_RVU) -> RVU -> evidence**. C4 only **reads** C3's nodes (`USKGClient.get_c3_evidence`, `agents/traceability_agent/c3.py`) and uses them in two places:

* **Completeness score:** a requirement's validation coverage (C3's RVC from its AdequacySummary, else validated RVUs divided by all RVUs, where "validated" = at least one evidence with execution PASS) enters the score as `evidence_coverage` (40%, link confidence 60%). Without C3 data the score is link confidence only. `python -m agents.traceability_agent score` does this automatically.
* **Impact analysis (dashboard, Analytics page):** for a code file, the affected requirements show their RVUs validated and the tests C3 holds for them, i.e. what to re-run after a change.

C4 tells C3 about broken links through the Redis event `trace_decayed`; C3 decides on a `RevalidationCase`.

Assumptions to confirm with C3 (taken from their diagram, not from data, because the graph has no C3 nodes yet): the property name of RVC in `AdequacySummary` (read case-insensitively as `RVC`, either 0.67 or 66.67), that `execution` holds `PASS` for a passing test, that `SUMMARIZED_AS` joins the requirement and its summary (read in either direction), and that RVUs hang off the same `Requirement` nodes that C1 wrote.

## Self-check

```bash
python -m agents.traceability_agent selfcheck --project iTrust      # add --json for the full report
```

No LLM. Checks that both ends of every link exist, no pair is linked twice, confidences are valid, verified links pass the threshold, linked files still contain code, a code quote a link relies on is still in its file, a method named in a reason still exists, every decayed link has its DecayFlag, and that orphans and scores agree with the links. For a ground-truth dataset (iTrust, eTour, CM-1, ...) it also prints precision and recall of the stored links against `data/processed/<name>/traces.json`; recall counts only the true links of requirements C4 has already processed. The same report is on the dashboard (Overview, Health tab). The exit code is 1 if any check fails.
