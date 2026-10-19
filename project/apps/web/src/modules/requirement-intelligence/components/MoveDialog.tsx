import { Plus, X } from 'lucide-react'
import { useState } from 'react'
import { useAssignRanges, useSetSourceSprint } from '../api/hooks'
import type { Source, Sprint } from '../api/types'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { Dialog } from './Dialog'
import { FIELD } from './PlanDialogs'
import { Spinner } from './ui'

interface Row {
  from: string
  to: string
  sprint: string
}

/** Move a whole document to a sprint, or give page ranges of it to different sprints. Moving never starts an analysis. */
export function MoveDialog({ pid, source, sprints, onClose }: { pid: number; source: Source; sprints: Sprint[]; onClose: () => void }) {
  const toasts = useToasts()
  const setSprint = useSetSourceSprint(pid)
  const assign = useAssignRanges(pid)
  const canRanges = source.pages !== null && source.analysis_state === 'analyzed'
  const [mode, setMode] = useState<'whole' | 'ranges'>('whole')
  const [target, setTarget] = useState<string>(String(source.default_sprint_id ?? sprints[0]?.id ?? ''))
  const [rows, setRows] = useState<Row[]>([{ from: '', to: '', sprint: String(sprints[0]?.id ?? '') }])
  const [error, setError] = useState('')
  const busy = setSprint.isPending || assign.isPending

  const patchRow = (i: number, p: Partial<Row>) => setRows((old) => old.map((r, k) => (k === i ? { ...r, ...p } : r)))

  const submit = async () => {
    try {
      if (mode === 'whole') {
        await setSprint.mutateAsync({ sourceId: source.id, sprintId: Number(target) })
        toasts.push(copy.sources.movedWhole(source.filename, sprints.find((s) => s.id === Number(target))?.name ?? ''), 'success')
      } else {
        const ranges = rows.map((r) => ({ from_page: Number(r.from), to_page: Number(r.to), sprint_id: Number(r.sprint) }))
        if (ranges.some((r) => !Number.isInteger(r.from_page) || !Number.isInteger(r.to_page) || r.from_page < 1 || r.to_page < r.from_page || !r.sprint_id)) return setError(copy.sources.moveInvalid)
        setError('')
        const out = await assign.mutateAsync({ sourceId: source.id, ranges })
        toasts.push(copy.sources.movedRanges(out.assigned, out.without_page), 'success')
      }
      onClose()
    } catch (e) {
      toasts.push(copy.sources.moveFailed((e as Error).message), 'error')
    }
  }

  return (
    <Dialog
      title={copy.sources.moveTitle(source.filename)}
      onClose={onClose}
      actions={
        <>
          <button type="button" className="c1-btn-secondary" onClick={onClose}>
            {copy.common.cancel}
          </button>
          <button type="button" className="c1-btn-primary" disabled={busy || sprints.length === 0} onClick={() => void submit()}>
            {busy && <Spinner className="h-3.5 w-3.5" />} {copy.sources.moveButton}
          </button>
        </>
      }
    >
      <div role="radiogroup" aria-label={copy.sources.moveTitle(source.filename)} className="inline-flex overflow-hidden rounded-lg border border-border">
        {(['whole', 'ranges'] as const).map((m, i) => (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={mode === m}
            disabled={m === 'ranges' && !canRanges}
            onClick={() => setMode(m)}
            className={`px-3 py-1.5 text-xs font-medium ${i > 0 ? 'border-l border-border' : ''} ${mode === m ? 'bg-primary text-white' : 'bg-white text-heading hover:bg-primary-light'} disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {m === 'whole' ? copy.sources.moveWhole : copy.sources.moveRanges}
          </button>
        ))}
      </div>
      {!canRanges && (
        <p className="mt-1.5 text-[11px] text-secondary-text" data-testid="ranges-unavailable">
          {source.pages === null ? copy.sources.moveNoPages : copy.sources.moveNeedsAnalysis}
        </p>
      )}

      {mode === 'whole' ? (
        <label className="mt-3 block text-xs text-secondary-text">
          {copy.sources.moveSprint}
          <select value={target} onChange={(e) => setTarget(e.target.value)} className={FIELD} data-testid="move-sprint">
            {sprints.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <div className="mt-3 space-y-2" data-testid="range-rows">
          {rows.map((r, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_1.4fr_auto] items-end gap-2">
              <label className="text-xs text-secondary-text">
                {copy.sources.moveFrom}
                <input type="number" min={1} max={source.pages ?? undefined} value={r.from} onChange={(e) => patchRow(i, { from: e.target.value })} className={FIELD} />
              </label>
              <label className="text-xs text-secondary-text">
                {copy.sources.moveTo}
                <input type="number" min={1} max={source.pages ?? undefined} value={r.to} onChange={(e) => patchRow(i, { to: e.target.value })} className={FIELD} />
              </label>
              <label className="text-xs text-secondary-text">
                {copy.sources.moveSprint}
                <select value={r.sprint} onChange={(e) => patchRow(i, { sprint: e.target.value })} className={FIELD}>
                  {sprints.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" aria-label={copy.sources.moveRemoveRange} disabled={rows.length === 1} onClick={() => setRows((old) => old.filter((_, k) => k !== i))} className="mb-1 rounded p-1 text-muted hover:bg-secondary-bg disabled:opacity-40">
                <X size={14} aria-hidden="true" />
              </button>
            </div>
          ))}
          <button type="button" className="inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-2 hover:underline" onClick={() => setRows((old) => [...old, { from: '', to: '', sprint: String(sprints[0]?.id ?? '') }])}>
            <Plus size={12} aria-hidden="true" /> {copy.sources.moveAddRange}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 text-[11px] text-danger-text">
          {error}
        </p>
      )}
    </Dialog>
  )
}
