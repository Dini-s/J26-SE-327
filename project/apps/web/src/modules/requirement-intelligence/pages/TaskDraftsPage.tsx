import { Sparkles } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useGenerate, useRequirementList, useSprints } from '../api/hooks'
import type { GenerationState, RequirementRow } from '../api/types'
import { FilterBar, NO_FILTERS, type ReviewFilters } from '../components/FilterBar'
import { RequirementList } from '../components/RequirementList'
import { RequirementView } from '../components/RequirementView'
import { Skeleton, Tag } from '../components/ui'
import { useModule } from '../context/ModuleState'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { GENERATION_LABEL } from '../lib/format'

type StateFilter = 'all' | 'ready' | 'clarify' | 'failed' | 'none' | 'waiting'
const FILTERS: StateFilter[] = ['all', 'ready', 'clarify', 'failed', 'none', 'waiting']
const MATCH: Record<StateFilter, (s: GenerationState) => boolean> = {
  all: () => true,
  ready: (s) => s === 'done',
  clarify: (s) => s === 'needs_clarification',
  failed: (s) => s === 'failed' || s === 'manual_review',
  none: (s) => s === 'not_requested',
  waiting: (s) => s === 'queued' || s === 'running',
}

/** The draft of each requirement, with its filters. The progress of the queue and the choice of which drafts to write are on Sources & Findings. */
export function TaskDraftsPage() {
  const { project } = useModule()
  const pid = project?.id
  const toasts = useToasts()
  const [params, setParams] = useSearchParams()
  const selected = params.get('uid')
  const [filter, setFilter] = useState<StateFilter>(() => {
    const asked = params.get('filter')
    return FILTERS.includes(asked as StateFilter) ? (asked as StateFilter) : 'all'
  })
  const [f, setF] = useState<ReviewFilters>(NO_FILTERS)
  const sprints = useSprints(pid)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const generate = useGenerate()
  const filters = useMemo(() => ({ risk: 'all' as const, type: 'all' as const, q: '', sprint: f.sprint === 'all' ? null : f.sprint }), [f.sprint])
  const sprintList = useMemo(() => sprints.data ?? [], [sprints.data])
  const sprintNames = useMemo(() => new Map(sprintList.map((s) => [s.id, s.name])), [sprintList])
  const list = useRequirementList(pid, filters, 500)
  const all = useMemo(() => list.data?.pages.flatMap((p) => p.items) ?? [], [list.data])
  const rows = all.filter((r) => MATCH[filter](r.generation_state))
  const activeUid = selected ?? (list.isFetching ? null : (rows[0]?.uid ?? null))
  const counts = useMemo(() => {
    const c: Record<StateFilter, number> = { all: all.length, ready: 0, clarify: 0, failed: 0, none: 0, waiting: 0 }
    for (const r of all) for (const f of FILTERS) if (f !== 'all' && MATCH[f](r.generation_state)) c[f] += 1
    return c
  }, [all])

  const choose = (uid: string) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        next.set('uid', uid)
        return next
      },
      { replace: true },
    )
  const extra = (r: RequirementRow) => (
    <>
      <Tag tone={r.generation_state === 'done' ? 'ok' : 'neutral'}>{GENERATION_LABEL[r.generation_state]}</Tag>
      {r.generation_state === 'failed' && r.failure_reason && (
        <span className="text-[11px] text-danger-text" data-testid="row-reason">
          {copy.drafts.reason[r.failure_reason] ?? copy.drafts.reason.unknown}
        </span>
      )}
      {r.generation_state === 'not_requested' && (
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md border border-border bg-white px-2 py-0.5 text-[11px] font-medium text-heading hover:bg-primary-light disabled:opacity-50"
          disabled={generate.isPending}
          aria-label={copy.drafts.generateFor(r.id)}
          onClick={(e) => {
            e.stopPropagation()
            generate.mutate(r.uid, { onError: (err) => toasts.push(copy.drafts.startFailed(err.message), 'error') })
          }}
        >
          <Sparkles size={11} aria-hidden="true" /> {copy.drafts.generate}
        </button>
      )}
    </>
  )

  return (
    <div className="space-y-3">
      <div className="c1-card grid overflow-hidden xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]" data-testid="workspace">
        <section className="flex min-w-0 flex-col border-border xl:border-r" aria-label={copy.drafts.listTitle}>
          <div className="border-b border-border p-4">
            <div role="group" aria-label={copy.drafts.filterLabel} className="flex flex-wrap gap-1.5">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  type="button"
                  aria-pressed={filter === f}
                  data-testid={`draft-filter-${f}`}
                  onClick={() => setFilter(f)}
                  className={`rounded-full border px-2.5 py-1 text-[11.5px] font-medium transition-colors ${filter === f ? 'border-primary bg-primary text-white' : 'border-border bg-white text-heading hover:bg-primary-light'}`}
                >
                  {copy.drafts.filter[f]} ({counts[f]})
                </button>
              ))}
            </div>
            <div className="mt-3">
              <FilterBar value={f} onChange={setF} sprints={sprintList} documents={[]} fields={['sprint']} />
            </div>
          </div>
          {list.isError ? (
            <div role="alert" className="m-4 rounded-lg border border-danger-border bg-danger-bg p-3 text-xs text-danger-text">
              {(list.error as Error).message}
            </div>
          ) : list.isLoading || pid === undefined ? (
            <div className="flex flex-col gap-3 p-4" aria-busy="true" aria-label={copy.common.loading}>
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <div className="px-4 py-12 text-center text-xs text-secondary-text" data-testid="empty-list">
              {all.length === 0 ? copy.drafts.noRequirements : copy.drafts.noMatch}
            </div>
          ) : (
            <RequirementList rows={rows} selectedUid={activeUid} onSelect={choose} label={copy.drafts.listTitle} onOpen={() => headingRef.current?.focus()} extra={extra} sprintNames={sprintNames} />
          )}
        </section>
        <div className="min-w-0 border-t border-border xl:border-t-0">
          <RequirementView uid={activeUid} projectId={pid} mode="drafts" headingRef={headingRef} waiting={list.isFetching && selected === null} />
        </div>
      </div>
    </div>
  )
}
