import { AlertTriangle, ChevronDown, Inbox } from "lucide-react";
import { cx } from "./utils";

/* ------------------------------------------------------------------ small helpers */

/* ------------------------------------------------------------------ chips */
const chipTones = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-600/15",
  red: "bg-red-50 text-red-700 ring-red-600/15",
  amber: "bg-amber-50 text-amber-700 ring-amber-600/20",
  blue: "bg-sky-50 text-sky-700 ring-sky-600/15",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-600/15",
  violet: "bg-violet-50 text-violet-700 ring-violet-600/15",
  slate: "bg-slate-100 text-slate-600 ring-slate-500/10",
};
const dotTones = { green: "bg-emerald-500", red: "bg-red-500", amber: "bg-amber-500", blue: "bg-sky-500", indigo: "bg-indigo-500", violet: "bg-violet-500", slate: "bg-slate-400" };

export function Chip({ tone = "slate", dot = false, children, className = "" }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium leading-5 ring-1 ring-inset", chipTones[tone], className)}>
      {dot && <span className={cx("h-1.5 w-1.5 rounded-full", dotTones[tone])} />}
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ cards */
export function Card({ title, description, action, children, className = "", bodyClassName = "p-5", flush = false }) {
  return (
    <section data-trace-card className={cx("rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]", className)}>
      {(title || action) && (
        <header className="flex flex-wrap items-start justify-between gap-3 px-5 pt-4">
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold tracking-tight text-slate-900">{title}</h2>
            {description && <p className="mt-0.5 max-w-3xl text-[13px] leading-snug text-slate-500">{description}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={flush ? "pt-3" : cx(bodyClassName, title || action ? "pt-4" : "")}>{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------ numbers */
const statTones = {
  indigo: "bg-indigo-50 text-indigo-600",
  green: "bg-emerald-50 text-emerald-600",
  red: "bg-red-50 text-red-600",
  amber: "bg-amber-50 text-amber-600",
  slate: "bg-slate-100 text-slate-500",
};

export function Stat({ label, value, hint, tone = "indigo", icon: Icon, loading, compact }) {
  if (compact) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-slate-200/80 bg-white px-3 py-2.5 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
        {Icon && <div className={cx("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", statTones[tone])}><Icon size={17} strokeWidth={1.8} /></div>}
        <div className="min-w-0">
          <p className="truncate text-[11px] font-medium text-slate-500">{label}</p>
          {loading ? <Skeleton className="mt-1 h-5 w-10" /> : <p className="text-xl font-semibold leading-6 tabular-nums text-slate-900">{value}</p>}
        </div>
      </div>
    );
  }
  return (
    <div data-trace-stat className="flex items-center gap-4 rounded-2xl border border-slate-200/80 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
      {Icon && (
        <div className={cx("flex h-12 w-12 shrink-0 items-center justify-center rounded-xl", statTones[tone])}>
          <Icon size={22} strokeWidth={1.8} />
        </div>
      )}
      <div className="min-w-0">
        <p className="text-[12px] font-medium text-slate-500">{label}</p>
        {loading ? <Skeleton className="mt-1.5 h-7 w-16" /> : <p className="text-[28px] font-semibold leading-8 tracking-tight text-slate-900 tabular-nums">{value}</p>}
        {hint && <p className="mt-0.5 text-[12px] text-slate-400">{hint}</p>}
      </div>
    </div>
  );
}

/** Compact number with a small icon, used inside the summary band. */
export function Metric({ label, value, icon: Icon, tone = "indigo", loading }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 whitespace-nowrap text-[12px] font-medium text-slate-500">
        {Icon && <span className={cx("flex h-6 w-6 items-center justify-center rounded-md", statTones[tone])}><Icon size={14} strokeWidth={2} /></span>}
        {label}
      </div>
      {loading ? <Skeleton className="h-8 w-14" /> : <p className="text-[30px] font-semibold leading-8 tracking-tight tabular-nums text-slate-900">{value}</p>}
    </div>
  );
}

/** Circular score, 0 to 100. */
export function Ring({ value, size = 132, stroke = 12, label = "score", loading }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, value ?? 0));
  const color = v >= 80 ? "#10b981" : v >= 60 ? "#6366f1" : v >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eef2f7" strokeWidth={stroke} />
        {!loading && <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} style={{ transition: "stroke-dashoffset 0.8s ease" }} />}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {loading ? <Skeleton className="h-8 w-12" /> : <span className="text-[30px] font-semibold leading-none tracking-tight text-slate-900 tabular-nums">{Math.round(v)}</span>}
        <span className="mt-0.5 text-[10px] font-medium text-slate-400">{label}</span>
      </div>
    </div>
  );
}

export function ConfBar({ value, tone, className = "" }) {
  const v = value ?? 0;
  const color = tone === "red" ? "bg-red-500" : v >= 0.85 ? "bg-emerald-500" : v >= 0.65 ? "bg-indigo-500" : "bg-amber-500";
  return (
    <div className={cx("flex items-center gap-2", className)}>
      <span className="w-9 text-right text-[12px] font-medium tabular-nums text-slate-700">{v.toFixed(2)}</span>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
        <div className={cx("h-full rounded-full", color)} style={{ width: `${Math.round(v * 100)}%` }} />
      </div>
    </div>
  );
}

/** Horizontal bar with an optional target tick (0 to max). */
export function MeterBar({ value, max = 1, target, tone = "indigo" }) {
  const w = Math.max(0, Math.min(100, ((value ?? 0) / max) * 100));
  const color = { indigo: "bg-indigo-500", green: "bg-emerald-500", red: "bg-red-500", amber: "bg-amber-500" }[tone];
  return (
    <div className="relative h-2 w-full rounded-full bg-slate-100">
      <div className={cx("h-full rounded-full", color)} style={{ width: `${w}%` }} />
      {target != null && <div className="absolute -top-1 h-4 w-0.5 rounded bg-slate-700" style={{ left: `${Math.min(100, (target / max) * 100)}%` }} title={`target ${target}`} />}
    </div>
  );
}

/* ------------------------------------------------------------------ files */
const extTones = { java: "bg-orange-50 text-orange-700", html: "bg-sky-50 text-sky-700", jsp: "bg-sky-50 text-sky-700", c: "bg-slate-100 text-slate-700", h: "bg-slate-100 text-slate-700", xml: "bg-violet-50 text-violet-700", js: "bg-amber-50 text-amber-700" };
export function FileBadge({ name }) {
  const ext = String(name).includes(".") ? String(name).split(".").pop().toLowerCase() : "";
  return <span className={cx("inline-flex h-5 min-w-[34px] items-center justify-center rounded px-1.5 text-[10px] font-semibold uppercase", extTones[ext] || "bg-slate-100 text-slate-600")}>{ext || "file"}</span>;
}

/* ------------------------------------------------------------------ states */
export function Skeleton({ className = "" }) {
  return <div className={cx("animate-pulse rounded-md bg-slate-100", className)} />;
}

export function SkeletonRows({ rows = 5 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 flex-1" />
          <Skeleton className="h-9 w-32" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, children }) {
  return (
    <div data-trace-empty className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/50 px-6 py-10 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-white text-slate-400 shadow-sm ring-1 ring-slate-200">
        <Icon size={20} strokeWidth={1.7} />
      </div>
      <p className="mt-3 text-[14px] font-medium text-slate-700">{title}</p>
      {children && <p className="mt-1 max-w-md text-[13px] leading-relaxed text-slate-500">{children}</p>}
    </div>
  );
}

const calloutTones = {
  info: "border-sky-200 bg-sky-50 text-sky-900",
  ok: "border-emerald-200 bg-emerald-50 text-emerald-900",
  warn: "border-amber-200 bg-amber-50 text-amber-900",
  bad: "border-red-200 bg-red-50 text-red-900",
};
export function Callout({ tone = "info", children, className = "" }) {
  return <div className={cx("rounded-xl border px-4 py-3 text-[13px] leading-relaxed", calloutTones[tone], className)}>{children}</div>;
}

/* ------------------------------------------------------------------ tabs */
export function Tabs({ items, value, onChange }) {
  return (
    <div data-trace-tabs role="tablist" className="flex gap-1 overflow-x-auto border-b border-slate-200">
      {items.map((item) => {
        const active = item.id === value;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(item.id)}
            className={cx(
              "-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2.5 text-[13px] font-medium transition",
              active ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-800",
            )}
          >
            {item.label}
            {item.count != null && <span className={cx("rounded-full px-2 py-0.5 text-[11px] tabular-nums", active ? "bg-indigo-50 text-indigo-700" : "bg-slate-100 text-slate-500")}>{item.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

/** Small segmented switch (for two or three alternatives inside a card). */
export function Segmented({ items, value, onChange }) {
  return (
    <div className="inline-flex rounded-lg bg-slate-100 p-0.5">
      {items.map((item) => (
        <button key={item.id} type="button" onClick={() => onChange(item.id)} className={cx("rounded-md px-3 py-1 text-[12px] font-medium transition", value === item.id ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800")}>
          {item.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ buttons */
export function Button({ variant = "primary", className = "", ...props }) {
  const styles = {
    primary: "bg-indigo-600 text-white shadow-sm hover:bg-indigo-700 disabled:bg-indigo-300",
    secondary: "border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50 disabled:text-slate-300",
    danger: "border border-red-200 bg-white text-red-600 hover:bg-red-50 disabled:text-red-300",
    ghost: "text-slate-600 hover:bg-slate-100",
  };
  return <button type="button" className={cx("inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-[13px] font-medium transition disabled:cursor-not-allowed", styles[variant], className)} {...props} />;
}

export function Disclosure({ open }) {
  return <ChevronDown size={16} className={cx("shrink-0 text-slate-400 transition-transform duration-200", open && "rotate-180")} />;
}

/* ------------------------------------------------------------------ page header */
export function PageHeader({ page, title, description, apiError, children }) {
  return (
    <div data-trace-header className="mb-6">
      <div className="c4-page-kicker">
        <span className="c4-page-kicker-mark">C4</span>
        <span>Traceability intelligence</span>
        <span className="c4-page-kicker-divider">/</span>
        <span className="c4-page-kicker-current">{page}</span>
      </div>
      <div className="c4-page-heading">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h1>
          {description && <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-slate-500">{description}</p>}
        </div>
        {children}
      </div>
      {apiError && (
        <div className="c4-api-alert mt-4 flex items-start gap-3 rounded-xl border p-3.5 text-[13px]">
          <AlertTriangle size={17} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">The C4 API is not reachable ({apiError}).</p>
            <p className="mt-0.5 text-amber-800">
              Start it from the project folder with <code className="rounded bg-amber-100 px-1">python -m apps.api.server</code> and make sure Neo4j is running. If the API uses another port,
              start this page with <code className="rounded bg-amber-100 px-1">C4_API=http://127.0.0.1:PORT npm run dev</code>.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
