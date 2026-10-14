"""Seed the USKG with Spring PetClinic: stand-in for C2 (repository) and C1 (requirements) in the demo.

    git clone https://github.com/spring-projects/spring-petclinic data/seed/spring-petclinic
    .venv/bin/python -m apps.seed.petclinic              # analyze + write to the local Neo4j
    .venv/bin/python -m apps.seed.petclinic --dry-run    # analyze only, print a summary
    .venv/bin/python -m apps.seed.petclinic --reset      # remove what this seed wrote, then write again

What is written (shapes follow the structures C2 and C1 proposed):

C2 side   (:Repository)-[:CONTAINS]->(:Package)-[:CONTAINS]->(:CodeFile:CodeEntity)
          (:Package)-[:DEPENDS_ON]->(:Package), (:CodeFile)-[:DEPENDS_ON]->(:CodeFile),
          (:CodeFile)-[:HAS_EVOLUTION]->(:EvolutionFeature), (:Finding)-[:INVOLVES_PACKAGE]->(:Package)
C1 side   (:Requirement)-[:FROM_DOCUMENT]->(:Document), HAS_STORY->(:UserStory), HAS_CRITERION->(:AcceptanceCriterion),
          HAS_TASK->(:TechnicalTask), HAS_FINDING->(:AnalysisFinding), HAS_RISK->(:Risk), SIMILAR_TO->(:Requirement)

Every code file is ALSO labelled ``CodeEntity`` (id, text, kind, project), which is the type C4 reads, so C4 needs no
change. Metrics are computed from the real source and git history (static, regex-based; the code is never run).
Not seeded: C2's machine-learning outputs (embeddings, XGBoost risk, SHAP evidence, recommendations); they would be
invented. The requirements are synthetic (see ``petclinic_requirements.py``). Nothing outside project
``spring-petclinic`` is touched; writes only run against a local Neo4j.
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from apps.seed import petclinic_requirements as data

PROJECT = "spring-petclinic"
SOURCE = "seed-petclinic"
REPO_URL = "https://github.com/spring-projects/spring-petclinic"
BASE_PACKAGE = "org.springframework.samples.petclinic"
DEFAULT_REPO = Path(__file__).resolve().parents[2] / "data" / "seed" / "spring-petclinic"

_KEYWORDS = {"if", "else", "for", "while", "do", "switch", "case", "break", "continue", "return", "try", "catch", "finally", "throw",
             "throws", "new", "class", "interface", "enum", "record", "extends", "implements", "import", "package", "public", "private",
             "protected", "static", "final", "abstract", "void", "int", "long", "boolean", "double", "float", "this", "super", "instanceof"}


# ------------------------------------------------------------------ analysis (pure: no Neo4j, no network)
@dataclass
class FileInfo:
    id: str
    path: str                  # relative to the repository root
    name: str
    package: str
    language: str
    text: str
    loc: int
    complexity: int
    maintainability: float
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    depends_on: set[str] = field(default_factory=set)          # ids of other files


def strip_comments(source: str) -> str:
    """Java / Thymeleaf-free comment removal (block, line); string contents are kept (only counted as tokens)."""
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    return re.sub(r"(?m)//.*$", "", source)


def measure_java(source: str) -> tuple[int, int, float]:
    """Lines of code, cyclomatic complexity and maintainability index (0..100) of one Java file (approximate)."""
    code = strip_comments(source)
    loc = sum(1 for line in code.splitlines() if line.strip())
    decisions = len(re.findall(r"\b(?:if|for|while|case|catch)\b|&&|\|\||\s\?\s", code))
    complexity = 1 + decisions
    tokens = re.findall(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|&&|\|\||[^\s\w]", re.sub(r'"(?:\\.|[^"\\])*"', '"s"', code))
    n_total, n_distinct = len(tokens), max(2, len(set(tokens)))
    volume = max(1.0, n_total * math.log2(n_distinct))
    mi = (171 - 5.2 * math.log(volume) - 0.23 * complexity - 16.2 * math.log(max(loc, 1))) * 100 / 171
    return loc, complexity, round(max(0.0, min(100.0, mi)), 1)


def file_id(path: str) -> str:
    return f"{PROJECT}:{path}"


def package_id(name: str) -> str:
    return f"{PROJECT}:pkg:{name}"


def scan(root: Path) -> list[FileInfo]:
    """Main Java sources and the Thymeleaf templates, as ``FileInfo`` (package-info files are skipped)."""
    files: list[FileInfo] = []
    for path in sorted((root / "src" / "main").rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if path.suffix == ".java" and path.name != "package-info.java":
            text = path.read_text(encoding="utf-8", errors="replace")
            pkg = (re.search(r"^\s*package\s+([\w.]+);", text, re.M) or [None, "(default)"])[1]
            loc, cc, mi = measure_java(text)
            files.append(FileInfo(file_id(rel), rel, path.name, pkg, "java", text, loc, cc, mi,
                                  classes=re.findall(r"\b(?:class|interface|enum|record)\s+(\w+)", strip_comments(text)),
                                  imports=re.findall(r"^\s*import\s+(?:static\s+)?([\w.]+?)(?:\.\*)?;", text, re.M)))
        elif path.suffix == ".html" and "templates" in path.parts:
            text = path.read_text(encoding="utf-8", errors="replace")
            pkg = "templates" + ("." + path.parent.name if path.parent.name != "templates" else "")
            loc = sum(1 for line in text.splitlines() if line.strip())
            files.append(FileInfo(file_id(rel), rel, path.name, pkg, "html", text, loc, 1 + len(re.findall(r"th:(?:if|unless|each)", text)), 0.0))
    return files


def resolve_dependencies(files: list[FileInfo]) -> None:
    """Fill ``depends_on``: file A depends on B if A mentions a class of B and A is in B's package or imports it."""
    by_fqn: dict[str, FileInfo] = {}
    by_name: dict[str, list[FileInfo]] = {}
    for f in files:
        if f.language != "java":
            continue
        for cls in f.classes:
            by_fqn[f"{f.package}.{cls}"] = f
            by_name.setdefault(cls, []).append(f)
    for f in files:
        if f.language != "java":
            continue
        code = strip_comments(f.text)
        imported = {by_fqn[i].id for i in f.imports if i in by_fqn} | {
            by_fqn[".".join(i.split(".")[:-1])].id for i in f.imports if ".".join(i.split(".")[:-1]) in by_fqn}
        for cls, owners in by_name.items():
            for other in owners:
                if other.id == f.id or not (other.package == f.package or other.id in imported):
                    continue
                if re.search(rf"\b{re.escape(cls)}\b", code):
                    f.depends_on.add(other.id)


def package_metrics(files: list[FileInfo]) -> dict[str, dict[str, Any]]:
    """Per-package size, coupling and a heuristic layer / risk level (labelled as heuristic in the graph)."""
    owner = {f.id: f.package for f in files}
    edges: set[tuple[str, str]] = {(f.package, owner[d]) for f in files for d in f.depends_on if owner[d] != f.package}
    layers = {"model": "domain", "owner": "feature", "vet": "feature", "system": "infrastructure"}
    out: dict[str, dict[str, Any]] = {}
    for pkg in sorted({f.package for f in files}):
        members = [f for f in files if f.package == pkg]
        fan_out = len({b for a, b in edges if a == pkg})
        fan_in = len({a for a, b in edges if b == pkg})
        total = fan_in + fan_out
        instability = round(fan_out / total, 2) if total else 0.0
        avg_cc = sum(f.complexity for f in members) / len(members)
        score = 0.4 * instability + 0.3 * min(total / 10, 1) + 0.3 * min(avg_cc / 15, 1)
        last = pkg.rsplit(".", 1)[-1]
        out[pkg] = {"files": len(members), "loc": sum(f.loc for f in members), "fan_in": fan_in, "fan_out": fan_out,
                    "total_coupling": total, "instability": instability, "avg_complexity": round(avg_cc, 1),
                    "layer": layers.get(last, "view" if pkg.startswith("templates") else "application"),
                    "risk_level": "High" if score >= 0.6 else "Medium" if score >= 0.35 else "Low", "risk_score": round(score, 2)}
    out["__edges__"] = {"edges": sorted(edges)}                       # type: ignore[assignment]
    return out


def circular_dependencies(edges: list[tuple[str, str]]) -> list[list[str]]:
    """Strongly connected groups of more than one package (Tarjan)."""
    graph: dict[str, list[str]] = {}
    for a, b in edges:
        graph.setdefault(a, []).append(b)
        graph.setdefault(b, [])
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    groups: list[list[str]] = []

    def visit(v: str) -> None:
        index[v] = low[v] = len(index)
        stack.append(v)
        on.add(v)
        for w in graph[v]:
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            group = []
            while True:
                w = stack.pop()
                on.discard(w)
                group.append(w)
                if w == v:
                    break
            if len(group) > 1:
                groups.append(sorted(group))

    for v in sorted(graph):
        if v not in index:
            visit(v)
    return groups


def git_evolution(root: Path) -> dict[str, dict[str, Any]]:
    """Per-file commit count, lines added/removed and last change date, from ``git log --numstat`` (renames not followed)."""
    try:
        out = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "log", "--no-renames", "--numstat", "--format=@%H%x09%aI", "--", "src/main"],
                             cwd=root, capture_output=True, text=True, check=True, timeout=120).stdout
    except (subprocess.SubprocessError, OSError):
        return {}
    evo: dict[str, dict[str, Any]] = {}
    date = ""
    for line in out.splitlines():
        if line.startswith("@"):
            date = line.split("\t", 1)[1][:10]
        elif line.strip():
            added, removed, path = (line.split("\t") + ["", "", ""])[:3]
            e = evo.setdefault(path, {"commit_count": 0, "total_insertions": 0, "total_deletions": 0, "last_modified": date, "first_commit": date})
            e["commit_count"] += 1
            e["total_insertions"] += int(added) if added.isdigit() else 0
            e["total_deletions"] += int(removed) if removed.isdigit() else 0
            e["first_commit"] = date                                   # log is newest first, so the last one seen is the oldest
    for e in evo.values():
        e["total_churn"] = e["total_insertions"] + e["total_deletions"]
    return evo


def head_commit(root: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True, timeout=20).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def analyze(root: Path) -> dict[str, Any]:
    """Everything the C2 side needs: files, packages, dependencies, evolution, circular-dependency findings."""
    files = scan(root)
    if not files:
        raise SystemExit(f"error: no source files found under {root}/src/main (is this the spring-petclinic clone?)")
    resolve_dependencies(files)
    packages = package_metrics(files)
    edges = packages.pop("__edges__")["edges"]                         # type: ignore[assignment]
    evolution = git_evolution(root)
    return {"files": files, "packages": packages, "package_edges": edges, "evolution": evolution,
            "cycles": circular_dependencies(edges), "commit": head_commit(root)}


# ------------------------------------------------------------------ requirements (C1 stand-in)
def derive_findings(text: str) -> list[dict[str, Any]]:
    """AnalysisFinding nodes by simple cue-word rules (security cues, vague wording); not an ML result."""
    low = text.lower()
    found = []
    cues = [c for c in data.SECURITY_CUES if c in low]
    if cues:
        found.append({"type": "security", "is_security": True, "cue_words": cues, "confidence": round(min(0.95, 0.6 + 0.1 * len(cues)), 2)})
    weak = [w for w in data.WEAK_WORDS if re.search(rf"\b{re.escape(w)}\b", low)]
    found.append({"type": "ambiguity", "label": "vague" if weak else "clear", "score": round(min(1.0, 0.25 * len(weak)), 2), "weak_words": weak})
    return found


def build_requirements() -> dict[str, Any]:
    """The C1-style nodes for every synthetic requirement, plus TF-IDF similarity between requirements."""
    items = []
    for suffix, rtype, section, text, story, criteria, task, status in data.REQUIREMENTS:
        rid = f"PC-REQ-{suffix}"
        findings = derive_findings(text)
        security = any(f["type"] == "security" for f in findings)
        items.append({"id": rid, "type": rtype, "section": section, "text": text, "status": status,
                      "story": f"As a {story[0]}, I want to {story[1]}, so that {story[2]}.", "criteria": list(criteria), "task": task,
                      "findings": findings,
                      "risk": {"level": "medium" if security else "low", "score": 0.65 if security else 0.2,
                               "reason": "Security-related requirement" if security else "No security or ambiguity cue found"}})
    from sklearn.feature_extraction.text import TfidfVectorizer

    matrix = TfidfVectorizer(stop_words="english").fit_transform([i["text"] for i in items])
    sim = (matrix @ matrix.T).toarray()
    similar = []
    for a in range(len(items)):
        b = max((j for j in range(len(items)) if j != a), key=lambda j: sim[a][j])
        if sim[a][b] >= 0.35 and a < b:
            similar.append((items[a]["id"], items[b]["id"], round(float(sim[a][b]), 2)))
    return {"document": data.DOCUMENT, "items": items, "similar": similar}


# ------------------------------------------------------------------ writing (local Neo4j only)
_C2_QUERIES = [
    ("""MERGE (r:Repository {id: $id}) SET r += $props""", "repository"),
    ("""UNWIND $rows AS row MERGE (p:Package {id: row.id}) SET p += row.props
       WITH p, row MATCH (r:Repository {id: $repo}) MERGE (r)-[:CONTAINS]->(p)""", "packages"),
    ("""UNWIND $rows AS row MERGE (c:CodeEntity {id: row.id}) SET c:CodeFile, c += row.props
       WITH c, row MATCH (p:Package {id: row.package}) MERGE (p)-[:CONTAINS]->(c)""", "files"),
    ("""UNWIND $rows AS row MATCH (a:Package {id: row.a}), (b:Package {id: row.b}) MERGE (a)-[:DEPENDS_ON]->(b)""", "package edges"),
    ("""UNWIND $rows AS row MATCH (a:CodeFile {id: row.a}), (b:CodeFile {id: row.b}) MERGE (a)-[:DEPENDS_ON]->(b)""", "file edges"),
    ("""UNWIND $rows AS row MATCH (c:CodeFile {id: row.file}) MERGE (e:EvolutionFeature {id: row.id}) SET e += row.props
       MERGE (c)-[:HAS_EVOLUTION]->(e)""", "evolution"),
    ("""UNWIND $rows AS row MERGE (f:Finding {id: row.id}) SET f += row.props
       WITH f, row UNWIND row.packages AS pid MATCH (p:Package {id: pid}) MERGE (f)-[:INVOLVES_PACKAGE]->(p)""", "findings"),
]
_C1_QUERIES = [
    ("""MERGE (d:Document {id: $id}) SET d += $props""", "document"),
    ("""UNWIND $rows AS row MERGE (r:Requirement {id: row.id}) SET r += row.props
       WITH r MATCH (d:Document {id: $doc}) MERGE (r)-[:FROM_DOCUMENT]->(d)""", "requirements"),
    ("""UNWIND $rows AS row MATCH (r:Requirement {id: row.req}) MERGE (n:UserStory {id: row.id}) SET n += row.props MERGE (r)-[:HAS_STORY]->(n)""", "stories"),
    ("""UNWIND $rows AS row MATCH (r:Requirement {id: row.req}) MERGE (n:AcceptanceCriterion {id: row.id}) SET n += row.props MERGE (r)-[:HAS_CRITERION]->(n)""", "criteria"),
    ("""UNWIND $rows AS row MATCH (r:Requirement {id: row.req}) MERGE (n:TechnicalTask {id: row.id}) SET n += row.props MERGE (r)-[:HAS_TASK]->(n)""", "tasks"),
    ("""UNWIND $rows AS row MATCH (r:Requirement {id: row.req}) MERGE (n:AnalysisFinding {id: row.id}) SET n += row.props MERGE (r)-[:HAS_FINDING]->(n)""", "findings"),
    ("""UNWIND $rows AS row MATCH (r:Requirement {id: row.req}) MERGE (n:Risk {id: row.id}) SET n += row.props MERGE (r)-[:HAS_RISK]->(n)""", "risks"),
    ("""UNWIND $rows AS row MATCH (a:Requirement {id: row.a}), (b:Requirement {id: row.b}) MERGE (a)-[s:SIMILAR_TO]->(b) SET s.similarity = row.similarity""", "similar"),
]
# only nodes this seed created (source = 'seed-petclinic') of project spring-petclinic are removed; links C4 wrote stay out of it
_RESET = """
MATCH (n) WHERE n.source = $source AND n.project = $project
DETACH DELETE n
"""
_RESET_CHILDREN = """
MATCH (r:Requirement {source: $source, project: $project})-[]->(n) WHERE any(l IN labels(n) WHERE l IN
      ['UserStory','AcceptanceCriterion','TechnicalTask','AnalysisFinding','Risk'])
DETACH DELETE n
"""


def c2_rows(a: dict[str, Any]) -> dict[str, Any]:
    stamp = {"project": PROJECT, "repo": PROJECT, "dataset": PROJECT, "source": SOURCE}
    pkgs = [{"id": package_id(n), "props": {"name": n, "language": "html" if n.startswith("templates") else "java", **m, **stamp,
                                              "layer_source": "heuristic", "risk_source": "heuristic"}} for n, m in a["packages"].items()]
    files = [{"id": f.id, "package": package_id(f.package), "props": {
        "file_path": f.path, "name": f.name, "language": f.language, "kind": "code", "text": f.text, "loc": f.loc,
        "cyclomatic_complexity": f.complexity, "classes": f.classes, **stamp,
        **({"maintainability_index": f.maintainability} if f.language == "java" else {})}} for f in a["files"]]
    evo = [{"id": f"evo:{f.id}", "file": f.id, "props": {**a["evolution"][f.path], "project": PROJECT, "source": SOURCE}}
           for f in a["files"] if f.path in a["evolution"]]
    findings = [{"id": f"{PROJECT}:cycle:{i + 1}", "packages": [package_id(p) for p in group],
                 "props": {"type": "circular_dependency", "cycle_id": f"CYCLE-{i + 1:03d}", "packages": group, "status": "detected", **stamp,
                           "description": "Packages " + " and ".join(g.rsplit('.', 1)[-1] for g in group) + " depend on each other."}}
                for i, group in enumerate(a["cycles"])]
    return {
        "repository": {"id": f"repo:{PROJECT}", "props": {"name": "Spring PetClinic", "language": "Java", "type": "open-source", "url": REPO_URL,
                                                          "commit": a["commit"], **stamp}},
        "packages": pkgs, "files": files, "evolution": evo, "findings": findings,
        "package edges": [{"a": package_id(x), "b": package_id(y)} for x, y in a["package_edges"]],
        "file edges": [{"a": f.id, "b": d} for f in a["files"] for d in sorted(f.depends_on)],
    }


def c1_rows(req: dict[str, Any]) -> dict[str, Any]:
    stamp = {"project": PROJECT, "dataset": PROJECT, "source": SOURCE}
    doc = req["document"]
    out: dict[str, Any] = {"document": {"id": doc["id"], "props": {"name": doc["name"], "type": doc["type"], **stamp}},
                           "requirements": [], "stories": [], "criteria": [], "tasks": [], "findings": [], "risks": [], "similar": []}
    for r in req["items"]:
        out["requirements"].append({"id": r["id"], "props": {"text": r["text"], "type": r["type"], "section": r["section"], "status": r["status"],
                                                             "source_document": doc["name"], **stamp}})
        n = r["id"].split("-")[-1]
        out["stories"].append({"req": r["id"], "id": f"US-PC-{n}", "props": {"text": r["story"], **stamp}})
        for i, c in enumerate(r["criteria"], 1):
            out["criteria"].append({"req": r["id"], "id": f"AC-PC-{n}-{i}", "props": {"text": c, "type": "functional", **stamp}})
        out["tasks"].append({"req": r["id"], "id": f"TASK-PC-{n}", "props": {"text": r["task"], "status": "done" if r["status"] == "approved" else "not_started", **stamp}})
        for i, f in enumerate(r["findings"], 1):
            out["findings"].append({"req": r["id"], "id": f"FIND-PC-{n}-{i}", "props": {**{k: v for k, v in f.items()}, **stamp}})
        out["risks"].append({"req": r["id"], "id": f"RISK-PC-{n}", "props": {**r["risk"], **stamp}})
    out["similar"] = [{"a": a, "b": b, "similarity": s} for a, b, s in req["similar"]]
    return out


def write_graph(analysis: dict[str, Any], reqs: dict[str, Any], driver: Any, reset: bool = False) -> dict[str, int]:
    """Write everything. Raises if Neo4j is not local (same rule as the demo controls)."""
    from apps.api import demo

    state = demo.allowed()
    if not state["allowed"]:
        raise SystemExit(f"error: {state['reason']}")
    counts: dict[str, int] = {}
    if reset:
        driver.execute_query(_RESET_CHILDREN, source=SOURCE, project=PROJECT)
        driver.execute_query(_RESET, source=SOURCE, project=PROJECT)
    c2, c1 = c2_rows(analysis), c1_rows(reqs)
    repo = c2["repository"]
    driver.execute_query(_C2_QUERIES[0][0], id=repo["id"], props=repo["props"])
    for query, key in _C2_QUERIES[1:]:
        rows = c2[key]
        if rows:
            driver.execute_query(query, rows=rows, repo=repo["id"])
        counts["c2 " + key] = len(rows)
    doc = c1["document"]
    driver.execute_query(_C1_QUERIES[0][0], id=doc["id"], props=doc["props"])
    for query, key in _C1_QUERIES[1:]:
        rows = c1[key]
        if rows:
            driver.execute_query(query, rows=rows, doc=doc["id"])
        counts["c1 " + key] = len(rows)
    return counts


def summary(a: dict[str, Any], reqs: dict[str, Any]) -> str:
    lines = [f"repository  Spring PetClinic @ {a['commit'][:7] or '?'}",
             f"packages    {len(a['packages'])}  ({len(a['package_edges'])} dependencies, {len(a['cycles'])} circular)",
             f"code files  {len(a['files'])}  ({sum(f.loc for f in a['files'])} lines, {len(a['evolution'])} with git history)",
             f"requirements {len(reqs['items'])}  ({len(reqs['similar'])} similar pairs)"]
    for name, m in a["packages"].items():
        lines.append(f"  {name.removeprefix(BASE_PACKAGE + '.') or '(root)':<18} files={m['files']:<3} fan_in={m['fan_in']} fan_out={m['fan_out']} "
                     f"instability={m['instability']} risk={m['risk_level']}")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the USKG with Spring PetClinic (C2 + C1 stand-in)")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO, help="path of the spring-petclinic clone")
    parser.add_argument("--dry-run", action="store_true", help="analyze and print a summary, write nothing")
    parser.add_argument("--reset", action="store_true", help="remove what this seed wrote earlier, then write again")
    args = parser.parse_args(argv)
    if not (args.repo / "src" / "main").is_dir():
        print(f"error: {args.repo} is not a spring-petclinic clone. Run:\n  git clone {REPO_URL} {args.repo}", file=sys.stderr)
        return 1
    analysis, reqs = analyze(args.repo), build_requirements()
    print(summary(analysis, reqs))
    if args.dry_run:
        return 0
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    from apps.api.sources import _neo4j_driver

    with _neo4j_driver() as driver:
        counts = write_graph(analysis, reqs, driver, reset=args.reset)
    print("written:", ", ".join(f"{v} {k}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
