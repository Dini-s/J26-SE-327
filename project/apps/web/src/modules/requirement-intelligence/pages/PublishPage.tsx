import { ChevronDown, ChevronRight, FileText } from 'lucide-react'
import { Fragment, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { usePublishDocuments, useSprints, useSprintSummary, useUnpublishDocuments } from '../api/hooks'
import type { PublishDocsResult, PublishState, SkipReason, SprintDocRow } from '../api/types'
import { Dialog } from '../components/Dialog'
import { FailedDraftsBanner } from '../components/DraftsStatus'
import { JiraIcon } from '../components/JiraIcon'
import { Skeleton, Spinner, Tag } from '../components/ui'
import { useModule } from '../context/ModuleState'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { ownSprints } from '../lib/planning'

const T = copy.publish

/** Why a document cannot be published right now, or null when it can. Mirrors the rules of the service, which has the last word. */
export function skipReason(r: SprintDocRow): SkipReason | null {
  if (r.analysis_state !== 'analyzed') return r.analysis_state === 'analyzing' ? 'analyzing' : r.analysis_state === 'failed' ? 'failed' : 'not_analyzed'
  if (r.requirements === 0) return 'no_requirements'
  return r.publish_state === 'not_published' ? null : 'already_published'
}

interface Ask {
  /** The documents the user chose (the whole sprint = every row). */
  rows: SprintDocRow[]
  whole: boolean
}

const STATE_TAG: Record<PublishState, 'neutral' | 'ai' | 'ok'> = { not_published: 'neutral', published: 'ok', syncing: 'ai', sync_error: 'neutral' }

function StatusCell({ r }: { r: SprintDocRow }) {
  if (r.analysis_state !== 'analyzed') return <Tag>{copy.sources.state[r.analysis_state]}</Tag>
  const text = T.state[r.publish_state]
  return (
    <span className={r.publish_state === 'sync_error' ? 'inline-flex items-center rounded-full border border-warning-border bg-warning-bg px-2.5 py-0.5 text-[10.5px] font-semibold text-warning-text' : undefined} title={r.published_at ?? undefined} data-testid="publish-state" data-state={r.publish_state}>
      {r.publish_state === 'sync_error' ? text : <Tag tone={STATE_TAG[r.publish_state]}>{text}</Tag>}
    </span>
  )
}

function Findings({ r }: { r: SprintDocRow }) {
  const parts = (['ambiguity', 'conflict', 'duplicate', 'security'] as const).filter((k) => r.findings[k] > 0)
  if (parts.length === 0) return <span className="text-muted">{T.noFindings}</span>
  return (
    <span className="flex flex-wrap gap-1">
      {parts.map((k) => (
        <span key={k} className="rounded-full border border-border bg-secondary-bg px-1.5 py-px text-[10.5px] text-heading">
          {T.findings[k]} {r.findings[k]}
        </span>
      ))}
    </span>
  )
}

/** Publish: per sprint, a table of its documents with a summary, and a manual Publish of one document, a selection or the whole sprint. */
export function PublishPage() {
  const { project } = useModule()
  const pid = project?.id
  const toasts = useToasts()
  const sprints = useSprints(pid)
  const sprintList = useMemo(() => ownSprints(sprints.data ?? []), [sprints.data])
  const [chosen, setChosen] = useState<number | null>(null)
  const sprintId = (sprintList.find((s) => s.id === chosen) ?? sprintList.find((s) => s.is_current) ?? sprintList[0])?.id
  const summary = useSprintSummary(pid, sprintId)
  const publish = usePublishDocuments(pid)
  const unpublish = useUnpublishDocuments(pid)
  // the choice belongs to the sprint it was made in: another sprint starts with nothing chosen
  const at = `${pid}:${sprintId}`
  const [choice, setChoice] = useState<{ at: string; ids: Set<number> }>({ at: '', ids: new Set() })
  const picked = choice.at === at ? choice.ids : new Set<number>()
  const setPicked = (ids: Set<number>) => setChoice({ at, ids })
  const [open, setOpen] = useState<Set<number>>(new Set())
  const [ask, setAsk] = useState<Ask | null>(null)
  const data = summary.data
  const rows = useMemo(() => data?.rows ?? [], [data])

  const chosenRows = rows.filter((r) => picked.has(r.document_id))
  const toggle = (set: Set<number>, id: number) => {
    const next = new Set(set)
    if (!next.delete(id)) next.add(id)
    return next
  }

  const report = (r: PublishDocsResult) => {
    const n = r.changed.length
    const word = r.action === 'publish' ? T.done.published(n) : T.done.unpublished(n)
    const skipped = r.skipped.length ? ` ${T.done.skipped(r.skipped.length)}` : ''
    toasts.push(n > 0 ? word + skipped : (r.skipped[0]?.message ?? T.done.nothing), n > 0 ? 'success' : 'info')
    if (n > 0 && r.sync.state === 'retrying') toasts.push(T.done.retrying, 'info')
    if (n > 0 && r.sync.state === 'not_configured') toasts.push(T.done.notConnected, 'info')
  }
  const failed = (e: Error) => toasts.push(T.done.failed(e.message), 'error')
  const plan = ask ? ask.rows.map((r) => ({ r, reason: skipReason(r) })) : []
  const going = plan.filter((p) => !p.reason).map((p) => p.r)
  const skipping = plan.filter((p) => p.reason)
  const confirm = () => {
    if (!ask) return
    const body = ask.whole && sprintId !== undefined ? { sprint_id: sprintId } : { document_ids: going.map((r) => r.document_id) }
    publish.mutate(body, {
      onSuccess: (r) => {
        report(r)
        setAsk(null)
        setPicked(new Set())
      },
      onError: (e) => {
        failed(e)
        setAsk(null)
      },
    })
  }
  const takeBack = (r: SprintDocRow) => unpublish.mutate({ document_ids: [r.document_id] }, { onSuccess: report, onError: failed })


  return (
    <div className="space-y-3">
      <FailedDraftsBanner pid={pid} />

      <section className="c1-card p-4" aria-label={T.title}>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-heading">{T.title}</h2>
            <p className="mt-0.5 max-w-[640px] text-xs text-secondary-text">{T.intro}</p>
          </div>
          <label className="text-xs text-secondary-text">
            {T.sprint}
            <select
              value={sprintId ?? ''}
              onChange={(e) => setChosen(Number(e.target.value))}
              data-testid="publish-sprint"
              className="ml-2 rounded-lg border border-border bg-white px-2 py-1 text-xs text-heading"
              disabled={sprintList.length === 0}
            >
              {sprintList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.is_current ? `${s.name} ${T.current}` : s.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {summary.isError ? (
          <div role="alert" className="mt-3 rounded-lg border border-danger-border bg-danger-bg p-3 text-xs text-danger-text">
            {(summary.error as Error).message}
          </div>
        ) : !data || pid === undefined ? (
          <div className="mt-3 space-y-2" aria-busy="true" aria-label={copy.common.loading}>
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <>
            <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="publish-summary">
              {[
                [T.summary.documents, T.summary.publishedOf(data.published, data.documents), 'documents'],
                [T.summary.requirements, `${data.requirements} · ${T.summary.kinds(data.fr, data.nfr)}`, 'requirements'],
                [T.summary.drafts, T.summary.draftsLine(data.ready, data.needs_clarification, data.failed), 'drafts'],
                [T.summary.decided, T.summary.decidedLine(data.decided), 'decided'],
              ].map(([label, value, key]) => (
                <div key={key} className="rounded-lg border border-border bg-[#fafbfe] px-3 py-2" data-testid={`summary-${key}`}>
                  <dt className="c1-label">{label}</dt>
                  <dd className="mt-0.5 text-xs font-semibold text-heading">{value}</dd>
                </div>
              ))}
            </dl>

            <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
              <button type="button" className="c1-btn-secondary" data-testid="publish-selected" disabled={chosenRows.length === 0} onClick={() => setAsk({ rows: chosenRows, whole: false })}>
                {T.publishSelected(chosenRows.length)}
              </button>
              <button type="button" className="c1-btn-primary" data-testid="publish-whole-sprint" disabled={rows.length === 0} onClick={() => setAsk({ rows, whole: true })}>
                {T.publishSprint}
              </button>
            </div>

            {rows.length === 0 ? (
              <p className="mt-3 rounded-lg border border-border bg-[#fafbfe] px-3 py-6 text-center text-xs text-secondary-text" data-testid="publish-empty">
                {T.empty}
              </p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[860px] border-collapse text-left text-xs" data-testid="publish-table">
                  <thead>
                    <tr className="border-b border-border text-[10.5px] uppercase tracking-wide text-muted">
                      <th className="w-8 py-2 pr-2">
                        <input
                          type="checkbox"
                          aria-label={T.selectAll}
                          checked={picked.size === rows.length}
                          onChange={(e) => setPicked(e.target.checked ? new Set(rows.map((r) => r.document_id)) : new Set())}
                        />
                      </th>
                      <th className="py-2 pr-3 font-semibold">{T.col.document}</th>
                      <th className="py-2 pr-3 font-semibold">{T.col.requirements}</th>
                      <th className="py-2 pr-3 font-semibold">{T.col.kind}</th>
                      <th className="py-2 pr-3 font-semibold">{T.col.drafts}</th>
                      <th className="py-2 pr-3 font-semibold">{T.col.decided}</th>
                      <th className="py-2 pr-3 font-semibold">{T.col.findings}</th>
                      <th className="py-2 pr-3 font-semibold">{T.col.status}</th>
                      <th className="py-2 text-right font-semibold">{T.col.action}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => {
                      const reason = skipReason(r)
                      const isOpen = open.has(r.document_id)
                      const published = r.publish_state !== 'not_published'
                      return (
                        <Fragment key={r.document_id}>
                          <tr className="border-b border-border align-top" data-testid="publish-row" data-doc={r.name} data-state={r.publish_state}>
                            <td className="py-2.5 pr-2">
                              <input type="checkbox" aria-label={T.select(r.name)} checked={picked.has(r.document_id)} onChange={() => setPicked(toggle(picked, r.document_id))} />
                            </td>
                            <td className="py-2.5 pr-3">
                              <button type="button" className="flex items-center gap-1.5 text-left font-medium text-heading hover:text-primary" aria-expanded={isOpen} aria-label={T.details(r.name)} onClick={() => setOpen(toggle(open, r.document_id))}>
                                {isOpen ? <ChevronDown size={13} aria-hidden="true" /> : <ChevronRight size={13} aria-hidden="true" />}
                                {r.source === 'jira' ? <JiraIcon size={14} /> : <FileText size={14} className="shrink-0 text-primary" aria-hidden="true" />}
                                <span className="break-all">{r.name}</span>
                              </button>
                            </td>
                            <td className="py-2.5 pr-3 text-heading">{r.requirements}</td>
                            <td className="py-2.5 pr-3 text-heading" title={r.unclassified ? T.unclassified(r.unclassified) : undefined}>
                              {T.summary.kinds(r.fr, r.nfr)}
                            </td>
                            <td className="py-2.5 pr-3 text-heading">
                              <span title={T.draftsTitle}>{T.draftsCell(r.ready, r.needs_clarification, r.failed)}</span>
                            </td>
                            <td className="py-2.5 pr-3 text-heading">
                              <span aria-label={T.summary.decidedLine(r.decided)}>
                                {T.decidedCell(r.decided)}
                              </span>
                            </td>
                            <td className="py-2.5 pr-3">
                              <Findings r={r} />
                            </td>
                            <td className="py-2.5 pr-3">
                              <StatusCell r={r} />
                            </td>
                            <td className="py-2.5 text-right">
                              {published ? (
                                <button type="button" className="c1-btn-secondary !px-2.5 !py-1" data-testid="row-unpublish" aria-label={T.unpublishRow(r.name)} disabled={unpublish.isPending} onClick={() => takeBack(r)}>
                                  {unpublish.isPending && unpublish.variables?.document_ids?.[0] === r.document_id && <Spinner className="h-3 w-3" />} {T.unpublish}
                                </button>
                              ) : (
                                <button type="button" className="c1-btn-primary !px-2.5 !py-1" data-testid="row-publish" aria-label={T.publishRow(r.name)} disabled={reason !== null} title={reason ? T.reason[reason] : undefined} onClick={() => setAsk({ rows: [r], whole: false })}>
                                  {T.publish}
                                </button>
                              )}
                            </td>
                          </tr>
                          {isOpen && (
                            <tr className="border-b border-border bg-[#fafbfe]" data-testid="publish-detail">
                              <td />
                              <td colSpan={8} className="py-3 pr-3">
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <ul className="space-y-1 text-xs text-heading">
                                    {(['ambiguity', 'conflict', 'duplicate', 'security'] as const).map((k) => (
                                      <li key={k}>
                                        {T.findingsLong[k]}: <strong>{r.findings[k]}</strong>
                                      </li>
                                    ))}
                                    <li className="text-secondary-text">{T.notWritten(r.not_written)}</li>
                                  </ul>
                                  <Link className="c1-btn-secondary !px-3 !py-1.5" to={`/requirement/review?document=${encodeURIComponent(r.name)}`} data-testid="open-in-review">
                                    {T.openInReview}
                                  </Link>
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      {ask && (
        <Dialog
          title={ask.whole ? T.confirm.titleSprint : T.confirm.title(ask.rows.length)}
          description={T.confirm.intro}
          onClose={() => setAsk(null)}
          actions={
            <>
              <button type="button" data-autofocus className="c1-btn-secondary" onClick={() => setAsk(null)}>
                {copy.common.cancel}
              </button>
              <button type="button" className="c1-btn-primary" data-testid="publish-confirm" disabled={going.length === 0 || publish.isPending} onClick={confirm}>
                {publish.isPending && <Spinner className="h-3.5 w-3.5" />} {going.length > 0 ? T.confirm.go(going.length) : T.confirm.nothing}
              </button>
            </>
          }
        >
          <div className="space-y-2 text-xs text-heading" data-testid="publish-plan">
            <p data-testid="plan-documents">{T.confirm.documents(going.length, going.reduce((n, r) => n + r.requirements, 0))}</p>
            {going.reduce((n, r) => n + r.decided.pending, 0) > 0 && <p data-testid="plan-pending">{T.confirm.pending(going.reduce((n, r) => n + r.decided.pending, 0))}</p>}
            {skipping.length > 0 && (
              <div data-testid="plan-skipped">
                <p className="font-medium">{T.confirm.skipped(skipping.length)}</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-secondary-text">
                  {skipping.map((p) => (
                    <li key={p.r.document_id}>
                      {p.r.name}: {T.reason[p.reason!]}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Dialog>
      )}
    </div>
  )
}
