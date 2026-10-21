import StatusBadge from "../common/StatusBadge";
import { Bar, Card, Empty } from "./common";

const num = (x, d = 3) => (typeof x === "number" ? x.toFixed(d) : x ?? "-");

function Target({ label, measured, target, met, note }) {
  return (
    <div className={`rounded-xl border p-3 ${met ? "border-emerald-200 bg-emerald-50/50" : "border-red-100 bg-red-50/50"}`}>
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-3xl font-semibold tracking-tight ${met ? "text-emerald-700" : "text-red-600"}`}>{measured}</p>
      <p className="text-[11px] text-slate-500">target {target}</p>
      {note && <p className="mt-1 text-[11px] text-slate-400">{note}</p>}
    </div>
  );
}

const pct = (x, d = 1) => (typeof x === "number" ? `${(x * 100).toFixed(d)}%` : "-");
const formatValue = (t) => (t.format === "seconds" ? `${Math.round(t.value)} s` : pct(t.value));
const formatTarget = (t) => `${t.higherIsBetter ? ">=" : "<="} ${t.format === "seconds" ? `${t.target} s` : `${Math.round(t.target * 100)}%`}`;

export function EvaluationPanel({ results, targets = [], pending = [] }) {
  if (!results) return <Card title="Measured results"><Empty>Loading results...</Empty></Card>;
  const decay = results.decay_injection;
  const recallRows = Object.entries(results.stage1_recall ?? {}).flatMap(([dataset, byK]) =>
    Object.entries(byK).map(([k, v]) => ({ dataset, k, ...v })),
  );

  return (
    <Card
      title="Measured results against the targets"
      subtitle="Every number comes from a saved result file in data/results. Samples are small; read the notes."
    >
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {targets.length === 0 && <Empty>Loading the measured targets...</Empty>}
        {targets.map((t) => (
          <Target key={t.key} label={t.label} measured={formatValue(t)} target={formatTarget(t)} met={t.met} note={t.note} />
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div>
          <h3 className="mb-3 text-[13px] font-semibold text-slate-900">Stage-1 recall (shortlist, no LLM)</h3>
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-400">
                <th className="py-2 text-left font-medium">Dataset</th>
                <th className="py-2 text-left font-medium">Top-k</th>
                <th className="py-2 text-right font-medium">TF-IDF</th>
                <th className="py-2 text-right font-medium">Embeddings</th>
                <th className="py-2 text-right font-medium">Hybrid</th>
              </tr>
            </thead>
            <tbody>
              {recallRows.map((r) => (
                <tr key={`${r.dataset}-${r.k}`} className="border-b border-slate-50">
                  <td className="py-2 text-slate-700">{r.dataset}</td>
                  <td className="py-2 text-slate-500">{r.k}</td>
                  <td className="py-2 text-right tabular-nums text-slate-600">{num(r.tfidf)}</td>
                  <td className="py-2 text-right tabular-nums text-slate-600">{num(r.embeddings)}</td>
                  <td className="py-2 text-right font-semibold tabular-nums text-indigo-700">{num(r.hybrid)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <h3 className="mb-3 text-[13px] font-semibold text-slate-900">Precision / recall / F1</h3>
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-400">
                <th className="py-2 text-left font-medium">Set and method</th>
                <th className="w-14 py-2 pl-3 text-right font-medium">P</th>
                <th className="w-14 py-2 pl-3 text-right font-medium">R</th>
                <th className="w-14 py-2 pl-3 text-right font-medium">F1</th>
              </tr>
            </thead>
            <tbody>
              {(results.prf ?? []).map((r, i) => (
                <tr key={i} className="border-b border-slate-50">
                  <td className="py-2 pr-2 text-slate-700">
                    <span className="text-slate-400">{r.dataset}</span> {r.method}
                  </td>
                  <td className="py-2 pl-3 text-right tabular-nums text-slate-600">{num(r.precision)}</td>
                  <td className="py-2 pl-3 text-right tabular-nums text-slate-600">{num(r.recall)}</td>
                  <td className="py-2 pl-3 text-right font-semibold tabular-nums text-indigo-700">{num(r.f1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {decay && (
        <div className="mt-6">
          <h3 className="mb-3 text-[13px] font-semibold text-slate-900">
            Decay-injection test: known-good links, target code deliberately broken ({decay.links_used ?? decay.sample_links} links, {decay.model})
          </h3>
          <ul className="space-y-2">
            {Object.entries(decay.per_mutation).map(([name, v]) => {
              const control = name.includes("control");
              const rate = v.injected ? v.detected / v.injected : 0;
              return (
                <li key={name} className="flex items-center gap-3 text-[13px]">
                  <span className="w-44 shrink-0 text-slate-700">{name.replaceAll("_", " ")}</span>
                  <div className="flex-1">
                    <Bar value={rate} tone={control ? "orange" : rate >= 0.85 ? "green" : "red"} />
                  </div>
                  <span className="w-20 shrink-0 text-right tabular-nums text-slate-600">
                    {v.detected}/{v.injected}
                  </span>
                  <span className="w-28 shrink-0 text-[11px] text-slate-400">{control ? "should be 0 (false decay)" : v.injected === 0 ? "not applicable to the data" : "should be flagged"}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {Array.isArray(pending) && pending.length > 0 && (
        <p className="mt-4 text-[12px] text-slate-400">Still pending: {pending.join("; ")}.</p>
      )}
    </Card>
  );
}

const datasetNames = { ebt: "EBT (test)", libest: "LibEST (test)", cm1: "CM-1 (test)", etour: "eTour", smos: "SMOS", eanci: "eANCI", itrust: "iTrust" };
const modelNames = ["MiniLM", "code-search", "UniXcoder"];

export function RerankerPanel({ analysis }) {
  const r = analysis?.reranker;
  const emb = analysis?.stage1Embeddings;
  if (!analysis) return <Card title="Stage-1 and reranker experiments"><Empty>Loading...</Empty></Card>;
  const top5 = r?.petclinic_with_llm?.top5;
  const qe = r?.query_expansion;

  return (
    <Card
      title="What was tried to improve the shortlist"
      subtitle="Held-out tests on LibEST, CM-1 and EBT (never used in training). Full tables: docs/c4_reranker_and_stage1_analysis.md"
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 p-4">
          <p className="text-[12px] font-semibold text-slate-700">MiniLM cross-encoder fused with stage 1</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-indigo-600">+0.10 to +0.16</p>
          <p className="text-[12px] text-slate-500">more true links in the top 5 per requirement (about 10%, interval above 0)</p>
          <p className="mt-2 text-[12px] text-slate-400">No reliable gain in the order of the top 1 to 3. An untrained model gives a similar gain, so fine-tuning is not shown to help.</p>
        </div>
        <div className="rounded-xl border border-slate-200 p-4">
          <p className="text-[12px] font-semibold text-slate-700">PetClinic with Llama 3.1 8B (same 130 LLM calls)</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-indigo-600">
            {top5 ? `${top5.stage1_confirmed} to ${top5.reranked_confirmed}` : "-"}
          </p>
          <p className="text-[12px] text-slate-500">LLM-confirmed links in the top 5 without and with the reranker</p>
          <p className="mt-2 text-[12px] text-slate-400">No human gold labels; the 8B LLM also makes false positives.</p>
        </div>
        <div className="rounded-xl border border-red-100 bg-red-50/40 p-4">
          <p className="text-[12px] font-semibold text-slate-700">Fine-tuned CodeBERT cross-encoder</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-red-600">did not generalise</p>
          <p className="text-[12px] text-slate-500">CM-1 MRR 0.211 versus 0.876 for stage 1 alone. Not used.</p>
        </div>
        <div className="rounded-xl border border-slate-200 p-4">
          <p className="text-[12px] font-semibold text-slate-700">Query expansion (LLM writes likely class names)</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-700">no gain</p>
          <p className="text-[12px] text-slate-500">
            {qe ? `iTrust top-10 recall ${qe.stage1_recall_hybrid.top10.plain} before and ${qe.stage1_recall_hybrid.top10.expanded} after (20 requirements).` : "Not run."}
          </p>
        </div>
      </div>

      {emb && (
        <div className="mt-6">
          <h3 className="mb-3 text-[13px] font-semibold text-slate-900">Stage-1 recall@10 (hybrid) with three embedding models</h3>
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-400">
                <th className="py-2 text-left font-medium">Dataset</th>
                {modelNames.map((m) => (
                  <th key={m} className="py-2 text-right font-medium">{m}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.keys(datasetNames).map((d) => (
                <tr key={d} className="border-b border-slate-50">
                  <td className="py-2 text-slate-700">{datasetNames[d]}</td>
                  {modelNames.map((m) => {
                    const value = emb[d]?.[m]?.hybrid?.["10"];
                    const best = Math.max(...modelNames.map((x) => emb[d]?.[x]?.hybrid?.["10"] ?? 0));
                    return (
                      <td key={m} className={`py-2 text-right tabular-nums ${value === best ? "font-semibold text-indigo-700" : "text-slate-600"}`}>
                        {num(value)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[11px] text-slate-400">The code-specific models (code-search, UniXcoder) do not beat MiniLM. Bold = best of the three.</p>
        </div>
      )}

      {r?.heldout_retrieval_level?.caveats && (
        <div className="mt-4">
          <StatusBadge type="warning">Limits</StatusBadge>
          <ul className="mt-2 list-disc space-y-0.5 pl-5 text-[12px] text-slate-500">
            {r.heldout_retrieval_level.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

/** The comparisons behind the design choices (verifier LLM, prompt, decay check, CodeBERT), from data/results. */
export function EvidencePanel({ evidence }) {
  if (!evidence) return <Card title="Why these choices"><Empty>Loading...</Empty></Card>;
  const { llmComparison, prompt, decay, codebert } = evidence;
  const bestF1 = llmComparison ? Math.max(...llmComparison.map((m) => m.f1)) : 0;

  return (
    <Card
      title="Why these choices: what was compared"
      subtitle="Each design choice was compared with alternatives on the same data. The numbers are read from the saved result files; the limits are stated under each one."
    >
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {codebert && (
          <div className="rounded-xl border border-slate-200 p-4">
            <p className="text-[12px] font-semibold text-slate-700">Adding a fine-tuned CodeBERT to stage 1 (7 real projects)</p>
            <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-700">
              {pct(codebert.meanBefore)} <span className="text-slate-400">to</span> {pct(codebert.meanAfter)}
            </p>
            <p className="text-[12px] text-slate-500">average recall@10 before and after. Better in {codebert.better} projects, worse in {codebert.worse}.</p>
            <ul className="mt-3 space-y-1.5">
              {codebert.rows.map((r) => (
                <li key={r.project} className="flex items-center gap-2 text-[12px]">
                  <span className="w-14 shrink-0 text-slate-600">{r.project}</span>
                  <div className="flex-1"><Bar value={r.after} tone={r.after >= r.before ? "green" : "red"} /></div>
                  <span className="w-28 shrink-0 text-right tabular-nums text-slate-500">{num(r.before, 2)} to {num(r.after, 2)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] text-slate-400">No supported gain, so CodeBERT is kept only as an extra signal and not claimed as an improvement. The model was trained on LLM-written pairs; training on the real labelled projects is the open next step.</p>
          </div>
        )}

        {llmComparison && (
          <div className="rounded-xl border border-slate-200 p-4">
            <p className="text-[12px] font-semibold text-slate-700">Which LLM verifies the links ({llmComparison[0].pairs} labelled pairs)</p>
            <table className="mt-2 w-full text-[13px]">
              <thead>
                <tr className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-400">
                  <th className="py-2 text-left font-medium">Model</th>
                  <th className="py-2 text-right font-medium">P</th>
                  <th className="py-2 text-right font-medium">R</th>
                  <th className="py-2 text-right font-medium">F1</th>
                  <th className="py-2 text-right font-medium">s</th>
                </tr>
              </thead>
              <tbody>
                {llmComparison.map((m) => (
                  <tr key={m.model} className="border-b border-slate-50">
                    <td className="py-2 text-slate-700">{m.model}{m.noAnswer ? <span className="text-[10px] text-slate-400"> ({m.noAnswer} empty)</span> : null}</td>
                    <td className="py-2 text-right tabular-nums text-slate-600">{num(m.precision, 2)}</td>
                    <td className="py-2 text-right tabular-nums text-slate-600">{num(m.recall, 2)}</td>
                    <td className={`py-2 text-right tabular-nums ${m.f1 === bestF1 ? "font-semibold text-indigo-700" : "text-slate-600"}`}>{num(m.f1, 2)}</td>
                    <td className="py-2 text-right tabular-nums text-slate-500">{m.seconds ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[11px] text-slate-400">One model is strict (high precision, low recall), one lenient. Llama 3.1 8B sits between them and is the one the pipeline was built and measured with. Only 60 pairs: indicative, not strong.</p>
          </div>
        )}

        {prompt && (
          <div className="rounded-xl border border-slate-200 p-4">
            <p className="text-[12px] font-semibold text-slate-700">Verification prompt: expert against evidence ({prompt.judged} labelled links, {prompt.project})</p>
            <div className="mt-3 space-y-2 text-[13px]">
              <div className="flex items-center gap-3"><span className="w-32 shrink-0 text-slate-700">expert prompt</span><div className="flex-1"><Bar value={prompt.expertPrecision} tone="orange" /></div><span className="w-12 text-right tabular-nums text-slate-600">{pct(prompt.expertPrecision, 0)}</span></div>
              <div className="flex items-center gap-3"><span className="w-32 shrink-0 text-slate-700">evidence prompt</span><div className="flex-1"><Bar value={prompt.evidencePrecision} tone="green" /></div><span className="w-12 text-right tabular-nums text-slate-600">{pct(prompt.evidencePrecision, 0)}</span></div>
            </div>
            <p className="mt-2 text-[12px] text-slate-500">Precision of the kept links. The evidence prompt kept {prompt.correctKept} correct links and rejected {prompt.wrongRejected} wrong ones.</p>
            <p className="mt-1 text-[11px] text-slate-400">A trade-off, not a free win: it also rejects correct links, and on a later project (a small BMI calculator) it rejected correct ones. The dashboard therefore uses the expert prompt. One project, labels by an AI reviewer.</p>
          </div>
        )}

        {decay && (
          <div className="rounded-xl border border-slate-200 p-4">
            <p className="text-[12px] font-semibold text-slate-700">Detecting a decayed link: LLM alone against LLM + meaning-change check</p>
            <div className="mt-3 space-y-2 text-[13px]">
              <div className="flex items-center gap-3"><span className="w-32 shrink-0 text-slate-700">LLM only</span><div className="flex-1"><Bar value={decay.llmOnly} tone="orange" /></div><span className="w-12 text-right tabular-nums text-slate-600">{pct(decay.llmOnly, 0)}</span></div>
              <div className="flex items-center gap-3"><span className="w-32 shrink-0 text-slate-700">+ meaning check</span><div className="flex-1"><Bar value={decay.withCheck} tone="green" /></div><span className="w-12 text-right tabular-nums text-slate-600">{pct(decay.withCheck, 0)}</span></div>
            </div>
            <p className="mt-2 text-[12px] text-slate-500">Share of deliberately broken links that were detected ({decay.links} links; the target is 85%). False alarms on harmless edits: {pct(decay.falseAlarms, 0)}.</p>
            <p className="mt-1 text-[11px] text-slate-400">The check was designed around these kinds of edits (numbers, negations, operators), so the number is favourable; real edits are more varied and the sample is small.</p>
          </div>
        )}
      </div>
    </Card>
  );
}
