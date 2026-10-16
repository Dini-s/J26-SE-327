import { AlertTriangle, Code2, FileText, Layers, ShieldAlert, type LucideIcon } from 'lucide-react'
import type { FindingType, Summary } from '../api/types'
import { Skeleton } from './ui'

interface Line {
  text: string
  testid: string
  title?: string
}

interface CardDef {
  key: string
  label: string
  icon: LucideIcon
  tint: string
  filter: FindingType | null
  value: (s: Summary) => string
  sub: (s: Summary) => string
  /** Further, separately labelled numbers (never added to `value`). */
  lines?: (s: Summary) => Line[]
}

/** Drafts that are not written yet (waiting, running or never requested): the AI count below is only what the model has answered so far. */
const draftsPending = (s: Summary) => s.task_drafts.not_generated + s.task_drafts.in_progress > 0

const CARDS: CardDef[] = [
  { key: 'requirements', label: 'Requirements', icon: FileText, tint: 'bg-brand-50 text-brand-600', filter: 'all', value: (s) => String(s.requirements), sub: () => 'Source-linked' },
  {
    key: 'ambiguities',
    label: 'Ambiguities',
    icon: AlertTriangle,
    tint: 'bg-amber-50 text-amber-600',
    filter: 'ambiguity',
    value: (s) => String(s.ambiguities.count),
    sub: (s) => `Part A · ${s.ambiguities.high_risk} high risk`,
    lines: (s) => {
      const n = s.ambiguities.asked_by_ai
      return [
        {
          text: draftsPending(s) ? `+${n} asked by AI (${n} so far, drafts pending)` : `+${n} asked by AI`,
          title: draftsPending(s)
            ? 'Requirements Part A did not label as ambiguous but the AI model asked for clarification. Some drafts are not written yet, so this can still grow. Not included in the Part A number.'
            : 'Requirements Part A did not label as ambiguous, but the AI model asked for clarification. Not included in the Part A number.',
          testid: 'asked-by-ai',
        },
      ]
    },
  },
  { key: 'conflicts', label: 'Conflicts', icon: ShieldAlert, tint: 'bg-red-50 text-red-600', filter: 'conflict', value: (s) => String(s.conflicts), sub: () => 'Candidate, decision required' },
  { key: 'duplicates', label: 'Duplicates', icon: Layers, tint: 'bg-violet-50 text-violet-600', filter: 'duplicate', value: (s) => String(s.duplicates), sub: () => 'Semantic matches' },
  {
    key: 'drafts',
    label: 'Task drafts',
    icon: Code2,
    tint: 'bg-emerald-50 text-emerald-600',
    filter: null,
    value: (s) => `${s.task_drafts.generated} / ${s.task_drafts.total}`,
    sub: () => 'Generated · human review',
    lines: (s) => {
      const d = s.task_drafts
      const out: Line[] = []
      if (d.needs_clarification > 0) out.push({ text: `${d.needs_clarification} needs clarification`, testid: 'drafts-clarification' })
      if (d.not_generated > 0) out.push({ text: `${d.not_generated} not generated yet`, testid: 'drafts-not-generated' })
      if (d.in_progress > 0) out.push({ text: `${d.in_progress} in progress${d.paused ? ' (paused)' : ''}`, testid: 'drafts-in-progress' })
      if (d.failed > 0) out.push({ text: `${d.failed} failed`, testid: 'drafts-failed' })
      if (d.manual_review > 0) out.push({ text: `${d.manual_review} manual review`, testid: 'drafts-manual-review' })
      return out
    },
  },
]

export function StatCards({ summary, loading, active, onSelect }: { summary?: Summary; loading: boolean; active: FindingType; onSelect: (f: FindingType) => void }) {
  return (
    <section className="mx-6 mt-5 grid grid-cols-2 gap-4 md:grid-cols-3 xl:mx-9 xl:grid-cols-5" aria-label="Summary">
      {CARDS.map((c) => {
        const Icon = c.icon
        const pressed = c.filter !== null && c.filter === active && c.filter !== 'all'
        return (
          <button
            key={c.key}
            type="button"
            data-testid={`stat-${c.key}`}
            aria-pressed={c.filter === null ? undefined : pressed}
            onClick={() => onSelect(c.filter ?? 'all')}
            className={`card flex items-center gap-4 px-5 py-4 text-left transition hover:border-brand-200 ${pressed ? '!border-brand-600 ring-1 ring-brand-600' : ''}`}
          >
            <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${c.tint}`}>
              <Icon size={21} aria-hidden="true" />
            </span>
            <span className="min-w-0">
              <span className="block text-[12.5px] text-ink-body">{c.label}</span>
              {loading || !summary ? (
                <>
                  <Skeleton className="mt-1.5 h-6 w-12" />
                  <Skeleton className="mt-1.5 h-3 w-20" />
                </>
              ) : (
                <>
                  <span className="block text-[26px] font-bold leading-tight text-ink">{c.value(summary)}</span>
                  <span className="block truncate text-[11px] text-ink-muted">{c.sub(summary)}</span>
                  {c.lines?.(summary).map((l) => (
                    <span key={l.testid} className="block text-[11px] font-medium leading-snug text-ai-title" data-testid={l.testid} title={l.title}>
                      {l.text}
                    </span>
                  ))}
                </>
              )}
            </span>
          </button>
        )
      })}
    </section>
  )
}
