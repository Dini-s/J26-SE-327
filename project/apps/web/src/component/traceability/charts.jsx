import { useLayoutEffect, useRef, useState } from "react";
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
export function Timeline({ points, valueKey = "total", showDecay = true, max: fixedMax }) {
  const ref = useRef(null);
  const [W, setW] = useState(640);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fit = (width) => setW(Math.max(260, Math.floor(width)));
    fit(el.clientWidth);
    const observer = new ResizeObserver(([entry]) => fit(entry.contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  if (points.length === 0) {
    return <div ref={ref}><p className="py-10 text-center text-[13px] text-slate-400">No dated links yet.</p></div>;
  }
  const H = 170, P = { l: 36, r: 16, t: 14, b: 26 };
  const plotW = W - P.l - P.r;
  const max = fixedMax ?? Math.max(1, ...points.map((p) => p[valueKey]));
  const last = points.length - 1;
  const labelEvery = Math.max(1, Math.ceil(points.length / Math.max(2, Math.floor(plotW / 60))));
  const x = (i) => P.l + (points.length === 1 ? plotW / 2 : (i / last) * plotW);
  const y = (v) => P.t + (1 - v / max) * (H - P.t - P.b);
  const line = points.map((p, i) => `${i ? "L" : "M"} ${x(i)} ${y(p[valueKey])}`).join(" ");
  const area = `${line} L ${x(last)} ${H - P.b} L ${x(0)} ${H - P.b} Z`;
  const anchor = (i) => (i === 0 ? "start" : i === last ? "end" : "middle");
  return (
    <div ref={ref} className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="block max-w-full" role="img" aria-label="Links over time">
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={P.l} x2={W - P.r} y1={y(max * f)} y2={y(max * f)} stroke="#e2e8f0" />
            <text x={P.l - 8} y={y(max * f) + 4} textAnchor="end" fontSize="11" fill="#94a3b8">{Math.round(max * f)}</text>
          </g>
        ))}
        <path d={area} fill="#6366f1" opacity="0.12" />
        <path d={line} fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinejoin="round" />
        {points.map((p, i) => (
          <g key={p.day}>
            <circle cx={x(i)} cy={y(p[valueKey])} r="3.5" fill="#6366f1" />
            {showDecay && p.decayed > 0 && (
              <g>
                <circle cx={x(i)} cy={y(p[valueKey]) - 14} r="8" fill="#ef4444" />
                <text x={x(i)} y={y(p[valueKey]) - 10} textAnchor="middle" fontSize="10" fontWeight="700" fill="#fff">{p.decayed}</text>
              </g>
            )}
            {(i % labelEvery === 0 || i === last) && (
              <text x={x(i)} y={H - 6} textAnchor={anchor(i)} fontSize="11" fill="#64748b">{p.day.slice(5)}</text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
