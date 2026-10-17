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

export function EvaluationPanel({ results }) {
  if (!results) return <Card title="Measured results"><Empty>Loading results...</Empty></Card>;
  const decay = results.decay_injection;
  const recallRows = Object.entries(results.stage1_recall ?? {}).flatMap(([dataset, byK]) =>
    Object.entries(byK).map(([k, v]) => ({ dataset, k, ...v })),
  );

  return (
    <Card
      title="Measured results against the targets"
      subtitle="From data/results/summary.json and the decay-injection test. Samples are small; read the notes."
    >
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Target label="LLM precision" measured="37.5%" target=">= 90%" met={false} note="iTrust, 10 requirements, top-5" />
        <Target label="LLM time per link" measured="52 s" target="<= 5 s" met={false} note="CPU-only server, p95 80 s" />
        <Target
          label="Decay detection"
          measured={decay ? `${(decay.decay_detection_accuracy * 100).toFixed(1)}%` : "-"}
          target=">= 85%"
          met={Boolean(decay) && decay.decay_detection_accuracy >= 0.85}
          note={decay ? `${decay.links_used ?? decay.sample_links} links used${decay.baseline_skipped ? ` (${decay.baseline_skipped} skipped: the LLM rejected them anyway)` : ""}; false decay ${(decay.false_decay_rate * 100).toFixed(0)}%` : ""}
        />
        <Target label="Stage-1 recall (top-10)" measured="41.6%" target=">= 80%" met={false} note="iTrust; the LLM cannot recover a missed link" />
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
                <th className="py-2 text-right font-medium">P</th>
                <th className="py-2 text-right font-medium">R</th>
                <th className="py-2 text-right font-medium">F1</th>
              </tr>
            </thead>
            <tbody>
              {(results.prf ?? []).map((r, i) => (
                <tr key={i} className="border-b border-slate-50">
                  <td className="py-2 pr-2 text-slate-700">
                    <span className="text-slate-400">{r.dataset}</span> {r.method}
                  </td>
                  <td className="py-2 text-right tabular-nums text-slate-600">{num(r.precision)}</td>
                  <td className="py-2 text-right tabular-nums text-slate-600">{num(r.recall)}</td>
                  <td className="py-2 text-right font-semibold tabular-nums text-indigo-700">{num(r.f1)}</td>
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

      {Array.isArray(results.pending) && results.pending.length > 0 && (
        <p className="mt-4 text-[12px] text-slate-400">Still pending: {results.pending.join("; ")}.</p>
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
