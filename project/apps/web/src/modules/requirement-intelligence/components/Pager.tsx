import { ChevronLeft, ChevronRight } from 'lucide-react'
import { copy } from '../copy'

export const PAGE_SIZE = 50
export type PageSize = typeof PAGE_SIZE | 'all'

const KEY = 'requirement-intelligence.pageSize'

/** The remembered page size ("50" or "See all"). Storage can be blocked: then it is simply 50 every visit. */
export function loadPageSize(): PageSize {
  try {
    return window.localStorage.getItem(KEY) === 'all' ? 'all' : PAGE_SIZE
  } catch {
    return PAGE_SIZE
  }
}

export function savePageSize(size: PageSize) {
  try {
    window.localStorage.setItem(KEY, String(size))
  } catch {
    /* not remembered, still applied for this visit */
  }
}

/** The rows of page `page` (0-based) and the numbers the pager shows. */
export function paginate<T>(rows: T[], page: number, size: PageSize) {
  const pages = size === 'all' ? 1 : Math.max(1, Math.ceil(rows.length / size))
  const current = Math.min(Math.max(0, page), pages - 1)
  const from = size === 'all' ? 0 : current * size
  const shown = size === 'all' ? rows : rows.slice(from, from + size)
  return { shown, pages, page: current, from: shown.length ? from + 1 : 0, to: from + shown.length, total: rows.length }
}

interface Props {
  total: number
  page: number
  pages: number
  from: number
  to: number
  size: PageSize
  onPage: (page: number) => void
  onSize: (size: PageSize) => void
}

const nav = 'inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 font-medium text-heading hover:bg-primary-light disabled:cursor-not-allowed disabled:opacity-50'

/** "Showing 1-20 of N", previous / next, and the page size choice (50 | See all). All of it works from the keyboard. */
export function Pager({ total, page, pages, from, to, size, onPage, onSize }: Props) {
  return (
    <nav aria-label={copy.pager.label} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-border px-4 py-2.5 text-xs text-secondary-text" data-testid="pager">
      <span data-testid="pager-showing" aria-live="polite">
        {size === 'all' ? copy.pager.showingAll(total) : copy.pager.showing(from, to, total)}
      </span>
      <div className="flex flex-wrap items-center gap-2">
        {size !== 'all' && pages > 1 && (
          <>
            <button type="button" className={nav} disabled={page <= 0} onClick={() => onPage(page - 1)} data-testid="pager-previous">
              <ChevronLeft size={13} aria-hidden="true" /> {copy.pager.previous}
            </button>
            <span className="tabular-nums">{copy.pager.page(page + 1, pages)}</span>
            <button type="button" className={nav} disabled={page >= pages - 1} onClick={() => onPage(page + 1)} data-testid="pager-next">
              {copy.pager.next} <ChevronRight size={13} aria-hidden="true" />
            </button>
          </>
        )}
        <div role="group" aria-label={copy.pager.size} className="inline-flex overflow-hidden rounded-md border border-border">
          {([PAGE_SIZE, 'all'] as const).map((s, i) => (
            <button
              key={s}
              type="button"
              aria-pressed={size === s}
              data-testid={`page-size-${s}`}
              onClick={() => onSize(s)}
              className={`px-2.5 py-1 font-medium ${i > 0 ? 'border-l border-border' : ''} ${size === s ? 'bg-primary text-white' : 'bg-white text-heading hover:bg-primary-light'}`}
            >
              {s === 'all' ? copy.pager.all : copy.pager.first}
            </button>
          ))}
        </div>
      </div>
    </nav>
  )
}
