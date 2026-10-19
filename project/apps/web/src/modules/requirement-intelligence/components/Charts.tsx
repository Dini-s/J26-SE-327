import type { ReactNode } from 'react'
import type { Overview } from '../api/types'
import { copy } from '../copy'

/** Colours of the decision statuses and the finding types, written out so they never depend on generated style classes. */
export const DECISION_COLOR = { accepted: '#10b981', edited: '#3b82f6', rejected: '#ef4444', pending: '#e2e8f0' } as const
const FINDING_COLOR: Record<string, string> = { ambiguity: '#f59e0b', conflict: '#ef4444', duplicate: '#8b5cf6', security: '#0ea5e9' }
const STATUSES = ['accepted', 'edited', 'rejected', 'pending'] as const

function Legend() {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-secondary-text" aria-label={copy.progress.legend}>
      {STATUSES.map((k) => (
        <li key={k} className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: DECISION_COLOR[k] }} aria-hidden="true" />
          {copy.overview.status[k]}
        </li>
      ))}
    </ul>
  )
}

function Card({ title, text, children, testid }: { title: string; text: string; children: ReactNode; testid: string }) {
  return (
    <section className="c1-card p-4" aria-label={title} data-testid={testid}>
      <h2 className="text-sm font-semibold text-heading">{title}</h2>
      {/* the same numbers as words, for anyone who cannot see the bars */}
      <p className="sr-only" data-testid={`${testid}-text`}>
        {text}
      </p>
      {children}
    </section>
  )
}

/** One stacked bar per sprint (accepted, edited, rejected, pending). Bars share one scale, so sprints can be compared. */
export function SprintBars({ rows }: { rows: Overview['by_sprint'] }) {
  const max = Math.max(1, ...rows.map((r) => r.total))
  const text = copy.overview.chartSprintsText(rows.map((r) => copy.overview.chartSprintRow(r.name, r.accepted, r.edited, r.rejected, r.pending)).join('; '))
  return (
    <Card title={copy.overview.chartSprints} text={text} testid="chart-sprints">
      {rows.length === 0 ? (
        <p className="mt-3 text-xs text-secondary-text">{copy.overview.noChartData}</p>
      ) : (
        <ul className="mt-3 space-y-2.5">
          {rows.map((r) => (
            <li key={r.sprint_id} data-testid="sprint-bar" data-sprint={r.sprint_id}>
              <div className="flex items-baseline justify-between text-xs">
                <span className="truncate font-medium text-heading">
                  {r.name}
                  {r.is_current && <span className="ml-1.5 text-[10px] font-semibold text-primary">{copy.plan.current}</span>}
                </span>
                <span className="text-secondary-text">{r.total}</span>
              </div>
              <div className="mt-1 h-2.5 w-full rounded-full bg-secondary-bg" aria-hidden="true">
                <div className="flex h-full overflow-hidden rounded-full" style={{ width: `${(r.total / max) * 100}%` }}>
                  {STATUSES.map((k) => (
                    <div key={k} data-segment={k} data-count={r[k]} title={`${copy.overview.status[k]}: ${r[k]}`} style={{ width: `${r.total ? (r[k] / r.total) * 100 : 0}%`, backgroundColor: DECISION_COLOR[k] }} />
                  ))}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Legend />
    </Card>
  )
}

const RADIUS = 46
const CIRCLE = 2 * Math.PI * RADIUS
const percent = (n: number, total: number) => (total ? Math.round((n / total) * 1000) / 10 : 0)

/** Requirement status as a ring: accepted, edited, rejected, pending, with the total in the middle and a legend with counts and percentages. */
export function StatusDonut({ decisions, total }: { decisions: Pick<Overview['decisions'], 'accepted' | 'edited' | 'rejected' | 'pending'>; total: number }) {
  const parts = STATUSES.map((k, i) => ({ key: k, n: decisions[k], pct: percent(decisions[k], total), before: STATUSES.slice(0, i).reduce((sum, j) => sum + decisions[j], 0) }))
  const text = copy.overview.donutText(total, parts.map((x) => copy.overview.donutRow(copy.overview.status[x.key], x.n, x.pct)).join('; '))
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-3" data-testid="status-donut">
      <p className="sr-only" data-testid="status-donut-text">
        {text}
      </p>
      <div className="relative h-32 w-32 shrink-0" aria-hidden="true">
        <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
          <circle cx="60" cy="60" r={RADIUS} fill="none" stroke="#f1f5f9" strokeWidth="14" />
          {parts.map((x) => {
            const len = (x.n / total) * CIRCLE
            return x.n > 0 ? (
              <circle key={x.key} data-segment={x.key} data-count={x.n} cx="60" cy="60" r={RADIUS} fill="none" stroke={DECISION_COLOR[x.key]} strokeWidth="14" strokeDasharray={`${len} ${CIRCLE - len}`} strokeDashoffset={-(x.before / total) * CIRCLE}>
                <title>{`${copy.overview.status[x.key]}: ${x.n}`}</title>
              </circle>
            ) : null
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold leading-none text-heading" data-testid="donut-total">
            {total}
          </span>
          <span className="mt-0.5 text-[10.5px] text-secondary-text">{copy.overview.donutCentre}</span>
        </div>
      </div>
      <ul className="min-w-[150px] flex-1 space-y-1.5 text-xs" aria-label={copy.progress.legend}>
        {parts.map((x) => (
          <li key={x.key} className="flex items-center gap-2" data-testid="donut-legend" data-status={x.key}>
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: DECISION_COLOR[x.key] }} aria-hidden="true" />
            <span className="text-heading">{copy.overview.status[x.key]}</span>
            <span className="ml-auto font-medium text-heading">{x.n}</span>
            <span className="w-12 text-right text-secondary-text">{x.pct}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Findings by type, as horizontal bars on one scale. */
export function FindingBars({ counts }: { counts: Overview['findings_by_type'] }) {
  const entries = Object.entries(counts)
  const max = Math.max(1, ...entries.map(([, n]) => n))
  const text = copy.overview.chartFindingsText(entries.map(([k, n]) => copy.overview.findingRow(copy.overview.findingLabels[k] ?? k, n)).join('; '))
  return (
    <Card title={copy.overview.chartFindings} text={text} testid="chart-findings">
      <ul className="mt-3 space-y-2.5">
        {entries.map(([k, n]) => (
          <li key={k} data-testid="finding-bar" data-type={k} data-count={n}>
            <div className="flex items-baseline justify-between text-xs">
              <span className="font-medium text-heading">{copy.overview.findingLabels[k] ?? k}</span>
              <span className="text-secondary-text">{n}</span>
            </div>
            <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-secondary-bg" aria-hidden="true">
              <div className="h-full rounded-full" style={{ width: `${(n / max) * 100}%`, backgroundColor: FINDING_COLOR[k] ?? '#64748b' }} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
