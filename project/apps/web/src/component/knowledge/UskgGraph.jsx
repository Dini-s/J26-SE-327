import { linkColor, linkLabel } from "../traceability/linkStatus";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { KS, PALETTE, layoutGraph, radiusOf } from "./layout";
import { shortName } from "../traceability/utils";

const trunc = (text, n) => {
  const t = String(text || "").replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n - 1)}...` : t;
};

const edgeGeometry = (a, b, bendOn) => {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const d = Math.hypot(dx, dy) || 1;
  const ux = dx / d;
  const uy = dy / d;
  const ra = radiusOf(a) + 2;
  const rb = radiusOf(b) + 4;
  const x1 = a.x + ux * ra;
  const y1 = a.y + uy * ra;
  const x2 = b.x - ux * rb;
  const y2 = b.y - uy * rb;
  const bend = Math.min(30, d * 0.1) * (bendOn ? 1 : 0);
  const mx = (x1 + x2) / 2 - uy * bend;
  const my = (y1 + y2) / 2 + ux * bend;
  return { d: `M${x1},${y1} Q${mx},${my} ${x2},${y2}`, mx, my };
};

/**
 * Interactive knowledge graph: drag nodes, drag the background to pan, scroll to zoom, click to inspect.
 * `nodes` and `edges` are the API's graph payload (already filtered); positions are computed here.
 */
export default function UskgGraph({ nodes, edges, selected, onSelect, search, arrangeToken, focusRef, className = "" }) {
  const box = useRef(null);
  const [size, setSize] = useState({ w: 900, h: 620 });
  const [view, setView] = useState({ k: 1, tx: 0, ty: 0 });
  const [, bump] = useState(0);
  const drag = useRef(null);

  // lay out when the data (or "Arrange") changes
  const laid = useMemo(() => {
    const copies = nodes.map((n) => ({ ...n }));
    layoutGraph(copies, edges, (size.w || 900) / (size.h || 620));
    return copies;
    // size is deliberately not a dependency: a resize must not rearrange the graph
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, arrangeToken]);
  const byId = useMemo(() => new Map(laid.map((n) => [n.id, n])), [laid]);

  useEffect(() => {
    if (!box.current) return undefined;
    const observer = new ResizeObserver(([entry]) => setSize({ w: entry.contentRect.width, h: entry.contentRect.height }));
    observer.observe(box.current);
    return () => observer.disconnect();
  }, []);

  const fit = useCallback(() => {
    if (!laid.length || !size.w) return;
    const xs = laid.map((n) => n.x);
    const ys = laid.map((n) => n.y);
    const minX = Math.min(...xs) - 110;
    const maxX = Math.max(...xs) + 110;
    const minY = Math.min(...ys) - 85;
    const maxY = Math.max(...ys) + 110;
    const k = Math.max(0.2, Math.min(1, Math.min((size.w - 48) / (maxX - minX), (size.h - 80) / (maxY - minY))));
    setView({ k, tx: size.w / 2 - ((minX + maxX) / 2) * k, ty: size.h / 2 - ((minY + maxY) / 2) * k });
  }, [laid, size]);

  // fit once per layout
  const fitted = useRef(null);
  useEffect(() => {
    if (fitted.current !== laid && size.w > 0) {
      fitted.current = laid;
      fit();
    }
  }, [laid, size, fit]);

  const zoom = useCallback(
    (factor, cx = size.w / 2, cy = size.h / 2) =>
      setView((v) => {
        const k = Math.max(0.3, Math.min(2.5, v.k * factor));
        return { k, tx: cx - ((cx - v.tx) * k) / v.k, ty: cy - ((cy - v.ty) * k) / v.k };
      }),
    [size],
  );

  useEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    const onWheel = (event) => {
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      zoom(event.deltaY < 0 ? 1.1 : 0.9, event.clientX - rect.left, event.clientY - rect.top);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoom]);

  // search: Enter focuses the first match (handled by the page through `search`), here we only dim non-matches
  const q = (search || "").trim().toLowerCase();
  const matches = useCallback((n) => !q || `${n.label} ${n.text || ""} ${n.id}`.toLowerCase().includes(q), [q]);

  const neighbours = useMemo(() => {
    if (selected?.type !== "node") return null;
    const set = new Set([selected.id]);
    edges.forEach((e) => {
      if (e.from === selected.id) set.add(e.to);
      if (e.to === selected.id) set.add(e.from);
    });
    return set;
  }, [selected, edges]);

  const onNodeDown = (event, node) => {
    event.stopPropagation();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current = { type: "node", node, sx: event.clientX, sy: event.clientY, x0: node.x, y0: node.y, moved: false };
  };
  const onBackgroundDown = (event) => {
    event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current = { type: "pan", sx: event.clientX, sy: event.clientY, tx: view.tx, ty: view.ty, moved: false };
  };
  const onMove = (event) => {
    const d = drag.current;
    if (!d) return;
    const dx = event.clientX - d.sx;
    const dy = event.clientY - d.sy;
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
    if (d.type === "node" && d.moved) {
      d.node.x = d.x0 + dx / view.k;
      d.node.y = d.y0 + dy / view.k;
      bump((n) => n + 1);
    } else if (d.type === "pan") {
      setView((v) => ({ ...v, tx: d.tx + dx, ty: d.ty + dy }));
    }
  };
  const onUp = () => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    if (d.type === "node" && !d.moved) onSelect({ type: "node", id: d.node.id });
    if (d.type === "pan" && !d.moved) onSelect(null);
  };

  // the page can centre a node (search + Enter) through focusRef.current(id)
  useEffect(() => {
    if (!focusRef) return undefined;
    const focus = (id) => {
      const n = byId.get(id);
      if (n) setView((v) => ({ ...v, tx: size.w / 2 - n.x * v.k, ty: size.h / 2 - n.y * v.k }));
    };
    focusRef.current = focus;
    return () => {
      focusRef.current = null;
    };
  }, [focusRef, byId, size]);

  const k = Math.max(0.6, view.k);
  const c = PALETTE;

  return (
    <div
      ref={box}
      className={`relative cursor-grab touch-none overflow-hidden bg-white ${className}`}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerCancel={onUp}
    >
      <svg className="block h-full w-full" onPointerDown={onBackgroundDown} role="img" aria-label="Knowledge graph">
        <defs>
          {[["ok", c.ok], ["bad", c.bad], ["warn", c.faint]].map(([name, color]) => (
            <marker key={name} id={`arr-${name}`} viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill={color} />
            </marker>
          ))}
        </defs>
        <g transform={`translate(${view.tx},${view.ty}) scale(${view.k})`}>
          {edges.map((e, i) => {
            const a = byId.get(e.from);
            const b = byId.get(e.to);
            if (!a || !b) return null;
            const decayed = e.category === "decayed";
            const flag = e.category === "has_decay";
            const rel = e.category === "rel";
            const color = flag ? c.warn : rel ? c.faint : linkColor(e.category);
            const { d, mx, my } = edgeGeometry(a, b, !flag);
            const touching = neighbours && neighbours.has(e.from) && neighbours.has(e.to) && (e.from === selected.id || e.to === selected.id);
            const dim = (neighbours && !touching) || (q && !(matches(a) || matches(b)));
            const isSelected = selected?.type === "edge" && selected.index === i;
            return (
              <g key={`${e.from}-${e.to}-${i}`} opacity={dim ? 0.12 : 1}>
                <path d={d} fill="none" stroke={color} strokeWidth={isSelected || touching ? 2.6 : flag ? 1 : 1.5} vectorEffect="non-scaling-stroke" strokeDasharray={decayed || e.category === "rejected" ? "6 4" : flag || e.category === "pending_review" ? "2 4" : undefined} markerEnd={`url(#arr-${decayed ? "bad" : flag || rel ? "warn" : "ok"})`} />
                {!flag && (
                  <path
                    d={d}
                    fill="none"
                    stroke="transparent"
                    strokeWidth="12"
                    vectorEffect="non-scaling-stroke"
                    className="cursor-pointer"
                    onPointerDown={(event) => event.stopPropagation()}
                    onClick={() => onSelect({ type: "edge", index: i })}
                  />
                )}
                {!flag && selected && view.k >= 0.7 && (
                  <text x={mx} y={my - 4} textAnchor="middle" fontSize={10 / k} fill={decayed ? c.bad : c.muted} fontFamily="ui-monospace, monospace" pointerEvents="none">
                    {rel ? e.rel : `Trace: ${linkLabel(e.category)}`}
                  </text>
                )}
              </g>
            );
          })}

          {laid.map((n) => {
            const ks = KS[n.kind];
            const r = radiusOf(n);
            const style = ks
              ? { fill: ks.fill, stroke: ks.stroke, dash: null }
              : n.kind === "requirement"
                ? { fill: n.orphan ? c.surface : c.blue, stroke: n.orphan ? c.faint : c.blueDark, dash: n.orphan ? "3 3" : null }
                : n.kind === "decayflag"
                  ? { fill: c.warn, stroke: c.warn, dash: null }
                  : { fill: c.green, stroke: c.greenDark, dash: null };
            const dim = (neighbours && !neighbours.has(n.id)) || (q && !matches(n));
            const isSelected = selected?.type === "node" && selected.id === n.id;
            const caption = n.kind === "requirement" || (ks && !ks.cap) ? "" : trunc(n.kind === "decayflag" ? "DecayFlag" : ks ? n.label : shortName(n.label), view.k < 0.6 ? 16 : 24);
            const inner = ks ? ks.inner : n.kind === "decayflag" ? "!" : n.kind === "requirement" ? trunc(n.label, 10) : "CODE";
            return (
              <g key={n.id} transform={`translate(${n.x},${n.y})`} opacity={dim ? 0.2 : 1} className="cursor-pointer" onPointerDown={(event) => onNodeDown(event, n)} role="button" aria-label={n.label || n.kind}>
                <title>{n.kind === "requirement" ? `${n.label}\n${n.text || ""}` : n.kind === "decayflag" ? `DecayFlag\n${n.text || ""}` : n.label}</title>
                <circle r={r} fill={style.fill} stroke={isSelected ? "#4f46e5" : style.stroke} strokeWidth={isSelected ? 3 : 1} strokeDasharray={style.dash || undefined} vectorEffect="non-scaling-stroke" />
                <text textAnchor="middle" y={3.5 / k} fontSize={(n.kind === "requirement" ? 11 : 10) / k} fontWeight="600" fill={n.orphan ? c.text : "#20251c"} pointerEvents="none">
                  {inner}
                </text>
                {caption && (
                  <text textAnchor="middle" y={r + 18 / k} fontSize={12 / k} fill={n.orphan ? c.muted : c.text} pointerEvents="none">
                    {caption}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {laid.length === 0 && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center text-xs text-slate-400">
          <strong className="text-slate-600">No nodes to display</strong>
          <p>Choose a project with requirements, or create a trace link.</p>
        </div>
      )}

      <p className="pointer-events-none absolute left-4 top-3 text-[11px] text-slate-400">
        {laid.length} nodes, {edges.length} relationships. Drag nodes to arrange, drag the background to pan, scroll to zoom.
      </p>

      <div className="absolute bottom-3 right-3 flex items-center gap-1 rounded-lg border border-slate-200 bg-white/95 p-1 text-xs shadow-sm" onPointerDown={(event) => event.stopPropagation()}>
        <span className="px-2 tabular-nums text-slate-500">{Math.round(view.k * 100)}%</span>
        <button type="button" onClick={() => zoom(1.25)} className="rounded px-2 py-1 hover:bg-slate-100" aria-label="Zoom in">+</button>
        <button type="button" onClick={() => zoom(0.8)} className="rounded px-2 py-1 hover:bg-slate-100" aria-label="Zoom out">-</button>
        <button type="button" onClick={fit} className="rounded px-2 py-1 hover:bg-slate-100">Fit</button>
      </div>
    </div>
  );
}
