import { linkLabel, linkColor } from "./linkStatus";
import { useState } from "react";
import { shortName } from "./utils";

const ROW = 28;
const TOP = 44;
const WIDTH = 940;
const X_REQ = 230;
const X_CODE = 560;

const edgePath = (x1, y1, x2, y2) => {
  const mid = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`;
};

export function GraphView({ data, selected, onSelect, requirementText }) {
  const { visible, reqs, codes, orphanIds, matches, searching } = data;
  const [hover, setHover] = useState(null);

  const height = Math.max(reqs.length, codes.length) * ROW + TOP + 20;
  const yReq = new Map(reqs.map((id, i) => [id, TOP + i * ROW]));
  const yCode = new Map(codes.map((id, i) => [id, TOP + i * ROW]));
  const active = hover || selected;

  const touches = (l) =>
    active && ((active.type === "req" && l.requirement === active.id) || (active.type === "code" && l.code === active.id));
  const connectedReq = new Set();
  const connectedCode = new Set();
  if (active) {
    visible.filter(touches).forEach((l) => {
      connectedReq.add(l.requirement);
      connectedCode.add(l.code);
    });
  }

  const nodeOpacity = (type, id) => {
    if (active) {
      const same = active.type === type && active.id === id;
      const linked = type === "req" ? connectedReq.has(id) : connectedCode.has(id);
      return same || linked ? 1 : 0.25;
    }
    return searching && !matches(id) ? 0.25 : 1;
  };

  if (reqs.length === 0 && codes.length === 0) {
    return <p className="py-16 text-center text-[13px] text-slate-400">Nothing to show with these filters.</p>;
  }

  return (
    <div className="max-h-[calc(100vh-390px)] min-h-[300px] overflow-auto rounded-lg border border-slate-100 bg-slate-50/40">
      <svg viewBox={`0 0 ${WIDTH} ${height}`} width="100%" style={{ minWidth: 640 }} role="img" aria-label="Requirement to code trace graph">
        <text x={X_REQ} y={20} textAnchor="end" className="fill-slate-500" fontSize="13" fontWeight="600">
          Requirements ({reqs.length})
        </text>
        <text x={X_CODE} y={20} className="fill-slate-500" fontSize="13" fontWeight="600">
          Code files ({codes.length})
        </text>

        <g fill="none">
          {visible.map((l) => {
            const decayed = l.status === "decayed";
            const on = touches(l);
            const dim = active ? !on : searching && !(matches(l.requirement) || matches(l.code));
            const base = 0.18 + 0.5 * (l.confidence ?? 0.5);
            return (
              <path
                key={`${l.requirement}||${l.code}`}
                d={edgePath(X_REQ + 6, yReq.get(l.requirement), X_CODE - 6, yCode.get(l.code))}
                stroke={linkColor(l.status)}
                strokeWidth={on ? 2.4 : 1.2}
                strokeDasharray={decayed || l.status !== "verified" ? "5 4" : undefined}
                opacity={dim ? 0.06 : on ? 0.95 : base}
              />
            );
          })}
        </g>

        {reqs.map((id) => {
          const y = yReq.get(id);
          const orphan = orphanIds.has(id);
          const isSelected = selected?.type === "req" && selected.id === id;
          return (
            <g
              key={id}
              opacity={nodeOpacity("req", id)}
              className="cursor-pointer"
              onMouseEnter={() => setHover({ type: "req", id })}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelect(isSelected ? null : { type: "req", id })}
            >
              <title>{requirementText.get(id) || id}</title>
              <circle cx={X_REQ} cy={y} r={isSelected ? 7 : 5} fill={orphan ? "#fef2f2" : "#4f46e5"} stroke={orphan ? "#dc2626" : "#312e81"} strokeWidth={orphan ? 2 : 1} />
              <text x={X_REQ - 12} y={y + 4} textAnchor="end" fontSize="13" className={orphan ? "fill-red-600" : "fill-slate-700"} fontWeight={isSelected ? 700 : 500}>
                {id}
                {orphan ? "  (no link)" : ""}
              </text>
            </g>
          );
        })}

        {codes.map((id) => {
          const y = yCode.get(id);
          const isSelected = selected?.type === "code" && selected.id === id;
          return (
            <g
              key={id}
              opacity={nodeOpacity("code", id)}
              className="cursor-pointer"
              onMouseEnter={() => setHover({ type: "code", id })}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelect(isSelected ? null : { type: "code", id })}
            >
              <title>{id}</title>
              <rect x={X_CODE - 5} y={y - 5} width={isSelected ? 14 : 10} height={isSelected ? 14 : 10} rx={2} transform={isSelected ? "translate(-2 -2)" : undefined} fill="#0ea5e9" stroke="#075985" />
              <text x={X_CODE + 12} y={y + 4} fontSize="13" className="fill-slate-700" fontWeight={isSelected ? 700 : 500}>
                {shortName(id)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function NodeDetails({ selected, links, orphans, requirementText }) {
  if (!selected) {
    return (
      <div className="space-y-3 text-[13px] text-slate-500">
        <p className="font-semibold text-slate-700">Legend</p>
        <p><span className="mr-2 inline-block h-3 w-3 rounded-full bg-indigo-600 align-middle" />requirement</p>
        <p><span className="mr-2 inline-block h-3 w-3 rounded-sm bg-sky-500 align-middle" />code file</p>
        <p><span className="mr-2 inline-block h-3 w-3 rounded-full border-2 border-red-600 bg-red-50 align-middle" />requirement without a link (orphan)</p>
        <p><span className="mr-2 inline-block h-0.5 w-6 bg-indigo-500 align-middle" />verified link (darker = higher confidence)</p>
        <p><span className="mr-2 inline-block w-6 border-t-2 border-dashed border-red-500 align-middle" />decayed link (kept, flagged)</p>
        <p className="pt-2 text-[12px] text-slate-400">Hover a node to follow its links; click it to read the LLM's reasons here.</p>
      </div>
    );
  }

  const related = links.filter((l) => (selected.type === "req" ? l.requirement === selected.id : l.code === selected.id));
  const isOrphan = selected.type === "req" && orphans.some((o) => o.requirement === selected.id);

  return (
    <div className="space-y-3 text-[13px]">
      <div>
        <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{selected.type === "req" ? "Requirement" : "Code file"}</p>
        <p className="break-all text-sm font-semibold text-slate-900">{selected.type === "req" ? selected.id : shortName(selected.id)}</p>
        {selected.type === "code" && <p className="break-all text-[11px] text-slate-400">{selected.id}</p>}
        {selected.type === "req" && <p className="mt-1 leading-relaxed text-slate-600">{requirementText.get(selected.id) || "-"}</p>}
      </div>
      {isOrphan && <p className="rounded-lg border border-red-100 bg-red-50 p-2 text-red-700">No approved link. Review candidates or create new trace links.</p>}
      <p className="font-semibold text-slate-700">{related.length} link{related.length === 1 ? "" : "s"}</p>
      <ul className="space-y-2">
        {related.map((l) => (
          <li key={`${l.requirement}||${l.code}`} className="rounded-lg border border-slate-100 p-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-medium text-slate-800">{selected.type === "req" ? shortName(l.code) : l.requirement}</span>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${l.status === "verified" ? "bg-emerald-50 text-emerald-600" : l.status === "deferred" ? "bg-slate-100 text-slate-600" : l.status === "decayed" || l.status === "rejected" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>
                {linkLabel(l.status)} {(l.confidence ?? 0).toFixed(2)}
              </span>
            </div>
            <p className="mt-1 leading-relaxed text-slate-500">{l.reason || "No reason stored."}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

const MAX_COLS = 36;

/** The traceability matrix: requirements as rows, code files as columns, confidence as colour. */
export function MatrixView({ data, selected, onSelect, requirementText }) {
  const { visible, reqs, codes, orphanIds } = data;
  const cols = codes.slice(0, MAX_COLS);
  const cell = new Map(visible.map((l) => [`${l.requirement}||${l.code}`, l]));

  if (reqs.length === 0) return <p className="py-16 text-center text-[13px] text-slate-400">Nothing to show with these filters.</p>;

  return (
    <div className="max-h-[calc(100vh-390px)] min-h-[300px] overflow-auto rounded-lg border border-slate-100">
      <table className="border-separate border-spacing-0 text-[11px]">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-20 bg-white px-2 py-1 text-left font-medium text-slate-500">Requirement</th>
            {cols.map((c) => (
              <th key={c} className="sticky top-0 z-10 h-28 min-w-[22px] bg-white px-0.5 align-bottom font-medium text-slate-500" title={c}>
                <span style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }} className="inline-block max-h-28 overflow-hidden">
                  {shortName(c)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {reqs.map((r) => (
            <tr key={r} className={selected?.type === "req" && selected.id === r ? "bg-indigo-50/60" : ""}>
              <td
                onClick={() => onSelect({ type: "req", id: r })}
                title={requirementText.get(r) || r}
                className={`sticky left-0 z-10 cursor-pointer whitespace-nowrap bg-white px-2 py-0.5 font-medium ${orphanIds.has(r) ? "text-red-600" : "text-slate-700"}`}
              >
                {r}
                {orphanIds.has(r) && " (no link)"}
              </td>
              {cols.map((c) => {
                const l = cell.get(`${r}||${c}`);
                return (
                  <td key={c} className="p-0.5" title={l ? `${r} to ${c}\n${l.status} ${(l.confidence ?? 0).toFixed(2)}` : undefined}>
                    <div
                      className={`h-4 w-4 rounded-sm ${l ? "" : "bg-slate-100/70"}`}
                      style={l ? { background: linkColor(l.status) } : undefined}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {codes.length > MAX_COLS && <p className="p-2 text-[11px] text-slate-400">Showing the {MAX_COLS} most-linked of {codes.length} code files.</p>}
    </div>
  );
}
