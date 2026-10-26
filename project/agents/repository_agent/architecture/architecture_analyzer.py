import argparse
import csv
import json
import re
from pathlib import Path

import networkx as nx

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_COUPLING_THRESHOLD = 4

PACKAGE_PATTERN = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
IMPORT_PATTERN = re.compile(r"^\s*import\s+(?!static\s)([\w.*]+)\s*;", re.MULTILINE)
EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "target",
    "build",
    "out",
    "dist",
    ".gradle",
    ".mvn",
    "vendor",
    "test",
    "tests",
    "generated",
    "generated-sources",
}


def read_csv(file_path):
    if not file_path.exists():
        raise FileNotFoundError(f"Required input file not found: {file_path}")
    with file_path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_csv(file_path, fieldnames, rows):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_source(path):
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError as error:
            print(f"[SOURCE READ WARNING] {path}: {error}")
            return None
    return None


def collect_import_evidence(repo_path, package_names):
    """Map package-level dependency edges to real Java import lines."""
    evidence_by_edge = {}
    repo_path = repo_path.resolve()

    for java_file in repo_path.rglob("*.java"):
        try:
            relative_parts = java_file.relative_to(repo_path).parts
        except ValueError:
            continue
        if any(
            part in EXCLUDED_DIRS or part.startswith(".") for part in relative_parts
        ):
            continue

        content = read_source(java_file)
        if content is None:
            continue

        package_match = PACKAGE_PATTERN.search(content)
        source_package = package_match.group(1) if package_match else ""
        if not source_package:
            continue

        lines = content.splitlines()
        for match in IMPORT_PATTERN.finditer(content):
            imported_name = match.group(1)
            if imported_name.endswith(".*"):
                target_package = imported_name[:-2]
                # Wildcard imports only provide package-level evidence when
                # the imported package is in the discovered structural scope.
                if target_package not in package_names:
                    continue
            else:
                target_package = None
                # Match the longest known package prefix of the imported type.
                for candidate in package_names:
                    if imported_name.startswith(candidate + "."):
                        if target_package is None or len(candidate) > len(
                            target_package
                        ):
                            target_package = candidate
                if target_package is None:
                    continue

            if source_package == target_package:
                continue

            line_number = content.count("\n", 0, match.start()) + 1
            code_line = (
                lines[line_number - 1].strip()
                if line_number <= len(lines)
                else match.group(0).strip()
            )
            record = {
                "source_file": str(java_file.relative_to(repo_path)).replace("\\", "/"),
                "line_number": line_number,
                "code_evidence": code_line,
                "imported_symbol": imported_name,
            }
            evidence_by_edge.setdefault((source_package, target_package), []).append(
                record
            )

    for records in evidence_by_edge.values():
        records.sort(key=lambda item: (item["source_file"], item["line_number"]))
    return evidence_by_edge


def load_layer_rules(rules_path):
    """Load explicit package-to-layer mappings and allowed layer dependencies."""
    if not rules_path:
        return None
    path = Path(rules_path)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Layer rules file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        rules = json.load(file)
    if not isinstance(rules.get("package_layers"), dict):
        raise ValueError("Layer rules must contain a 'package_layers' object")
    if not isinstance(rules.get("allowed_dependencies"), dict):
        raise ValueError("Layer rules must contain an 'allowed_dependencies' object")
    return rules


def resolve_layer(package_name, package_layers):
    """Resolve a package to the longest matching exact/prefix mapping."""
    matches = []
    for prefix, layer in package_layers.items():
        if package_name == prefix or package_name.startswith(prefix + "."):
            matches.append((len(prefix), layer))
    return max(matches, default=(0, None))[1]


def add_layer_violation_findings(repo_name, edges, edge_evidence, findings, rules):
    """Apply user-defined layer rules; do not infer architectural layers automatically."""
    if not rules:
        return 0

    package_layers = rules["package_layers"]
    allowed_dependencies = rules["allowed_dependencies"]
    next_id = 1 + sum(f["finding_type"] == "LAYER_VIOLATION" for f in findings)
    detected = 0

    for source, target in sorted(edges):
        source_layer = resolve_layer(source, package_layers)
        target_layer = resolve_layer(target, package_layers)
        # Unmapped packages cannot be judged against the configured architecture.
        if source_layer is None or target_layer is None:
            continue
        allowed_targets = allowed_dependencies.get(source_layer, [])
        if target_layer in allowed_targets:
            continue

        records = edge_evidence.get((source, target), [])
        evidence_details = " || ".join(
            f"{record['source_file']}:{record['line_number']}: {record['code_evidence']}"
            for record in records
        )
        findings.append(
            {
                "repository": repo_name,
                "finding_id": f"LAYER-{next_id:03d}",
                "finding_type": "LAYER_VIOLATION",
                "severity": rules.get("severity", "Medium"),
                "status": "Candidate",
                "source_package": source,
                "target_package": target,
                "evidence": (
                    f"Configured rule forbids dependency from layer '{source_layer}' "
                    f"to layer '{target_layer}'."
                ),
                "evidence_files": " | ".join(
                    sorted({r["source_file"] for r in records})
                ),
                "evidence_lines": " | ".join(str(r["line_number"]) for r in records),
                "code_evidence": " || ".join(
                    f"{r['source_file']}:{r['line_number']}: {r['code_evidence']}"
                    for r in records
                ),
                "evidence_details": evidence_details,
                "metric_value": f"{source_layer} -> {target_layer}",
                "threshold": f"allowed_dependencies[{source_layer}] contains {target_layer}",
                "notes": (
                    "Rule-based candidate generated from the supplied layer configuration. "
                    "Review the rule and source evidence before confirming the violation."
                    if records
                    else "The dependency edge has no recovered import-line evidence; review the dependency CSV and source discovery."
                ),
            }
        )
        next_id += 1
        detected += 1
    return detected


def calculate_architecture_metrics(repo_name, repo_path):
    """Calculate package metrics and detect graph cycles/coupling candidates."""
    structural_file = (
        PROJECT_ROOT / "data" / "structural" / f"{repo_name}_structure.csv"
    )
    dependency_file = (
        PROJECT_ROOT / "data" / "dependencies" / f"{repo_name}_dependencies.csv"
    )
    structural_rows = read_csv(structural_file)
    dependency_rows = read_csv(dependency_file)

    packages = {}
    for row in structural_rows:
        package = row.get("package_path", "").strip()
        if not package:
            continue
        packages[package] = {
            "repository": repo_name,
            "package_path": package,
            "java_files": int(row.get("java_files") or 0),
            "lines_of_code": int(row.get("lines_of_code") or 0),
            "fan_in": 0,
            "fan_out": 0,
        }

    structural_package_names = set(packages)
    edges, excluded_edges = set(), set()
    blank_edges = self_edges = 0
    for row in dependency_rows:
        source = row.get("source_package", "").strip()
        target = row.get("target_package", "").strip()
        if not source or not target:
            blank_edges += 1
            continue
        if source == target:
            self_edges += 1
            continue
        if (
            source not in structural_package_names
            or target not in structural_package_names
        ):
            excluded_edges.add((source, target))
            continue
        edges.add((source, target))

        edge_evidence = collect_import_evidence(repo_path, structural_package_names)

    graph = nx.DiGraph()
    graph.add_nodes_from(structural_package_names)
    graph.add_edges_from(edges)

    for source, target in edges:
        packages[source]["fan_out"] += 1
        packages[target]["fan_in"] += 1

    for item in packages.values():
        fan_in, fan_out = item["fan_in"], item["fan_out"]
        item["total_coupling"] = fan_in + fan_out
        denominator = fan_in + fan_out
        item["instability"] = fan_out / denominator if denominator else 0.0

    findings = []
    cycle_number = 0
    for component in nx.strongly_connected_components(graph):
        if len(component) > 1:
            cycle_number += 1
            members = sorted(component)
            internal_edges = sorted(
                (s, t) for s, t in edges if s in component and t in component
            )
            evidence_records = []
            for source, target in internal_edges:
                for record in edge_evidence.get((source, target), []):
                    evidence_records.append(
                        {
                            "source_package": source,
                            "target_package": target,
                            **record,
                        }
                    )
            findings.append(
                {
                    "repository": repo_name,
                    "finding_id": f"CYCLE-{cycle_number:03d}",
                    "finding_type": "CIRCULAR_DEPENDENCY",
                    "severity": "High",
                    "status": "Candidate",
                    "source_package": " | ".join(members),
                    "target_package": " | ".join(members),
                    "evidence": "Strongly connected package group; inspect each listed import edge.",
                    "evidence_files": " | ".join(
                        sorted({e["source_file"] for e in evidence_records})
                    ),
                    "evidence_lines": " | ".join(
                        str(e["line_number"]) for e in evidence_records
                    ),
                    "code_evidence": " || ".join(
                        f"{e['source_file']}:{e['line_number']}: {e['code_evidence']}"
                        for e in evidence_records
                    ),
                    "evidence_details": " || ".join(
                        f"{e['source_package']} -> {e['target_package']} | "
                        f"{e['source_file']}:{e['line_number']} | {e['code_evidence']}"
                        for e in evidence_records
                    ),
                    "metric_value": len(members),
                    "threshold": "2 or more mutually reachable packages",
                    "notes": (
                        "Cycle candidate from import-derived package edges. Code evidence shows "
                        "the imports supporting each edge; review the full graph to verify a concrete cycle path."
                        if evidence_records
                        else "Cycle candidate exists in the dependency CSV, but matching import-line evidence was not recovered. "
                        "Check package-name matching and source discovery."
                    ),
                }
            )

    audit = {
        "repository": repo_name,
        "structural_packages": len(structural_package_names),
        "accepted_dependency_edges": len(edges),
        "excluded_dependency_edges": len(excluded_edges),
        "blank_dependency_rows": blank_edges,
        "self_dependency_rows": self_edges,
        "circular_dependency_groups": cycle_number,
        "edges_with_source_evidence": sum(
            1 for edge in edges if edge_evidence.get(edge)
        ),
        "edges_without_source_evidence": sum(
            1 for edge in edges if not edge_evidence.get(edge)
        ),
    }
    return list(packages.values()), audit, findings


def add_coupling_findings(repo_name, metrics, findings, threshold):
    """Add threshold-based coupling candidates; evidence is based on metrics, not code lines."""
    next_id = 1 + sum(f["finding_type"] == "HIGH_COUPLING" for f in findings)
    for item in metrics:
        value = int(item["total_coupling"])
        if value >= threshold:
            findings.append(
                {
                    "repository": repo_name,
                    "finding_id": f"COUPLING-{next_id:03d}",
                    "finding_type": "HIGH_COUPLING",
                    "severity": "Medium",
                    "status": "Candidate",
                    "source_package": item["package_path"],
                    "target_package": "",
                    "evidence": f"fan_in={item['fan_in']}, fan_out={item['fan_out']}, total_coupling={value}",
                    "evidence_files": "",
                    "evidence_lines": "",
                    "code_evidence": "",
                    "evidence_details": "",
                    "metric_value": value,
                    "threshold": threshold,
                    "notes": "Metric-based candidate; no single source line proves high coupling. Review dependency edges and calibrate the threshold.",
                }
            )
            next_id += 1


def save_metrics(repo_name, metrics):
    output_file = (
        PROJECT_ROOT / "data" / "architecture" / f"{repo_name}_architecture.csv"
    )
    fields = [
        "repository",
        "package_path",
        "java_files",
        "lines_of_code",
        "fan_in",
        "fan_out",
        "total_coupling",
        "instability",
    ]
    write_csv(output_file, fields, metrics)
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Calculate architecture metrics and detect cycle/coupling candidates with source evidence"
    )
    parser.add_argument("repo_path", help="Path to the repository being analyzed")
    parser.add_argument(
        "--coupling-threshold",
        type=int,
        default=DEFAULT_COUPLING_THRESHOLD,
        help=f"Flag packages with total coupling >= this value (default: {DEFAULT_COUPLING_THRESHOLD})",
    )
    parser.add_argument(
        "--layer-rules",
        default=None,
        help="Optional JSON file defining package_layers and allowed_dependencies",
    )
    args = parser.parse_args()
    if args.coupling_threshold < 1:
        parser.error("--coupling-threshold must be at least 1")

    repo_path = Path(args.repo_path)
    if not repo_path.is_absolute():
        repo_path = (Path.cwd() / repo_path).resolve()
    if not repo_path.is_dir():
        raise FileNotFoundError(f"Repository directory not found: {repo_path}")

    repo_name = repo_path.name
    metrics, audit, findings = calculate_architecture_metrics(repo_name, repo_path)
    add_coupling_findings(repo_name, metrics, findings, args.coupling_threshold)
    layer_rules = load_layer_rules(args.layer_rules)
    # Reconstruct accepted edges and evidence using the same scope as the metrics.
    structural_package_names = {item["package_path"] for item in metrics}
    dependency_file = (
        PROJECT_ROOT / "data" / "dependencies" / f"{repo_name}_dependencies.csv"
    )
    dependency_rows = read_csv(dependency_file)
    accepted_edges = set()
    for row in dependency_rows:
        source = row.get("source_package", "").strip()
        target = row.get("target_package", "").strip()
        if (
            source
            and target
            and source != target
            and source in structural_package_names
            and target in structural_package_names
        ):
            accepted_edges.add((source, target))
    edge_evidence = collect_import_evidence(repo_path, structural_package_names)
    layer_findings_count = add_layer_violation_findings(
        repo_name, accepted_edges, edge_evidence, findings, layer_rules
    )
    audit["layer_violation_candidates"] = layer_findings_count
    audit["layer_rules_configured"] = int(layer_rules is not None)
    architecture_file = save_metrics(repo_name, metrics)

    audit_dir = PROJECT_ROOT / "data" / "processed" / "architecture_audit"
    audit_file = audit_dir / f"{repo_name}_architecture_scope_audit.csv"
    write_csv(audit_file, list(audit.keys()), [audit])

    findings_file = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "architecture_violations"
        / f"{repo_name}_findings.csv"
    )
    finding_fields = [
        "repository",
        "finding_id",
        "finding_type",
        "severity",
        "status",
        "source_package",
        "target_package",
        "evidence",
        "evidence_files",
        "evidence_lines",
        "code_evidence",
        "evidence_details",
        "metric_value",
        "threshold",
        "notes",
    ]
    write_csv(findings_file, finding_fields, findings)

    print(f"Structural packages analyzed: {len(metrics)}")
    print(f"Accepted dependency edges: {audit['accepted_dependency_edges']}")
    print(f"Circular dependency groups: {audit['circular_dependency_groups']}")
    print(f"Edges with source evidence: {audit['edges_with_source_evidence']}")
    print(f"Edges without source evidence: {audit['edges_without_source_evidence']}")
    print(f"Architecture findings/candidates: {len(findings)}")
    print(f"Architecture metrics saved: {architecture_file}")
    print(f"Scope audit saved: {audit_file}")
    print(f"Findings saved: {findings_file}")
    print(
        "Note: import lines support package-edge evidence; they do not alone prove a design-rule violation."
    )
    if layer_rules:
        print(f"Layer-violation candidates: {layer_findings_count}")
        print(f"Layer rules loaded: {args.layer_rules}")
    else:
        print(
            "Layer-violation detection skipped: pass --layer-rules with explicit mappings and allowed dependencies."
        )


if __name__ == "__main__":
    main()
