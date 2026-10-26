const arr = value => Array.isArray(value) ? value : [];
const num = (...values) => {
  for (const value of values) {
    const n = Number(value);
    if (value !== null && value !== undefined && value !== "" && Number.isFinite(n)) return n;
  }
  return null;
};
const first = (obj, keys, fallback = "") => {
  for (const key of keys) if (obj?.[key] !== undefined && obj?.[key] !== null) return obj[key];
  return fallback;
};

export function getRepositoryDashboardData(results) {
  const r = results || {};
  const summary = r.summary || {};
  const findings = arr(r.architecture_findings);
  const dependencies = arr(r.dependencies);
  const structure = arr(r.structure);
  const evolution = arr(r.evolution);
  const files = arr(r.file_evolution);
  const multimodal = r.multimodal_proxy_predictions || {};
  const predictions = arr(multimodal.predictions);
  const proxy = arr(r.proxy_predictions);

  const riskRows = [...predictions, ...proxy].map((p, i) => {
    const probability = num(p.predicted_probability, p.probability, p.risk_probability, p.score);
    const packageName = first(p, ["package_path", "package", "package_name", "module", "name"], `Package ${i + 1}`);
    return { name: String(packageName), package: String(first(p, ["package_path", "package", "package_name"], packageName)), probability, risk: probability === null ? "UNKNOWN" : probability >= 0.7 ? "HIGH" : probability >= 0.4 ? "MEDIUM" : "LOW", target: p.target, exploratory: multimodal.status === "exploratory" || p.target === "architecture_change_proxy_label" };
  }).filter((row, index, all) => all.findIndex(x => x.name === row.name) === index)
    .sort((a, b) => (b.probability ?? -1) - (a.probability ?? -1));

  const issueCounts = new Map();
  findings.forEach(item => {
    const type = String(first(item, ["finding_type", "issue_type", "type", "category"], "Architecture finding"));
    issueCounts.set(type, (issueCounts.get(type) || 0) + 1);
  });
  const issues = [...issueCounts.entries()].map(([name, value]) => ({ name, value, percentage: findings.length ? Math.round(value / findings.length * 100) : 0 }));

  const recentChanges = files.slice().sort((a, b) => String(first(b, ["last_modified", "date", "timestamp", "last_commit_date"], "")).localeCompare(String(first(a, ["last_modified", "date", "timestamp", "last_commit_date"], "")))).slice(0, 5).map((f, i) => ({
    module: String(first(f, ["package_path", "package", "file_path", "path", "file"], `Changed file ${i + 1}`)),
    commit: String(first(f, ["commit_hash", "commit", "short_hash"], "—")).slice(0, 9),
    description: `${num(f.files_changed, f.change_count, f.commits) ?? "—"} recorded changes`,
    time: String(first(f, ["last_modified", "date", "timestamp", "last_commit_date"], "")),
    changes: num(f.total_churn, f.churn, f.lines_changed) === null ? "—" : `${num(f.total_churn, f.churn, f.lines_changed)} churn`,
    type: "success",
  }));

  const evolutionMetrics = [
    { label: "Files with Evolution", value: num(summary.files_with_evolution, r.file_evolution_count, files.length) },
    { label: "Commits", value: sum(evolution, ["commit_count", "commits"]) },
    { label: "Contributors", value: sum(evolution, ["contributor_count", "contributors"]) },
    { label: "Files Changed", value: sum(evolution, ["files_changed"]) },
    { label: "Total Churn", value: sum(evolution, ["total_churn", "churn"]) },
  ];
  const statCards = [
    { title: "Packages Analyzed", value: num(summary.packages, r.total_packages, structure.length) ?? "—", description: "From repository structure", type: "info", icon: "size" },
    { title: "Dependency Edges", value: num(summary.dependency_edges, dependencies.length) ?? "—", description: "Detected relationships", type: "info", icon: "health" },
    { title: "Architecture Packages", value: num(summary.architecture_packages, arr(r.architecture).length) ?? "—", description: "Included in architecture analysis", type: "success", icon: "drift" },
    { title: "Architecture Findings", value: findings.length, description: "Reported findings/candidates", type: findings.length ? "warning" : "success", icon: "risk" },
    { title: "Files with Evolution", value: num(summary.files_with_evolution, r.file_evolution_count, files.length) ?? "—", description: "Files represented in history", type: "info", icon: "commits" },
    { title: "Risk Predictions", value: riskRows.length, description: "Returned package-level outputs", type: "warning", icon: "shield" },
  ];
  const dataSummary = [
    { label: "Packages", value: num(summary.packages, structure.length) ?? "—" },
    { label: "Dependencies", value: num(summary.dependency_edges, dependencies.length) ?? "—" },
    { label: "Architecture Packages", value: num(summary.architecture_packages, arr(r.architecture).length) ?? "—" },
    { label: "Evolution Files", value: num(summary.files_with_evolution, r.file_evolution_count, files.length) ?? "—" },
    { label: "Findings", value: findings.length },
    { label: "Predictions", value: riskRows.length },
  ];
  return { statCards, riskRows, issues, recentChanges, evolutionMetrics, dataSummary, findings, predictions, summary, multimodal, structure, dependencies, evolution, files };
}
function sum(rows, keys) {
  if (!rows.length) return null;
  let total = 0, found = false;
  rows.forEach(row => { const n = num(...keys.map(k => row?.[k])); if (n !== null) { total += n; found = true; } });
  return found ? total : null;
}
export const displayValue = value => value === null || value === undefined || value === "" ? "—" : Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value);
