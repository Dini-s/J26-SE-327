import { ArrowRightLeft, FileText, RefreshCw, Sparkles, X } from 'lucide-react'
import type { AnalysisState, Source, Sprint } from '../api/types'
import { copy } from '../copy'
import { formatDate, needsAnalysis } from '../lib/planning'
import { JiraIcon } from './JiraIcon'
import { Spinner, Tag } from './ui'

const kb = (bytes: number) => (bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`)

const BADGE: Record<AnalysisState, string> = {
  analyzed: 'border-success-border bg-success-bg text-success-text',
  analyzing: 'border-info-border bg-info-bg text-blue-800',
  not_analyzed: 'border-warning-border bg-warning-bg text-warning-text',
  failed: 'border-danger-border bg-danger-bg text-danger-text',
}

interface Props {
  source: Source
  /** Requirements of this document in the sprint it is shown under (null when shown without a sprint). */
  count: number | null
  sprints: Sprint[]
  /** Something else is running: the actions wait. */
  busy: boolean
  /** This document is being analysed right now by a button on this card. */
  working: boolean
  onAnalyse: () => void
  onReanalyse: () => void
  onMove: () => void
  onRemove: () => void
  /** Selection for "Analyse selected": a checkbox in front of the document. */
  selected?: boolean
  onToggle?: () => void
}

const action = 'inline-flex items-center gap-1 rounded-md border border-border bg-white px-2 py-1 text-[11.5px] font-medium text-heading hover:bg-primary-light disabled:cursor-not-allowed disabled:opacity-50'

/** One document: what it is, how far the analysis is, what it contains, where it sits, and what can be done with it. */
export function SourceCard({ source: s, count, sprints, busy, working, onAnalyse, onReanalyse, onMove, onRemove, selected, onToggle }: Props) {
  const names = new Map(sprints.map((x) => [x.id, x.name]))
  const analysing = s.analysis_state === 'analyzing' || working
  return (
    <li className="px-3 py-2.5 text-xs" data-testid="source-card" data-state={s.analysis_state} title={s.warnings.join('; ') || undefined}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        {onToggle && <input type="checkbox" checked={!!selected} onChange={onToggle} aria-label={copy.sources.selectDocument(s.filename)} data-testid="source-check" />}
        {s.source_type === 'jira' ? <JiraIcon size={15} /> : <FileText size={15} className="shrink-0 text-primary" aria-hidden="true" />}
        <span className="min-w-0 flex-1 truncate font-medium text-heading">{s.filename}</span>
        <Tag>{copy.sources.type[s.source_type] ?? s.source_type}</Tag>
        <span data-testid="source-state" className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10.5px] font-semibold ${BADGE[s.analysis_state]}`}>
          {analysing && <Spinner className="h-3 w-3" />} {copy.sources.state[analysing ? 'analyzing' : s.analysis_state]}
        </span>
      </div>
      <p className="mt-1 text-[11px] text-secondary-text">
        {[s.pages !== null ? copy.sources.pages(s.pages) : null, kb(s.size_bytes), copy.sources.uploadedOn(formatDate(s.uploaded_at))].filter(Boolean).join(' · ')}
      </p>
      {s.analysis_state === 'analyzed' || s.requirements > 0 ? (
        <p className="mt-1 text-[11.5px] text-body" data-testid="source-counts">
          {[
            count !== null && count !== s.requirements ? `${copy.sources.reqCount(count)} here (${s.requirements} in all)` : copy.sources.reqCount(s.requirements),
            copy.sources.ambCount(s.ambiguities),
            copy.sources.draftsReady(s.drafts.ready),
            copy.sources.draftsClarify(s.drafts.needs_clarification),
            copy.sources.draftsFailed(s.drafts.failed),
          ].join(' · ')}
        </p>
      ) : null}
      {s.sprints.length > 0 && (
        <ul className="mt-1.5 flex flex-wrap gap-1.5" aria-label={copy.plan.sprint}>
          {s.sprints.map((p) => (
            <li key={p.sprint_id ?? 'none'} data-testid="sprint-chip" className="rounded-full border border-border bg-secondary-bg px-2 py-0.5 text-[10.5px] text-heading">
              {copy.sources.sprintChip(p.sprint_id !== null ? (names.get(p.sprint_id) ?? '—') : copy.plan.unassigned, p.count)}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {needsAnalysis(s) ? (
          <button type="button" className={action} disabled={busy} aria-label={copy.sources.analyseDocument(s.filename)} onClick={onAnalyse}>
            <Sparkles size={12} aria-hidden="true" /> {copy.sources.analyse}
          </button>
        ) : (
          <button type="button" className={action} disabled={busy || analysing} aria-label={copy.sources.reanalyseDocument(s.filename)} onClick={onReanalyse}>
            <RefreshCw size={12} aria-hidden="true" /> {copy.sources.reanalyse}
          </button>
        )}
        <button type="button" className={action} disabled={busy} aria-label={copy.sources.moveDocument(s.filename)} onClick={onMove}>
          <ArrowRightLeft size={12} aria-hidden="true" /> {copy.sources.moveToSprint}
        </button>
        <button type="button" className={`${action} hover:!bg-danger-bg hover:!text-danger-text`} disabled={busy} aria-label={copy.sources.removeFile(s.filename)} title={busy ? copy.sources.busyHint : undefined} onClick={onRemove}>
          <X size={12} aria-hidden="true" /> {copy.sources.remove}
        </button>
      </div>
    </li>
  )
}
