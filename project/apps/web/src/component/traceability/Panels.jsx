import { ArrowDown, ArrowRight, CheckCircle2, ShieldCheck } from "lucide-react";
import { Card, Chip, EmptyState, MeterBar, Ring } from "./ui";
import { shortName } from "./utils";

const steps = [
  { name: "Requirement", note: "read from C1", tone: "green" },
  { name: "Find candidates", note: "TF-IDF + MiniLM shortlist", tone: "indigo" },
  { name: "AI check", note: "Llama 3.1 says yes/no and why", tone: "violet" },
  { name: "Verified link", note: "saved in the graph", tone: "amber" },
  { name: "Watch for decay", note: "re-checked after each change", tone: "red" },
  { name: "Tell C3", note: "Redis event trace_decayed", tone: "slate" },
];
const ring = { green: "bg-emerald-500", indigo: "bg-indigo-500", violet: "bg-violet-500", amber: "bg-amber-500", red: "bg-red-500", slate: "bg-slate-400" };

export function PipelineStrip() {
  return (
    <Card title="How a trace link is made and kept correct" description="Component 4 pipeline. An optional cross-encoder re-ranks candidates before the AI check (off by default).">
      <ol className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {steps.map((s, i) => (
          <li key={s.name} className="relative rounded-xl border border-slate-200 bg-slate-50/60 p-3.5">
            <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold text-white ${ring[s.tone]}`}>{i + 1}</span>
            <p className="mt-2 text-[13px] font-semibold text-slate-900">{s.name}</p>
            <p className="mt-0.5 text-[12px] leading-snug text-slate-500">{s.note}</p>
            {i < steps.length - 1 && <ArrowRight size={14} className="absolute -right-2.5 top-1/2 z-10 hidden -translate-y-1/2 rounded-full bg-white text-slate-300 xl:block" />}
          </li>
        ))}
      </ol>
    </Card>
  );
}

const when = (value) => (value ? String(value).replace("T", " ").slice(0, 16) : "-");

export function DecayPanel({ flags }) {
  return (
    <Card title="Broken links (decay)" description="Links that stopped holding after a requirement or code change. They are kept with a flag, never deleted.">
      {flags.length === 0 ? (
        <EmptyState icon={ShieldCheck} title="No broken links">Every link in this project still holds. Edit a linked file on the Code changes page to see one appear.</EmptyState>
      ) : (
        <ul className="space-y-3">
          {flags.slice(0, 6).map((f, i) => (
            <li key={`${f.requirement}-${f.code}-${i}`} className="rounded-xl border border-red-100 bg-red-50/40 p-3.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[13px] font-semibold text-slate-900">
                  {f.requirement} <ArrowRight size={12} className="mx-1 inline text-slate-400" /> {shortName(f.code)}
                </p>
                <Chip tone="red" dot>{f.previousConfidence != null ? `was ${Number(f.previousConfidence).toFixed(2)}` : "decayed"}</Chip>
              </div>
              <p className="mt-1.5 text-[13px] leading-relaxed text-slate-600">{f.reason || "No reason stored."}</p>
              <p className="mt-1.5 text-[11px] text-slate-400">{when(f.flaggedAt)}</p>
            </li>
          ))}
          {flags.length > 6 && <li className="text-center text-[12px] text-slate-400">and {flags.length - 6} more</li>}
        </ul>
      )}
    </Card>
  );
}

export function CompletenessPanel({ completeness }) {
  const rows = completeness?.requirements ?? [];
  const lowest = rows.slice(0, 8);
  return (
    <Card title="Completeness by requirement" description="0 to 100 per requirement: mean confidence of its verified links. No verified link means orphan (0).">
      {rows.length === 0 ? (
        <EmptyState title="No requirements yet" />
      ) : (
        <>
          <div className="mb-5 flex items-center gap-5">
            <Ring value={completeness.mean} size={104} stroke={10} label="mean" />
            <div className="space-y-1.5 text-[13px] text-slate-600">
              <p><span className="text-lg font-semibold text-slate-900">{rows.length}</span> requirements scored</p>
              <p><span className={`text-lg font-semibold ${completeness.orphans ? "text-red-600" : "text-emerald-600"}`}>{completeness.orphans}</span> orphans (no verified link)</p>
            </div>
          </div>
          <p className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-400"><ArrowDown size={12} /> Lowest first</p>
          <ul className="space-y-2.5">
            {lowest.map((r) => (
              <li key={r.requirement_id} className="flex items-center gap-3 text-[13px]">
                <span className="w-28 shrink-0 truncate font-medium text-slate-700">{r.requirement_id}</span>
                <div className="flex-1"><MeterBar value={r.score} max={100} tone={r.is_orphan ? "red" : r.score >= 70 ? "green" : "amber"} /></div>
                <span className="w-9 text-right tabular-nums text-slate-600">{r.score.toFixed(0)}</span>
                {r.is_orphan ? <Chip tone="red">orphan</Chip> : <CheckCircle2 size={15} className="text-emerald-500" />}
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}
