import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ChevronLeft, ChevronRight, CircleHelp, Eye, X } from "lucide-react";
import { postJson, useApi, useProject } from "../api/c4";
import { Button, Callout, Card, Chip, EmptyState, FileBadge, MeterBar, PageHeader } from "../component/traceability/ui";
import { shortName } from "../component/traceability/utils";

const keyOf = (i) => `${i.requirement}||${i.code}`;
const pct = (v) => (v == null ? "-" : `${Math.round(v * 100)}%`);

function Results({ s }) {
  const done = s.labelled;
  return (
    <Card title="Result so far" description="Precision = how many of the links the AI confirmed are really correct. 'Unsure' is left out.">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-[12px] text-slate-500">Precision</p>
          <p className="text-[34px] font-semibold leading-9 tabular-nums text-slate-900">{pct(s.precision)}</p>
          <p className="text-[12px] text-slate-500">{s.ci95 ? `95% range ${pct(s.ci95[0])} to ${pct(s.ci95[1])}` : "label some links first"}</p>
        </div>
        <div className="space-y-1 text-[13px] text-slate-600">
          <p><Chip tone="green" dot>{s.correct} correct</Chip></p>
          <p><Chip tone="red" dot>{s.wrong} wrong</Chip></p>
          <p><Chip tone="amber" dot>{s.unsure} unsure</Chip></p>
        </div>
      </div>
      <div className="mt-4">
        <div className="mb-1 flex justify-between text-[12px] text-slate-500"><span>Progress</span><span>{done} of {s.sample}</span></div>
        <MeterBar value={done} max={s.sample} />
      </div>
      <div className="mt-5">
        <p className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-slate-400">Precision by AI confidence</p>
        <ul className="space-y-1.5 text-[13px]">
          {s.byConfidence.map((b) => (
            <li key={b.label} className="flex items-center justify-between">
              <span className="text-slate-600">{b.label}</span>
              <span className="tabular-nums text-slate-800">{pct(b.precision)} <span className="text-slate-400">({b.correct}/{b.correct + b.wrong})</span></span>
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-4 text-[12px] leading-relaxed text-slate-400">With this few links the range is wide; label at least 40 before quoting a number.</p>
    </Card>
  );
}

const TraceabilityLabeling = () => {
  const { project, error: projectsError } = useProject();
  const enc = project ? encodeURIComponent(project) : null;
  const api = useApi(enc ? `/api/labeling?project=${enc}&n=40` : null);
  const items = useMemo(() => api.data?.items ?? [], [api.data]);

  const [index, setIndex] = useState(0);
  const [overrides, setOverrides] = useState({});
  const [showReason, setShowReason] = useState(false);
  const [error, setError] = useState("");

  const current = items[Math.min(index, Math.max(0, items.length - 1))];
  const code = useApi(current ? `/api/code-text?code=${encodeURIComponent(current.code)}` : null);
  const labelOf = (i) => (keyOf(i) in overrides ? overrides[keyOf(i)] : i.label);

  const go = useCallback((delta) => {
    setShowReason(false);
    setIndex((i) => Math.max(0, Math.min(items.length - 1, i + delta)));
  }, [items.length]);

  const { reload } = api;
  const mark = useCallback(
    async (label) => {
      if (!current) return;
      setError("");
      setOverrides((o) => ({ ...o, [keyOf(current)]: label }));
      try {
        await postJson("/api/label", { project, requirement: current.requirement, code: current.code, label });
        reload();
        go(1);
      } catch (e) {
        setError(e.message);
      }
    },
    [current, project, reload, go],
  );

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.closest("input, textarea, select")) return;
      if (e.key === "1") mark("correct");
      else if (e.key === "2") mark("wrong");
      else if (e.key === "3") mark("unsure");
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mark, go]);

  const cur = current ? labelOf(current) : null;
  const tone = { correct: "green", wrong: "red", unsure: "amber" };

  return (
    <div className="mx-auto w-full max-w-[1400px] pb-8">
      <PageHeader
        page="Evaluate"
        title="Check the links yourself"
        description="Read the requirement and the code, then say whether the code really implements it. Your answers give the true precision of the AI's links."
        apiError={projectsError || api.error}
      />

      {!api.data ? (
        <Card><EmptyState title="Loading a sample..." /></Card>
      ) : items.length === 0 ? (
        <Card><EmptyState title="No verified links in this project">Create trace links first.</EmptyState></Card>
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="min-w-0 space-y-4">
            <Callout tone="info">Do not trust the AI: decide from the text. Keys: <b>1</b> correct, <b>2</b> wrong, <b>3</b> unsure, arrows to move.</Callout>

            <Card
              title={`Link ${index + 1} of ${items.length}`}
              action={cur ? <Chip tone={tone[cur]} dot>{cur}</Chip> : <Chip>not labelled</Chip>}
            >
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Requirement {current.requirement}</p>
              <p className="mt-1 text-[15px] leading-relaxed text-slate-900">{current.requirementText}</p>

              <div className="mt-5 flex items-center gap-2">
                <FileBadge name={current.code} />
                <p className="text-[14px] font-semibold text-slate-900" title={current.code}>{shortName(current.code)}</p>
              </div>
              <pre className="mt-2 max-h-[230px] overflow-auto whitespace-pre-wrap break-words rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-[12px] leading-relaxed text-slate-700">
                {code.data ? code.data.text || "(no stored text)" : "Loading code..."}
              </pre>

              <div className="mt-4">
                <button type="button" onClick={() => setShowReason((v) => !v)} className="inline-flex items-center gap-1.5 text-[12px] font-medium text-slate-500 hover:text-indigo-600">
                  <Eye size={14} /> {showReason ? "Hide" : "Show"} what the AI said (decide first)
                </button>
                {showReason && (
                  <p className="mt-2 rounded-lg bg-indigo-50/60 p-3 text-[13px] leading-relaxed text-slate-700">
                    <b>confidence {Number(current.confidence).toFixed(2)}:</b> {current.reason || "-"}
                  </p>
                )}
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
                <Button onClick={() => mark("correct")} className="bg-emerald-600! hover:bg-emerald-700!"><Check size={16} /> Correct (1)</Button>
                <Button onClick={() => mark("wrong")} className="bg-red-600! hover:bg-red-700!"><X size={16} /> Wrong (2)</Button>
                <Button variant="secondary" onClick={() => mark("unsure")}><CircleHelp size={16} /> Unsure (3)</Button>
                <div className="ml-auto flex gap-2">
                  <Button variant="secondary" onClick={() => go(-1)} disabled={index === 0} aria-label="Previous"><ChevronLeft size={16} /></Button>
                  <Button variant="secondary" onClick={() => go(1)} disabled={index >= items.length - 1} aria-label="Next"><ChevronRight size={16} /></Button>
                </div>
              </div>
              {error && <p className="mt-3 text-[13px] text-red-600">Could not save: {error}</p>}
            </Card>

            <div className="flex flex-wrap gap-1.5" aria-label="Progress by link">
              {items.map((i, n) => {
                const l = labelOf(i);
                const color = l === "correct" ? "bg-emerald-500" : l === "wrong" ? "bg-red-500" : l === "unsure" ? "bg-amber-400" : "bg-slate-200";
                return <button key={keyOf(i)} type="button" onClick={() => { setShowReason(false); setIndex(n); }} aria-label={`Link ${n + 1}`} className={`h-3 w-5 rounded-sm ${color} ${n === index ? "ring-2 ring-indigo-500 ring-offset-1" : ""}`} />;
              })}
            </div>
          </div>

          <Results s={api.data.stats} />
        </div>
      )}
    </div>
  );
};

export default TraceabilityLabeling;
