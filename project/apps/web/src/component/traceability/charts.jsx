import { cx } from "./utils";

/** Vertical bars with value labels. items: [{label, count}] */
export function BarChart({ items, tone = "indigo", height = 150 }) {
  const max = Math.max(1, ...items.map((i) => i.count));
  const color = { indigo: "bg-indigo-500", green: "bg-emerald-500", amber: "bg-amber-500" }[tone];
  return (
    <div className="flex items-end gap-3" style={{ height: height + 44 }}>
      {items.map((i) => (
        <div key={i.label} className="flex flex-1 flex-col items-center justify-end gap-1.5">
          <span className="text-[12px] font-semibold tabular-nums text-slate-700">{i.count}</span>
          <div className={cx("w-full max-w-[56px] rounded-t-md", color)} style={{ height: Math.max(3, (i.count / max) * height) }} />
          <span className="text-[11px] text-slate-500">{i.label}</span>
        </div>
      ))}
    </div>
  );
}

/** Cumulative links as an area, decay events as red markers. points: [{day, total, created, decayed}] */
export function Timeline({ points }) {
  if (points.length === 0) return <p className="py-10 text-center text-[13px] text-slate-400">No dated links yet.</p>;
  const W = 640, H = 170, P = { l: 36, r: 12, t: 12, b: 26 };
  const max = Math.max(1, ...points.map((p) => p.total));
  const x = (i) => P.l + (points.length === 1 ? (W - P.l - P.r) / 2 : (i / (points.length - 1)) * (W - P.l - P.r));
  const y = (v) => P.t + (1 - v / max) * (H - P.t - P.b);
  const line = points.map((p, i) => `${i ? "L" : "M"} ${x(i)} ${y(p.total)}`).join(" ");
  const area = `${line} L ${x(points.length - 1)} ${H - P.b} L ${x(0)} ${H - P.b} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Links over time">
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={P.l} x2={W - P.r} y1={y(max * f)} y2={y(max * f)} stroke="#e2e8f0" />
          <text x={P.l - 6} y={y(max * f) + 4} textAnchor="end" fontSize="11" fill="#94a3b8">{Math.round(max * f)}</text>
        </g>
      ))}
      <path d={area} fill="#6366f1" opacity="0.12" />
      <path d={line} fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinejoin="round" />
      {points.map((p, i) => (
        <g key={p.day}>
          <circle cx={x(i)} cy={y(p.total)} r="3.5" fill="#6366f1" />
          {p.decayed > 0 && (
            <g>
              <circle cx={x(i)} cy={y(p.total) - 14} r="8" fill="#ef4444" />
              <text x={x(i)} y={y(p.total) - 10} textAnchor="middle" fontSize="10" fontWeight="700" fill="#fff">{p.decayed}</text>
            </g>
          )}
          <text x={x(i)} y={H - 8} textAnchor="middle" fontSize="11" fill="#64748b">{p.day.slice(5)}</text>
        </g>
      ))}
    </svg>
  );
}
