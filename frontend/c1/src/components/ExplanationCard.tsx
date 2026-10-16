import { Sparkles } from 'lucide-react'
import type { RequirementDetail } from '../api/types'
import { sourceLabel } from '../lib/format'

/** The API writes `defect` in backticks; show it as plain text. */
const plain = (text: string) => text.replace(/`/g, '')

function dominantTitle(d: RequirementDetail): string {
  if (d.conflicts.length) return 'Candidate conflict, needs human decision'
  if (d.ambiguity.label === 'defect') return 'Ambiguity detected'
  if (d.duplicates.length) return 'Possible duplicate'
  if (d.security.is_security) return 'Security-related requirement'
  return 'No finding'
}

/** Explanation built from the detector output the API returns (messages, partners, similarities). Nothing is added here. */
export function ExplanationCard({ detail: d }: { detail: RequirementDetail }) {
  const ambiguityMessages = d.findings.filter((f) => f.type === 'ambiguity' || f.type === 'weak_word')
  const securityMessage = d.findings.find((f) => f.type === 'security')
  return (
    <section className="rounded-card border border-ai-line bg-ai-bg p-5" aria-label="Explanation" data-testid="explanation-card">
      <div className="flex items-center gap-2">
        <Sparkles size={18} className="text-ai-title" aria-hidden="true" />
        <span className="label-caps !text-ai-title">Explanation · from detector output</span>
      </div>
      <h3 className="mt-3 text-[15px] font-semibold text-ai-title">{dominantTitle(d)}</h3>

      {ambiguityMessages.map((f, i) => (
        <p key={i} className="mt-1.5 text-[13px] text-ai-text">
          {plain(f.message)}
        </p>
      ))}

      {d.security.is_security && (
        <div className="mt-2 text-[13px] text-ai-text">
          <p>{plain(securityMessage?.message ?? 'Security-related.')}</p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {d.security.cue_words.map((w) => (
              <span key={w} className="rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700">
                {w}
              </span>
            ))}
          </div>
        </div>
      )}

      {d.duplicates.length > 0 && (
        <div className="mt-3 space-y-2" data-testid="duplicate-partners">
          {d.duplicates.map((p) => (
            <div key={p.uid} className="rounded-ctl border border-ai-line bg-white p-3 text-[13px]">
              <div className="flex items-center justify-between gap-2 text-[12px]">
                <span className="font-bold text-brand-600">{p.id}</span>
                <span className="text-ink-muted">similarity {p.similarity.toFixed(3)}</span>
              </div>
              <p className="mt-1 text-ink">{p.text}</p>
              <p className="mt-1 text-[10.5px] text-ink-faint">{sourceLabel(p.source_file, p.page, p.paragraph)}</p>
            </div>
          ))}
        </div>
      )}

      {d.conflicts.map((p) => (
        <div key={p.uid} className="mt-3" data-testid="conflict-partner">
          <div className="grid gap-2 md:grid-cols-2">
            <div className="rounded-ctl border border-ai-line bg-white p-3 text-[13px]">
              <div className="text-[12px] font-bold text-brand-600">{d.id} (this requirement)</div>
              <p className="mt-1 text-ink">{d.text}</p>
            </div>
            <div className="rounded-ctl border border-risk-highLine bg-white p-3 text-[13px]">
              <div className="flex items-center justify-between text-[12px]">
                <span className="font-bold text-brand-600">{p.id}</span>
                <span className="text-ink-muted">similarity {p.similarity.toFixed(2)}</span>
              </div>
              <p className="mt-1 text-ink">{p.text}</p>
              <p className="mt-1 text-[10.5px] text-ink-faint">{sourceLabel(p.source_file, p.page, p.paragraph)}</p>
            </div>
          </div>
          {p.reason && <p className="mt-2 text-[12.5px] text-risk-highText">{p.reason}</p>}
        </div>
      ))}

      {d.findings.length === 0 && <p className="mt-1.5 text-[13px] text-ai-text">No ambiguity, weak word, security, duplicate or conflict finding from the Part A detectors.</p>}
      <details className="mt-3 border-t border-ai-line pt-2 text-[11.5px] text-ink-muted">
        <summary className="cursor-pointer font-medium">Full explanation text from the API</summary>
        <p className="mt-1 leading-relaxed">{plain(d.explanation)}</p>
      </details>
    </section>
  )
}
