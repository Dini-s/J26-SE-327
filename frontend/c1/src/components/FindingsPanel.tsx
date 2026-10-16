import { AlertTriangle, ChevronDown, FileText, Layers, Lock, Search, ShieldAlert, type LucideIcon } from 'lucide-react'
import { useEffect, useState, type KeyboardEvent } from 'react'
import type { FindingType, ListFilters, RequirementRow, RiskFilter } from '../api/types'
import { SEARCH_DEBOUNCE_MS } from '../config'
import { TYPE_LABEL, primaryType, sourceLabel, type PrimaryType } from '../lib/format'
import { AiClarifyBadge, RiskBadge, Skeleton } from './ui'

const ICON: Record<PrimaryType, { icon: LucideIcon; tint: string }> = {
  conflict: { icon: ShieldAlert, tint: 'text-red-600' },
  ambiguity: { icon: AlertTriangle, tint: 'text-amber-600' },
  duplicate: { icon: Layers, tint: 'text-violet-600' },
  security: { icon: Lock, tint: 'text-sky-600' },
  none: { icon: FileText, tint: 'text-ink-faint' },
}

export function FindingRow({ row, selected, onSelect }: { row: RequirementRow; selected: boolean; onSelect: () => void }) {
  const kind = primaryType(row.flags)
  const { icon: Icon, tint } = ICON[kind]
  return (
    <li
      id={`row-${row.uid}`}
      role="option"
      aria-selected={selected}
      data-testid="finding-row"
      onClick={onSelect}
      className={`flex cursor-pointer items-start gap-3.5 border-b border-line border-l-[3px] px-5 py-3.5 transition-colors last:border-b-0 ${
        selected ? 'border-l-brand-600 bg-brand-50' : 'border-l-transparent hover:bg-[#fafbff]'
      }`}
    >
      <Icon size={24} className={`mt-0.5 shrink-0 ${tint}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-[12.5px]">
          <span className="font-bold text-brand-600">{row.id}</span>
          <span className="text-ink-muted">{TYPE_LABEL[kind]}</span>
          {row.generation_state === 'needs_clarification' && <AiClarifyBadge />}
          {row.decision && <span className="rounded bg-ok-bg px-1.5 py-px text-[10px] font-semibold uppercase text-ok-text">{row.decision}</span>}
        </div>
        <p className="mt-0.5 line-clamp-2 text-[13.5px] leading-snug text-ink">{row.text}</p>
        <p className="mt-1 truncate text-[10.5px] text-ink-faint">{sourceLabel(row.source_file, row.page, row.paragraph)}</p>
      </div>
      <RiskBadge level={row.risk_level} />
    </li>
  )
}

const RISKS: { value: RiskFilter; label: string }[] = [
  { value: 'all', label: 'All risks' },
  { value: 'HIGH', label: 'High' },
  { value: 'MEDIUM', label: 'Medium' },
  { value: 'LOW', label: 'Low' },
  { value: 'NONE', label: 'None' },
]
const TYPES: { value: FindingType; label: string }[] = [
  { value: 'all', label: 'All types' },
  { value: 'ambiguity', label: 'Ambiguity' },
  { value: 'conflict', label: 'Conflict' },
  { value: 'duplicate', label: 'Duplicate' },
  { value: 'security', label: 'Security' },
]

interface Props {
  filters: ListFilters
  onFilters: (f: ListFilters) => void
  rows: RequirementRow[]
  total: number
  open: number | undefined
  loading: boolean
  error: string | null
  hasSources: boolean
  selectedUid: string | null
  onSelect: (uid: string) => void
  onOpen: () => void
  onMore: () => void
  hasMore: boolean
  loadingMore: boolean
}

export function FindingsPanel(p: Props) {
  const [text, setText] = useState(p.filters.q)
  const { filters, onFilters } = p

  // debounce the search box into the filters
  useEffect(() => {
    if (text === filters.q) return
    const id = window.setTimeout(() => onFilters({ ...filters, q: text }), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(id)
  }, [text, filters, onFilters])

  const move = (delta: number) => {
    if (!p.rows.length) return
    const i = p.rows.findIndex((r) => r.uid === p.selectedUid)
    const next = p.rows[Math.min(p.rows.length - 1, Math.max(0, i < 0 ? 0 : i + delta))]!
    p.onSelect(next.uid)
    document.getElementById(`row-${next.uid}`)?.scrollIntoView({ block: 'nearest' })
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      move(1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      move(-1)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      p.onOpen()
    }
  }

  const filtered = p.filters.risk !== 'all' || p.filters.type !== 'all' || p.filters.q.trim() !== ''
  return (
    <section className="flex min-w-0 flex-col" aria-label="Requirement intelligence findings">
      <div className="border-b border-line px-5 pb-4 pt-5">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-[19px] font-medium text-ink">Requirement intelligence findings</h2>
          <span className="shrink-0 rounded-full bg-risk-noneBg px-2.5 py-0.5 text-[11px] font-medium text-ink-body" title="Findings on requirements that have no decision yet">
            {p.open === undefined ? '…' : p.open} open
          </span>
        </div>
        <p className="mt-1 text-[12px] text-ink-muted">Ambiguity, conflict and duplicate findings requiring human review</p>
        <div className="mt-4 flex flex-wrap gap-2.5">
          <label className="relative min-w-[180px] flex-1">
            <span className="sr-only">Search requirements or findings</span>
            <Search size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
            <input
              type="search"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Search requirements or findings"
              className="w-full rounded-ctl border border-line bg-[#f7f8fc] py-2.5 pl-10 pr-3 text-[13px] text-ink placeholder:text-ink-faint"
            />
          </label>
          <label className="relative">
            <span className="sr-only">Risk filter</span>
            <select
              value={p.filters.risk}
              onChange={(e) => p.onFilters({ ...p.filters, risk: e.target.value as RiskFilter })}
              className="h-full appearance-none rounded-ctl border border-line bg-[#f7f8fc] py-2.5 pl-3.5 pr-9 text-[13px] text-ink"
            >
              {RISKS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            <ChevronDown size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden="true" />
          </label>
          <label className="relative">
            <span className="sr-only">Type filter</span>
            <select
              value={p.filters.type}
              onChange={(e) => p.onFilters({ ...p.filters, type: e.target.value as FindingType })}
              className="h-full appearance-none rounded-ctl border border-line bg-[#f7f8fc] py-2.5 pl-3.5 pr-9 text-[13px] text-ink"
            >
              {TYPES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            <ChevronDown size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden="true" />
          </label>
        </div>
      </div>

      {p.error ? (
        <div role="alert" className="m-5 rounded-ctl border border-risk-highLine bg-risk-highBg p-4 text-[13px] text-risk-highText">
          {p.error}
        </div>
      ) : p.loading ? (
        <div className="flex flex-col gap-4 p-5" aria-busy="true" aria-label="Loading requirements">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="flex gap-3">
              <Skeleton className="h-6 w-6" />
              <div className="flex-1">
                <Skeleton className="h-3 w-28" />
                <Skeleton className="mt-2 h-4 w-full" />
                <Skeleton className="mt-2 h-3 w-40" />
              </div>
            </div>
          ))}
        </div>
      ) : p.rows.length === 0 ? (
        <div className="px-5 py-12 text-center text-[13.5px] text-ink-muted" data-testid="empty-list">
          {!p.hasSources && !filtered
            ? 'Upload an SRS to begin.'
            : filtered
              ? 'No requirements match these filters.'
              : 'No requirements yet. Choose “Run analysis” to find them in the uploaded sources.'}
        </div>
      ) : (
        <>
          <ul
            role="listbox"
            tabIndex={0}
            aria-label="Requirements"
            aria-activedescendant={p.selectedUid ? `row-${p.selectedUid}` : undefined}
            onKeyDown={onKey}
            className="max-h-[640px] overflow-y-auto focus-visible:outline-offset-[-2px]"
          >
            {p.rows.map((r) => (
              <FindingRow key={r.uid} row={r} selected={r.uid === p.selectedUid} onSelect={() => p.onSelect(r.uid)} />
            ))}
          </ul>
          <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-3 text-[12px] text-ink-muted">
            <span>
              Showing {p.rows.length} of {p.total}
            </span>
            {p.hasMore && (
              <button type="button" className="rounded-md border border-line px-3 py-1.5 font-medium text-ink hover:bg-brand-50 disabled:opacity-50" disabled={p.loadingMore} onClick={p.onMore}>
                {p.loadingMore ? 'Loading…' : 'Show more'}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  )
}
