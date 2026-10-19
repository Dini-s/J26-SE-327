import { Sparkles } from 'lucide-react'
import type { RequirementDetail } from '../api/types'
import { copy } from '../copy'
import { levelLabel, sourceLabel } from '../lib/format'

/** The service writes `defect` in backticks; show it as plain text. */
const plain = (text: string) => text.replace(/`/g, '')

function dominantTitle(d: RequirementDetail): string {
  if (d.conflicts.length) return copy.analysis.conflict
  if (d.ambiguity.label === 'defect') return copy.analysis.ambiguity
  if (d.duplicates.length) return copy.analysis.duplicate
  if (d.security.is_security) return copy.analysis.security
  return copy.analysis.none
}

/** The issues found for one requirement, built from what the service returns (messages, partners, similarities). Nothing is added here. */
export function ExplanationCard({ detail: d }: { detail: RequirementDetail }) {
  const securityMessage = d.findings.find((f) => f.type === 'security')
  return (
    <section className="rounded-xl border border-ai-border bg-ai-bg p-4" aria-label={copy.analysis.issues} data-testid="explanation-card">
      <div className="flex items-center gap-2">
        <Sparkles size={16} className="text-ai-primary" aria-hidden="true" />
        <span className="c1-label !text-ai-primary">{copy.analysis.issues}</span>
      </div>
      <h3 className="mt-2 text-sm font-semibold text-ai-primary">{dominantTitle(d)}</h3>

      {d.ambiguity.label === 'defect' && (
        <p className="mt-1.5 text-xs text-ai-text" data-testid="flagged-unclear">
          {copy.analysis.flaggedUnclear(levelLabel(d.ambiguity.probability_defect))}
        </p>
      )}
      {d.ambiguity.weak_words.length > 0 && <p className="mt-1.5 text-xs text-ai-text">{copy.analysis.vagueWords(d.ambiguity.weak_words.join(', '))}</p>}

      {d.security.is_security && (
        <div className="mt-2 text-xs text-ai-text">
          <p>{plain(securityMessage?.message ?? copy.analysis.securityFallback)}</p>
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
            <div key={p.uid} className="rounded-lg border border-ai-border bg-white p-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-bold text-primary">{p.id}</span>
                <span className="text-secondary-text">{copy.analysis.similarity(levelLabel(p.similarity, [0.9, 0.8]))}</span>
              </div>
              <p className="mt-1 text-heading">{p.text}</p>
              <p className="mt-1 text-[10.5px] text-muted">{sourceLabel(p.source_file, p.page, p.paragraph)}</p>
            </div>
          ))}
        </div>
      )}

      {d.conflicts.map((p) => (
        <div key={p.uid} className="mt-3" data-testid="conflict-partner">
          <div className="grid gap-2 md:grid-cols-2">
            <div className="rounded-lg border border-ai-border bg-white p-3 text-xs">
              <div className="font-bold text-primary">{copy.analysis.thisRequirement(d.id)}</div>
              <p className="mt-1 text-heading">{d.text}</p>
            </div>
            <div className="rounded-lg border border-danger-border bg-white p-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold text-primary">{p.id}</span>
                <span className="text-secondary-text">{copy.analysis.similarity(levelLabel(p.similarity, [0.9, 0.8]))}</span>
              </div>
              <p className="mt-1 text-heading">{p.text}</p>
              <p className="mt-1 text-[10.5px] text-muted">{sourceLabel(p.source_file, p.page, p.paragraph)}</p>
            </div>
          </div>
          {p.reason && <p className="mt-2 text-xs text-danger-text">{p.reason}</p>}
        </div>
      ))}

      {d.findings.length === 0 && <p className="mt-1.5 text-xs text-ai-text">{copy.analysis.noFindings}</p>}
    </section>
  )
}
