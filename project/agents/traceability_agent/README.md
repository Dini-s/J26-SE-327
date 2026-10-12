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
python scripts/download_model.py   # saves the embedding model to models/ (needs internet once)
python -m agents.traceability_agent setup   # creates the Neo4j indexes
```

`.env` holds your secrets. Keep it private; it is git-ignored.

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
   source .venv/bin/activate
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

The graph starts empty. A dataset becomes a **project** when loaded:

```bash
python scripts/load_to_neo4j.py --artifacts data/processed/itrust/artifacts.json
```

Other ready datasets: `etour`, `cm1`, `libest` (change the folder name). Running it again is safe.

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
