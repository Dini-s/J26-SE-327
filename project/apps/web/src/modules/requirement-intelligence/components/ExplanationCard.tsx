import { AlertTriangle, Check, ShieldAlert } from 'lucide-react'
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

export type IssueLevel = 'ok' | 'warning' | 'danger'

/** Green: nothing found. Yellow: something to look at (unclear wording, a possible duplicate, security, vague words). Red: a candidate conflict or a high risk. */
export function issueLevel(d: RequirementDetail): IssueLevel {
  if (d.conflicts.length > 0 || d.risk.level === 'HIGH') return 'danger'
  if (d.findings.length > 0 || d.ambiguity.label === 'defect' || d.ambiguity.weak_words.length > 0 || d.duplicates.length > 0 || d.security.is_security) return 'warning'
  return 'ok'
}

const STYLE: Record<IssueLevel, { box: string; icon: typeof Check }> = {
  ok: { box: 'border-success-border bg-success-bg text-success-text', icon: Check },
  warning: { box: 'border-warning-border bg-warning-bg text-warning-text', icon: AlertTriangle },
  danger: { box: 'border-danger-border bg-danger-bg text-danger-text', icon: ShieldAlert },
}

/**
 * A round status icon for the requirement (green, yellow or red) that replaces the "Issues found" card. Hover or focus shows what was found.
 * It is built from what the service returns (messages, words, partners); nothing is added here.
 */
export function IssueIndicator({ detail: d }: { detail: RequirementDetail }) {
  const level = issueLevel(d)
  const { box, icon: Icon } = STYLE[level]
  const securityMessage = d.findings.find((f) => f.type === 'security')
  const title = dominantTitle(d)
  return (
    <span className="group absolute right-3 top-3" data-testid="issue-indicator" data-level={level}>
      <button
        type="button"
        aria-label={`${copy.analysis.issues}: ${title}`}
        aria-describedby={`issue-help-${d.uid}`}
        className={`flex h-8 w-8 items-center justify-center rounded-full border ${box} shadow-sm transition-transform hover:scale-105 focus-visible:scale-105`}
      >
        <Icon size={16} strokeWidth={2.4} aria-hidden="true" />
      </button>
      <span
        id={`issue-help-${d.uid}`}
        role="tooltip"
        data-testid="explanation-card"
        className="pointer-events-none absolute right-0 top-full z-30 mt-2 hidden w-72 rounded-lg border border-border bg-white p-3 text-left text-xs text-body shadow-lg group-hover:block group-focus-within:block"
      >
        <span className="block text-[10.5px] font-semibold uppercase tracking-wide text-muted">{copy.analysis.issues}</span>
        <span className="mt-0.5 block text-[13px] font-semibold text-heading">{title}</span>
        {d.ambiguity.label === 'defect' && (
          <span className="mt-1.5 block" data-testid="flagged-unclear">
            {copy.analysis.flaggedUnclear(levelLabel(d.ambiguity.probability_defect))}
          </span>
        )}
        {d.ambiguity.weak_words.length > 0 && <span className="mt-1.5 block">{copy.analysis.vagueWords(d.ambiguity.weak_words.join(', '))}</span>}
        {d.security.is_security && (
          <span className="mt-1.5 block">
            {plain(securityMessage?.message ?? copy.analysis.securityFallback)}
            <span className="mt-1.5 flex flex-wrap gap-1.5">
              {d.security.cue_words.map((w) => (
                <span key={w} className="rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700">
                  {w}
                </span>
              ))}
            </span>
          </span>
        )}
        {d.conflicts.length > 0 && <span className="mt-1.5 block">{copy.analysis.relatedBelow}</span>}
        {d.duplicates.length > 0 && <span className="mt-1.5 block">{copy.analysis.relatedBelow}</span>}
        {d.findings.length === 0 && <span className="mt-1.5 block">{copy.analysis.noFindings}</span>}
      </span>
    </span>
  )
}

/** The requirements that were found to repeat or to contradict this one, side by side with it. Shown only when there are some. */
export function RelatedRequirements({ detail: d }: { detail: RequirementDetail }) {
  if (d.duplicates.length === 0 && d.conflicts.length === 0) return null
  return (
    <section className="rounded-xl border border-border bg-white p-4" aria-label={copy.analysis.related} data-testid="related-card">
      <div className="c1-label">{copy.analysis.related}</div>
      {d.duplicates.length > 0 && (
        <div className="mt-2 space-y-2" data-testid="duplicate-partners">
          {d.duplicates.map((p) => (
            <div key={p.uid} className="rounded-lg border border-border bg-[#fafbfe] p-3 text-xs">
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
            <div className="rounded-lg border border-border bg-[#fafbfe] p-3 text-xs">
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
    </section>
  )
}
