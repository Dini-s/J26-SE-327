import { Fragment, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Card, Chip, ConfBar, Disclosure, EmptyState, FileBadge, Segmented } from "./ui";
import { shortName } from "./utils";

const PAGE = 25;
const TRUSTED = 0.85; // calibration: ~82% of 0.9 verdicts correct vs ~36% of 0.8, so below this a person should look
const needsReview = (l) => l.status !== "decayed" && (l.confidence ?? 0) < TRUSTED;
const timeOf = (value) => (value ? String(value).replace("T", " ").slice(0, 16) : "-");

export default function LinksTable({ links }) {
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);
  const [open, setOpen] = useState(null);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return links
      .filter((l) => status === "all" || (status === "trusted" ? l.status !== "decayed" && (l.confidence ?? 0) >= TRUSTED : status === "review" ? needsReview(l) : l.status === status))
      .filter((l) => !q || `${l.requirement} ${l.code} ${l.requirementText}`.toLowerCase().includes(q))
      .sort((a, b) => (a.status === b.status ? (b.confidence ?? 0) - (a.confidence ?? 0) : a.status === "decayed" ? -1 : 1));
  }, [links, status, query]);

  return (
    <Card
      title="Verified trace links"
      description="Each link was checked by the AI model. Trusted = confidence 0.85 or more (about 8 in 10 correct on labelled data). Below that the model is often wrong (about 1 in 3 correct), so those links are marked Needs review for a person to decide."
      flush
      action={
        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            value={status}
            onChange={(v) => { setStatus(v); setShown(PAGE); }}
            items={[{ id: "all", label: "All" }, { id: "trusted", label: "Trusted" }, { id: "review", label: `Needs review (${links.filter(needsReview).length})` }, { id: "verified", label: "Verified" }, { id: "decayed", label: "Broken" }]}
          />
          <label className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-slate-400 focus-within:border-indigo-300">
            <Search size={14} />
            <input value={query} onChange={(e) => { setQuery(e.target.value); setShown(PAGE); }} placeholder="Search requirement or file" className="w-48 bg-transparent text-[13px] text-slate-800 outline-none placeholder:text-slate-400" />
          </label>
        </div>
      }
    >
      {rows.length === 0 ? (
        <div className="px-5 pb-5"><EmptyState title="No links match">Create links on the Link requirements page, or clear the filter.</EmptyState></div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-[13px]">
            <thead>
              <tr className="border-y border-slate-100 bg-slate-50/70 text-[11px] uppercase tracking-wide text-slate-500">
                <th className="px-5 py-2.5 font-medium">Requirement</th>
                <th className="px-3 py-2.5 font-medium">Code</th>
                <th className="px-3 py-2.5 font-medium">Confidence</th>
                <th className="px-3 py-2.5 font-medium">Status</th>
                <th className="px-3 py-2.5 font-medium">Checked</th>
                <th className="w-10 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, shown).map((l) => {
                const key = `${l.requirement}||${l.code}`;
                const expanded = open === key;
                const decayed = l.status === "decayed";
                return (
                  <Fragment key={key}>
                    <tr onClick={() => setOpen(expanded ? null : key)} className="cursor-pointer border-b border-slate-100 align-middle transition hover:bg-indigo-50/40">
                      <td className="px-5 py-3" title={l.requirementText}>
                        <span className="font-semibold text-slate-900">{l.requirement}</span>
                        <span className="mt-0.5 block max-w-[300px] truncate text-[12px] text-slate-500">{l.requirementText}</span>
                      </td>
                      <td className="px-3 py-3" title={l.code}>
                        <div className="flex items-center gap-2">
                          <FileBadge name={l.code} />
                          <span className="font-medium text-slate-700">{shortName(l.code)}</span>
                        </div>
                      </td>
                      <td className="px-3 py-3"><ConfBar value={l.confidence} tone={decayed ? "red" : undefined} /></td>
                      <td className="px-3 py-3"><Chip tone={decayed ? "red" : needsReview(l) ? "amber" : "green"} dot>{decayed ? "broken" : needsReview(l) ? "needs review" : "verified"}</Chip></td>
                      <td className="whitespace-nowrap px-3 py-3 tabular-nums text-slate-500">{timeOf(l.lastCheckedAt)}</td>
                      <td className="px-3 py-3"><Disclosure open={expanded} /></td>
                    </tr>
                    {expanded && (
                      <tr className="border-b border-slate-100 bg-slate-50/80">
                        <td colSpan={6} className="px-5 py-4">
                          <div className="grid gap-4 text-[13px] leading-relaxed md:grid-cols-2">
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Requirement</p>
                              <p className="mt-1 text-slate-700">{l.requirementText || "-"}</p>
                            </div>
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Why the AI linked it</p>
                              <p className="mt-1 text-slate-700">{l.reason || "-"}</p>
                            </div>
                          </div>
                          <p className="mt-3 break-all text-[11px] text-slate-400">{l.code}</p>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
          <div className="flex items-center justify-between px-5 py-3 text-[12px] text-slate-500">
            <span>Showing {Math.min(shown, rows.length)} of {rows.length}</span>
            {shown < rows.length && <button type="button" onClick={() => setShown(shown + PAGE)} className="font-medium text-indigo-600 hover:text-indigo-700">Show more</button>}
          </div>
        </div>
      )}
    </Card>
  );
}
