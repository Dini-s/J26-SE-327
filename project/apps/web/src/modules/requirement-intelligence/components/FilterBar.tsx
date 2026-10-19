import { ChevronDown, SlidersHorizontal, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { FindingType, RiskFilter, Sprint, SuggestAction } from '../api/types'
import { copy } from '../copy'

export interface ReviewFilters {
  risk: RiskFilter
  type: FindingType
  suggested: 'all' | SuggestAction
  sprint: number | 'all'
  document: string
}

export const NO_FILTERS: ReviewFilters = { risk: 'all', type: 'all', suggested: 'all', sprint: 'all', document: 'all' }

export type FilterField = keyof ReviewFilters

const RISKS: RiskFilter[] = ['all', 'HIGH', 'MEDIUM', 'LOW', 'NONE']
const TYPES: FindingType[] = ['all', 'ambiguity', 'conflict', 'duplicate', 'security']
const SUGGESTIONS: ('all' | SuggestAction)[] = ['all', 'accept', 'edit', 'reject']

const select = 'mt-1 block w-full appearance-none rounded-lg border border-border bg-secondary-bg py-1.5 pl-3 pr-8 text-xs text-heading'

interface Props {
  value: ReviewFilters
  onChange: (next: ReviewFilters) => void
  sprints: Sprint[]
  documents: string[]
  /** Which filters this list offers (the Review Queue all of them, Task Drafts the sprint). */
  fields: FilterField[]
}

/** Active filters as removable chips, in the order they appear in the panel. */
export function activeFilters(v: ReviewFilters, sprints: Sprint[], fields: FilterField[]): { field: FilterField; label: string }[] {
  const out: { field: FilterField; label: string }[] = []
  for (const f of fields) {
    if (f === 'risk' && v.risk !== 'all') out.push({ field: f, label: copy.filters.chipRisk(copy.common.risk[v.risk]) })
    if (f === 'type' && v.type !== 'all') out.push({ field: f, label: copy.filters.chipType(copy.review.types[v.type]) })
    if (f === 'suggested' && v.suggested !== 'all') out.push({ field: f, label: copy.filters.chipSuggested(copy.suggest.word[v.suggested]) })
    if (f === 'sprint' && v.sprint !== 'all') out.push({ field: f, label: copy.filters.chipSprint(sprints.find((s) => s.id === v.sprint)?.name ?? '—') })
    if (f === 'document' && v.document !== 'all') out.push({ field: f, label: copy.filters.chipDocument(v.document) })
  }
  return out
}

/** One "Filters" button with a panel of selects, and a chip for every active filter (each removable). */
export function FilterBar({ value, onChange, sprints, documents, fields }: Props) {
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  const chips = activeFilters(value, sprints, fields)

  useEffect(() => {
    if (!open) return
    const outside = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', outside)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', outside)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  const set = <K extends FilterField>(k: K, v: ReviewFilters[K]) => onChange({ ...value, [k]: v })
  const has = (f: FilterField) => fields.includes(f)
  const field = (label: string, children: ReactNode) => (
    <label className="relative block text-xs text-secondary-text">
      {label}
      {children}
      <ChevronDown size={13} className="pointer-events-none absolute bottom-2 right-2.5 text-secondary-text" aria-hidden="true" />
    </label>
  )

  return (
    <div className="flex flex-wrap items-center gap-2" ref={wrap}>
      <div className="relative">
        <button type="button" className="c1-btn-secondary" aria-haspopup="dialog" aria-expanded={open} data-testid="filters-button" onClick={() => setOpen((o) => !o)}>
          <SlidersHorizontal size={14} aria-hidden="true" /> {chips.length ? copy.filters.buttonCount(chips.length) : copy.filters.button}
        </button>
        {open && (
          <div role="dialog" aria-label={copy.filters.panelTitle} data-testid="filters-panel" className="absolute left-0 top-full z-40 mt-1.5 w-[300px] max-w-[88vw] space-y-3 rounded-xl border border-border bg-white p-4 shadow-lg">
            <h3 className="text-sm font-semibold text-heading">{copy.filters.panelTitle}</h3>
            {has('risk') &&
              field(
                copy.filters.risk,
                <select value={value.risk} onChange={(e) => set('risk', e.target.value as RiskFilter)} className={select}>
                  {RISKS.map((r) => (
                    <option key={r} value={r}>
                      {r === 'all' ? copy.findings.allRisks : copy.common.risk[r]}
                    </option>
                  ))}
                </select>,
              )}
            {has('type') &&
              field(
                copy.filters.type,
                <select value={value.type} onChange={(e) => set('type', e.target.value as FindingType)} className={select}>
                  {TYPES.map((t) => (
                    <option key={t} value={t}>
                      {copy.review.types[t]}
                    </option>
                  ))}
                </select>,
              )}
            {has('suggested') &&
              field(
                copy.filters.suggested,
                <select value={value.suggested} onChange={(e) => set('suggested', e.target.value as 'all' | SuggestAction)} className={select}>
                  {SUGGESTIONS.map((s) => (
                    <option key={s} value={s}>
                      {copy.suggest.filter[s]}
                    </option>
                  ))}
                </select>,
              )}
            {has('sprint') &&
              field(
                copy.filters.sprint,
                <select value={String(value.sprint)} onChange={(e) => set('sprint', e.target.value === 'all' ? 'all' : Number(e.target.value))} className={select}>
                  <option value="all">{copy.filters.allSprints}</option>
                  {sprints.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>,
              )}
            {has('document') &&
              field(
                copy.filters.document,
                <select value={value.document} onChange={(e) => set('document', e.target.value)} className={select}>
                  <option value="all">{copy.filters.allDocuments}</option>
                  {documents.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>,
              )}
            <div className="flex items-center justify-between pt-1">
              <button type="button" className="text-xs font-medium text-primary underline-offset-2 hover:underline disabled:text-muted disabled:no-underline" disabled={chips.length === 0} onClick={() => onChange({ ...value, ...Object.fromEntries(fields.map((f) => [f, NO_FILTERS[f]])) })}>
                {copy.filters.clearAll}
              </button>
              <button type="button" className="c1-btn-primary !px-3 !py-1" onClick={() => setOpen(false)}>
                {copy.filters.done}
              </button>
            </div>
          </div>
        )}
      </div>
      {chips.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label={copy.filters.activeLabel} data-testid="filter-chips">
          {chips.map((c) => (
            <li key={c.field} className="inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary-light px-2.5 py-0.5 text-[11px] font-medium text-primary" data-testid="filter-chip">
              {c.label}
              <button type="button" aria-label={copy.filters.removeChip(c.label)} className="rounded-full p-0.5 hover:bg-white" onClick={() => set(c.field, NO_FILTERS[c.field] as never)}>
                <X size={11} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
