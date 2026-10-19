import { useState } from 'react'
import { useCreateSprint, useDeleteSprint, useSetCurrentSprint, useUpdateSprint } from '../api/hooks'
import type { Sprint } from '../api/types'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { Dialog } from './Dialog'
import { Spinner } from './ui'

export const FIELD = 'mt-1 w-full rounded-lg border border-border bg-white px-2.5 py-1.5 text-xs text-heading'

/** Pick the sprint the team works on now (or create one) and make it the current one. */
export function ChangeSprintDialog({ pid, sprints, onClose }: { pid: number; sprints: Sprint[]; onClose: () => void }) {
  const toasts = useToasts()
  const setCurrent = useSetCurrentSprint(pid)
  const create = useCreateSprint(pid)
  const NEW = '__new'
  const [choice, setChoice] = useState<string>(String(sprints.find((s) => s.is_current)?.id ?? sprints[0]?.id ?? NEW))
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const busy = setCurrent.isPending || create.isPending

  const submit = async () => {
    try {
      let id = Number(choice)
      let label = sprints.find((s) => s.id === id)?.name ?? ''
      if (choice === NEW) {
        if (!name.trim()) return setError(copy.plan.nameRequired)
        const created = await create.mutateAsync({ name: name.trim() })
        id = created.id
        label = created.name
      }
      await setCurrent.mutateAsync(id)
      toasts.push(copy.plan.nowCurrent(label), 'success')
      onClose()
    } catch (e) {
      toasts.push(copy.plan.failed((e as Error).message), 'error')
    }
  }
  return (
    <Dialog
      title={copy.plan.changeTitle}
      description={copy.plan.changeIntro}
      onClose={onClose}
      actions={
        <>
          <button type="button" className="c1-btn-secondary" onClick={onClose}>
            {copy.common.cancel}
          </button>
          <button type="button" className="c1-btn-primary" disabled={busy} onClick={() => void submit()}>
            {busy && <Spinner className="h-3.5 w-3.5" />} {copy.plan.setCurrent}
          </button>
        </>
      }
    >
      <label className="block text-xs text-secondary-text">
        {copy.plan.chooseLabel}
        <select value={choice} onChange={(e) => setChoice(e.target.value)} className={FIELD} data-testid="current-sprint-select">
          {sprints.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
              {s.is_current ? ` (${copy.plan.current})` : ''}
            </option>
          ))}
          <option value={NEW}>{copy.plan.createNew}</option>
        </select>
      </label>
      {choice === NEW && (
        <div className="mt-3">
          <label className="block text-xs text-secondary-text">
            {copy.plan.newName}
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} className={FIELD} aria-invalid={!!error} />
          </label>
          {error && (
            <p role="alert" className="mt-1 text-[11px] text-danger-text">
              {error}
            </p>
          )}
        </div>
      )}
    </Dialog>
  )
}

interface SprintDialogProps {
  pid: number
  sprint?: Sprint
  sprints: Sprint[]
  /** The name offered for a new sprint. */
  defaultName?: string
  /** Called with the new sprint instead of closing, so the caller can offer what to do next. */
  onCreated?: (sprint: Sprint) => void
  onClose: () => void
}

/** Create or edit a sprint: name, dates, goal; set it as current; confirm a detected one; delete it (with somewhere to move what it holds). */
export function SprintDialog({ pid, sprint, sprints, defaultName, onCreated, onClose }: SprintDialogProps) {
  const toasts = useToasts()
  const create = useCreateSprint(pid)
  const update = useUpdateSprint(pid)
  const remove = useDeleteSprint(pid)
  const setCurrent = useSetCurrentSprint(pid)
  const [name, setName] = useState(sprint?.name ?? defaultName ?? '')
  const [start, setStart] = useState(sprint?.start_date ?? '')
  const [end, setEnd] = useState(sprint?.end_date ?? '')
  const [goal, setGoal] = useState(sprint?.goal ?? '')
  const [error, setError] = useState('')
  const [deleting, setDeleting] = useState(false)
  const others = sprints.filter((s) => s.id !== sprint?.id)
  const [target, setTarget] = useState<string>(String(others[0]?.id ?? ''))
  const holds = !!sprint && (sprint.requirements > 0 || sprint.documents > 0 || sprint.is_current)
  const busy = create.isPending || update.isPending || remove.isPending || setCurrent.isPending

  const fail = (e: unknown) => toasts.push(copy.plan.saveFailed((e as Error).message), 'error')
  const save = async () => {
    if (!name.trim()) return setError(copy.plan.nameRequired)
    if (start && end && end < start) return setError(copy.plan.datesOrder)
    setError('')
    const body = { name: name.trim(), start_date: start || null, end_date: end || null, goal: goal.trim() || null }
    try {
      const made = sprint ? await update.mutateAsync({ id: sprint.id, ...body }) : await create.mutateAsync(body)
      toasts.push(sprint ? copy.plan.sprintSaved(body.name) : copy.plan.sprintCreated(body.name), 'success')
      if (!sprint && onCreated) onCreated(made as Sprint)
      else onClose()
    } catch (e) {
      fail(e)
    }
  }
  const confirmDelete = async () => {
    try {
      await remove.mutateAsync({ id: sprint!.id, reassignTo: holds ? Number(target) : undefined })
      toasts.push(copy.plan.sprintDeleted(sprint!.name), 'success')
      onClose()
    } catch (e) {
      fail(e)
    }
  }
  const makeCurrent = async () => {
    try {
      await setCurrent.mutateAsync(sprint!.id)
      toasts.push(copy.plan.nowCurrent(sprint!.name), 'success')
      onClose()
    } catch (e) {
      fail(e)
    }
  }
  const confirmDetected = async () => {
    try {
      await update.mutateAsync({ id: sprint!.id, confirmed: true })
      toasts.push(copy.plan.confirmed(sprint!.name), 'success')
      onClose()
    } catch (e) {
      fail(e)
    }
  }

  return (
    <Dialog
      title={sprint ? copy.plan.sprintDialogEdit(sprint.name) : copy.plan.sprintDialogNew}
      onClose={onClose}
      actions={
        <>
          <button type="button" className="c1-btn-secondary" onClick={onClose}>
            {copy.common.cancel}
          </button>
          <button type="button" className="c1-btn-primary" disabled={busy} onClick={() => void save()}>
            {busy && <Spinner className="h-3.5 w-3.5" />} {sprint ? copy.plan.saveSprint : copy.plan.createSprint}
          </button>
        </>
      }
    >
      {sprint && sprint.origin === 'detected' && !sprint.confirmed && (
        <p className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-info-border bg-info-bg px-3 py-2 text-xs text-blue-800" data-testid="detected-note">
          <span className="flex-1">{copy.plan.detected}</span>
          <button type="button" className="c1-btn-secondary !px-2.5 !py-1" disabled={busy} onClick={() => void confirmDetected()}>
            {copy.plan.confirm}
          </button>
        </p>
      )}
      <label className="block text-xs text-secondary-text">
        {copy.plan.nameLabel}
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} className={FIELD} aria-invalid={!!error} />
      </label>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <label className="block text-xs text-secondary-text">
          {copy.plan.startLabel}
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={FIELD} />
        </label>
        <label className="block text-xs text-secondary-text">
          {copy.plan.endLabel}
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={FIELD} />
        </label>
      </div>
      <label className="mt-3 block text-xs text-secondary-text">
        {copy.plan.goalLabel}
        <textarea value={goal} onChange={(e) => setGoal(e.target.value)} rows={2} maxLength={2000} className={FIELD} />
      </label>
      {error && (
        <p role="alert" className="mt-2 text-[11px] text-danger-text">
          {error}
        </p>
      )}
      {sprint && (
        <div className="mt-4 space-y-2 border-t border-border pt-3">
          {!sprint.is_current && (
            <button type="button" className="c1-btn-secondary" disabled={busy} onClick={() => void makeCurrent()}>
              {copy.plan.makeCurrentButton}
            </button>
          )}
          {!deleting ? (
            <div>
              <button type="button" className="text-xs font-medium text-danger-text underline-offset-2 hover:underline disabled:opacity-50" disabled={busy} onClick={() => setDeleting(true)}>
                {copy.plan.deleteSprint}
              </button>
            </div>
          ) : others.length === 0 ? (
            <p className="text-xs text-secondary-text" data-testid="delete-last">
              {copy.plan.deleteLast}
            </p>
          ) : (
            <div className="rounded-lg border border-danger-border bg-danger-bg p-3 text-xs text-danger-text" data-testid="delete-sprint">
              <p className="font-medium">{copy.plan.deleteTitle(sprint.name)}</p>
              {holds ? (
                <label className="mt-2 block">
                  {copy.plan.deleteReassign}
                  <select value={target} onChange={(e) => setTarget(e.target.value)} className={FIELD} data-testid="reassign-select">
                    {others.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <p className="mt-1">{copy.plan.deleteNothing}</p>
              )}
              <div className="mt-2 flex gap-2">
                <button type="button" className="c1-btn border border-danger-border bg-white text-danger-text hover:bg-danger-bg" disabled={busy} onClick={() => void confirmDelete()}>
                  {copy.plan.deleteSprint}
                </button>
                <button type="button" className="c1-btn-secondary" onClick={() => setDeleting(false)}>
                  {copy.common.cancel}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </Dialog>
  )
}
