import { GitBranch, Link2 } from "lucide-react";

const SelectedModule = ({
  selectedPackage,
  structure = [],
  edges = [],
  metricsByPackage = new Map(),
  findings = [],
}) => {
  const packagePath = selectedPackage || structure[0]?.package_path;
  const structureRow =
    structure.find((row) => row.package_path === packagePath) || {};
  const metrics = metricsByPackage.get(packagePath) || {};
  const outgoing = edges.filter((edge) => edge.source === packagePath);
  const incoming = edges.filter((edge) => edge.target === packagePath);
  const relatedFindings = findings.filter(
    (item) =>
      String(item.source_package || "").includes(packagePath || "") ||
      String(item.target_package || "").includes(packagePath || ""),
  );

  if (!packagePath)
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500">
        Select a package in the graph to inspect its metrics.
      </section>
    );

  const rows = [
    ["Java files", structureRow.java_files ?? "—"],
    ["Lines of code", structureRow.lines_of_code ?? "—"],
    ["Outgoing dependencies", outgoing.length],
    ["Incoming dependencies", incoming.length],
    ["Fan-in", metrics.fan_in ?? incoming.length],
    ["Fan-out", metrics.fan_out ?? outgoing.length],
    ["Total coupling", metrics.total_coupling ?? "—"],
    [
      "Instability",
      typeof metrics.instability === "number"
        ? metrics.instability.toFixed(3)
        : (metrics.instability ?? "—"),
    ],
  ];
  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start gap-2">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
          <GitBranch size={17} />
        </div>
        <div className="min-w-0">
          <h2 className="break-all text-sm font-bold text-slate-800">
            Selected package
          </h2>
          <p className="mt-1 break-all text-xs text-slate-500">{packagePath}</p>
        </div>
      </div>
      <div className="mt-4 border-b border-slate-100 pb-3">
        <h3 className="text-xs font-bold text-slate-700">Dependency metrics</h3>
        <div className="mt-3 space-y-2">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-start justify-between gap-3">
              <span className="text-xs text-slate-500">{label}</span>
              <span className="text-right text-xs font-semibold text-slate-700">
                {value}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-4">
        <h3 className="text-xs font-bold text-slate-700">
          Outgoing dependencies{" "}
          <span className="font-normal text-slate-400">
            ({outgoing.length})
          </span>
        </h3>
        <div className="mt-2 space-y-2">
          {outgoing.map((edge) => (
            <div key={edge.id} className="flex items-start gap-2">
              <Link2 size={12} className="mt-0.5 shrink-0 text-blue-500" />
              <span className="break-all text-xs text-slate-600">
                {edge.target}
              </span>
            </div>
          ))}
          {!outgoing.length && (
            <p className="text-xs text-slate-400">
              No outgoing accepted edges.
            </p>
          )}
        </div>
      </div>
      <div className="mt-4">
        <h3 className="text-xs font-bold text-slate-700">
          Incoming dependencies{" "}
          <span className="font-normal text-slate-400">
            ({incoming.length})
          </span>
        </h3>
        <div className="mt-2 space-y-2">
          {incoming.map((edge) => (
            <div key={edge.id} className="flex items-start gap-2">
              <Link2 size={12} className="mt-0.5 shrink-0 text-emerald-500" />
              <span className="break-all text-xs text-slate-600">
                {edge.source}
              </span>
            </div>
          ))}
          {!incoming.length && (
            <p className="text-xs text-slate-400">
              No incoming accepted edges.
            </p>
          )}
        </div>
      </div>
      <div className="mt-4 border-t border-slate-100 pt-3">
        <p className="text-xs text-slate-500">
          Related analyzer findings:{" "}
          <span className="font-semibold text-slate-700">
            {relatedFindings.length}
          </span>
        </p>
      </div>
    </section>
  );
};
export default SelectedModule;
