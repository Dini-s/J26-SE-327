import { CheckSquare, Search } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAcceptSelected, useAcceptSuggested, useAssignRequirements, useOverview, useRequirementList, useSprints } from '../api/hooks'
import type { Sprint } from '../api/types'
import { ConfirmDialog, Dialog } from '../components/Dialog'
import { FilterBar, NO_FILTERS, type ReviewFilters } from '../components/FilterBar'
import { Pager, loadPageSize, paginate, savePageSize, type PageSize } from '../components/Pager'
import { FIELD } from '../components/PlanDialogs'
import { RequirementList } from '../components/RequirementList'
import { RequirementView } from '../components/RequirementView'
import { Skeleton, Spinner } from '../components/ui'
import { SEARCH_DEBOUNCE_MS } from '../config'
import { useModule } from '../context/ModuleState'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'

type Status = 'all' | 'pending' | 'accepted' | 'edited' | 'rejected'
const STATUSES: Status[] = ['all', 'pending', 'accepted', 'edited', 'rejected']
const FOLLOW = '__follow'

/** Move the chosen requirements to a sprint (or let them follow their document again). */
function MoveRequirementsDialog({ count, sprints, busy, onCancel, onConfirm }: { count: number; sprints: Sprint[]; busy: boolean; onCancel: () => void; onConfirm: (sprintId: number | null) => void }) {
  const [choice, setChoice] = useState<string>(String(sprints.find((s) => s.is_current)?.id ?? sprints[0]?.id ?? FOLLOW))
  return (
    <Dialog
      title={copy.select.moveTitle(count)}
      onClose={onCancel}
      actions={
        <>
          <button type="button" className="c1-btn-secondary" onClick={onCancel}>
            {copy.common.cancel}
          </button>
          <button type="button" className="c1-btn-primary" disabled={busy} onClick={() => onConfirm(choice === FOLLOW ? null : Number(choice))}>
            {busy && <Spinner className="h-3.5 w-3.5" />} {copy.select.confirm}
          </button>
        </>
      }
    >
      <label className="block text-xs text-secondary-text">
        {copy.select.chooseSprint}
        <select value={choice} onChange={(e) => setChoice(e.target.value)} className={FIELD} data-testid="bulk-sprint">
          {sprints.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
          <option value={FOLLOW}>{copy.select.follow}</option>
        </select>
      </label>
    </Dialog>
  )
}

/** List on the left (status chips, one Filters button, counts per status, pending first), the chosen requirement on the right with its decision card. */
export function ReviewQueuePage() {
  const { project } = useModule()
  const pid = project?.id
  const toasts = useToasts()
  const [params, setParams] = useSearchParams()
  const selected = params.get('uid')
  const [status, setStatus] = useState<Status>('all')
  const [f, setF] = useState<ReviewFilters>(NO_FILTERS)
  const [text, setText] = useState('')
  const [q, setQ] = useState('')
  const [confirmBulk, setConfirmBulk] = useState(false)
  const [confirmSelected, setConfirmSelected] = useState(false)
  const [selecting, setSelecting] = useState(false)
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [moving, setMoving] = useState(false)
  // the page belongs to the filters it was chosen under: another filter, status or search is page 1 again
  const [pageAt, setPageAt] = useState({ key: '', page: 0 })
  const [size, setSize] = useState<PageSize>(loadPageSize)
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    if (text === q) return
    const id = window.setTimeout(() => setQ(text), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(id)
  }, [text, q])

  const filters = useMemo(() => ({ risk: f.risk, type: f.type, q, sprint: f.sprint === 'all' ? null : f.sprint }), [f.risk, f.type, f.sprint, q])
  const list = useRequirementList(pid, filters, 500)
  // the whole list is loaded (it is small), so the pager can count it; a filter, a status or a search starts again at page 1
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = list
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])
  const pageKey = JSON.stringify([status, f, q])
  const page = pageAt.key === pageKey ? pageAt.page : 0
  const setPage = (p: number) => setPageAt({ key: pageKey, page: p })
  const changeSize = (s: PageSize) => {
    setSize(s)
    setPage(0)
    savePageSize(s)
  }

  const overview = useOverview(pid)
  const sprints = useSprints(pid)
  const bulk = useAcceptSuggested(pid)
  const acceptSelected = useAcceptSelected(pid)
  const assign = useAssignRequirements(pid)
  const sprintList = useMemo(() => sprints.data ?? [], [sprints.data])
  const sprintNames = useMemo(() => new Map(sprintList.map((s) => [s.id, s.name])), [sprintList])
  const all = useMemo(() => list.data?.pages.flatMap((p) => p.items) ?? [], [list.data])
  const documents = useMemo(() => Array.from(new Set(all.map((r) => r.source_file))), [all])
  // pending first, then the decided ones; the order inside each group stays the document order
  const rows = all
    .filter((r) => status === 'all' || (status === 'pending' ? r.decision === null : r.decision === status))
    .filter((r) => f.suggested === 'all' || r.suggestion.action === f.suggested)
    .filter((r) => f.document === 'all' || r.source_file === f.document)
    .map((r, i) => ({ r, i }))
    .sort((a, b) => Number(a.r.decision !== null) - Number(b.r.decision !== null) || a.i - b.i)
    .map((x) => x.r)
  const pageInfo = paginate(rows, page, size)
  const activeUid = selected ?? (list.isFetching ? null : (pageInfo.shown[0]?.uid ?? null))
  const select_ = (uid: string) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        next.set('uid', uid)
        return next
      },
      { replace: true },
    )

  const dec = overview.data?.decisions
  const counts: Record<Status, number | undefined> = {
    all: overview.data?.counts.requirements,
    pending: dec?.pending,
    accepted: dec?.accepted,
    edited: dec?.edited,
    rejected: dec?.rejected,
  }
  const filtered = status !== 'all' || (Object.keys(NO_FILTERS) as (keyof ReviewFilters)[]).some((k) => f[k] !== NO_FILTERS[k]) || q.trim() !== ''
  const canBulk = status === 'pending' && f.suggested === 'accept' && rows.length > 0
  const acceptAll = () =>
    bulk.mutate(
      { uids: rows.map((r) => r.uid), note: copy.suggest.bulkComment },
      {
        onSuccess: (r) => {
          setConfirmBulk(false)
          toasts.push(copy.suggest.bulkDone(r.accepted, r.skipped, r.failed), r.failed ? 'error' : 'success')
        },
        onError: (e) => {
          setConfirmBulk(false)
          toasts.push(copy.decision.saveFailed(e.message), 'error')
        },
      },
    )
  // a requirement that already has a decision is left as it is; the list holds the current decisions
  const pendingPicked = all.filter((r) => picked.has(r.uid) && r.decision === null).map((r) => r.uid)
  const onAcceptSelected = () =>
    acceptSelected.mutate(
      { uids: pendingPicked, note: copy.select.acceptComment },
      {
        onSuccess: (r) => {
          setConfirmSelected(false)
          toasts.push(copy.select.acceptDone(r.accepted, r.failed), r.failed ? 'error' : 'success')
          setPicked(new Set())
        },
        onError: (e) => {
          setConfirmSelected(false)
          toasts.push(copy.decision.saveFailed(e.message), 'error')
        },
      },
    )
  const stopSelecting = () => {
    setSelecting(false)
    setPicked(new Set())
  }
  const toggle = (uid: string) =>
    setPicked((old) => {
      const next = new Set(old)
      if (!next.delete(uid)) next.add(uid)
      return next
    })
  const moveSelected = (sprintId: number | null) =>
    assign.mutate(
      { ids: Array.from(picked), sprintId },
      {
        onSuccess: (r) => {
          toasts.push(sprintId === null ? copy.select.movedBack(r.assigned) : copy.select.moved(r.assigned, sprintNames.get(sprintId) ?? ''), 'success')
          setMoving(false)
          stopSelecting()
        },
        onError: (e) => {
          setMoving(false)
          toasts.push(copy.select.failed(e.message), 'error')
        },
      },
    )

  return (
    <div className="c1-card grid overflow-hidden xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]" data-testid="workspace">
      <section className="flex min-w-0 flex-col border-border xl:border-r" aria-label={copy.review.listTitle}>
        <div className="border-b border-border p-4">
          <div role="group" aria-label={copy.review.statusLabel} className="flex flex-wrap gap-1.5">
            {STATUSES.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={status === s}
                data-testid={`status-${s}`}
                onClick={() => setStatus(s)}
                className={`rounded-full border px-2.5 py-1 text-[11.5px] font-medium transition-colors ${status === s ? 'border-primary bg-primary text-white' : 'border-border bg-white text-heading hover:bg-primary-light'}`}
              >
                {copy.review.status[s]} {counts[s] === undefined ? '' : `(${counts[s]})`}
              </button>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <label className="relative min-w-[160px] flex-1">
              <span className="sr-only">{copy.review.search}</span>
              <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" aria-hidden="true" />
              <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder={copy.review.search} className="w-full rounded-lg border border-border bg-secondary-bg py-1.5 pl-9 pr-3 text-xs text-heading placeholder:text-muted" />
            </label>
            <FilterBar value={f} onChange={setF} sprints={sprintList} documents={documents} fields={['risk', 'type', 'suggested', 'sprint', 'document']} />
            <button type="button" className="c1-btn-secondary" aria-pressed={selecting} data-testid="select-mode" onClick={() => (selecting ? stopSelecting() : setSelecting(true))}>
              <CheckSquare size={14} aria-hidden="true" /> {selecting ? copy.select.stop : copy.select.start}
            </button>
          </div>
          {selecting && (
            <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-secondary-bg px-3 py-2 text-xs" data-testid="selection-bar">
              <span className="font-medium text-heading" data-testid="selected-count">
                {copy.select.selected(picked.size)}
              </span>
              <button type="button" className="font-medium text-primary underline-offset-2 hover:underline" data-testid="select-shown" onClick={() => setPicked((old) => new Set([...old, ...pageInfo.shown.map((r) => r.uid)]))}>
                {copy.select.all}
              </button>
              {rows.length > pageInfo.shown.length && (
                <button type="button" className="font-medium text-primary underline-offset-2 hover:underline" data-testid="select-all-n" onClick={() => setPicked(new Set(rows.map((r) => r.uid)))}>
                  {copy.select.allN(rows.length)}
                </button>
              )}
              {picked.size > 0 && (
                <button type="button" className="font-medium text-primary underline-offset-2 hover:underline" data-testid="select-clear" onClick={() => setPicked(new Set())}>
                  {copy.select.clear}
                </button>
              )}
              <button type="button" className="c1-btn-primary !px-3 !py-1" disabled={pendingPicked.length === 0 || acceptSelected.isPending} onClick={() => setConfirmSelected(true)} data-testid="accept-selected" title={picked.size > 0 && pendingPicked.length === 0 ? copy.select.acceptNone : undefined}>
                {copy.select.acceptSelected(pendingPicked.length)}
              </button>
              <button type="button" className="c1-btn-primary !px-3 !py-1" disabled={picked.size === 0 || sprintList.length === 0} onClick={() => setMoving(true)} data-testid="move-selected">
                {copy.select.moveTo}
              </button>
            </div>
          )}
          {canBulk && (
            <button type="button" className="c1-btn-primary mt-3" data-testid="bulk-accept" disabled={bulk.isPending} onClick={() => setConfirmBulk(true)}>
              {copy.suggest.bulk(rows.length)}
            </button>
          )}
        </div>

        {list.isError ? (
          <div role="alert" className="m-4 rounded-lg border border-danger-border bg-danger-bg p-3 text-xs text-danger-text">
            {(list.error as Error).message}
          </div>
        ) : list.isLoading || pid === undefined ? (
          <div className="flex flex-col gap-3 p-4" aria-busy="true" aria-label={copy.common.loading}>
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="px-4 py-12 text-center text-xs text-secondary-text" data-testid="empty-list">
            {filtered ? copy.review.noMatch : copy.review.empty}
          </div>
        ) : (
          <>
            <RequirementList
              rows={pageInfo.shown}
              selectedUid={activeUid}
              onSelect={select_}
              label={copy.review.listTitle}
              onOpen={() => headingRef.current?.focus()}
              showSuggestion
              sprintNames={sprintNames}
              selection={selecting ? { picked, toggle } : undefined}
            />
            <Pager total={pageInfo.total} page={pageInfo.page} pages={pageInfo.pages} from={pageInfo.from} to={pageInfo.to} size={size} onPage={setPage} onSize={changeSize} />
          </>
        )}
      </section>
      <div className="min-w-0 border-t border-border xl:border-t-0">
        <RequirementView uid={activeUid} projectId={pid} mode="review" headingRef={headingRef} waiting={list.isFetching && selected === null} />
      </div>
      {confirmBulk && (
        <ConfirmDialog title={copy.suggest.bulkTitle} message={copy.suggest.bulkMessage(rows.length)} confirmLabel={copy.suggest.bulkConfirm} busy={bulk.isPending} onCancel={() => setConfirmBulk(false)} onConfirm={acceptAll} />
      )}
      {confirmSelected && (
        <ConfirmDialog
          title={copy.select.acceptTitle}
          message={copy.select.acceptMessage(pendingPicked.length, picked.size - pendingPicked.length)}
          confirmLabel={copy.select.acceptConfirm}
          busy={acceptSelected.isPending}
          onCancel={() => setConfirmSelected(false)}
          onConfirm={onAcceptSelected}
        />
      )}
      {moving && <MoveRequirementsDialog count={picked.size} sprints={sprintList} busy={assign.isPending} onCancel={() => setMoving(false)} onConfirm={moveSelected} />}
    </div>
  )
}
