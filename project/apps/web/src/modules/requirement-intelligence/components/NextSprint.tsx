import { CloudUpload, ArrowRightLeft } from 'lucide-react'
import { useState } from 'react'
import { useSetSourceSprint } from '../api/hooks'
import type { Source, Sprint } from '../api/types'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { Dialog } from './Dialog'
import { Spinner } from './ui'

/** The sprint was just created: offer to add a document to it or to move existing documents into it. */
export function NextSprintCreated({ sprint, canMove, onUpload, onMove, onClose }: { sprint: Sprint; canMove: boolean; onUpload: () => void; onMove: () => void; onClose: () => void }) {
  return (
    <Dialog
      title={copy.nextSprint.createdTitle(sprint.name)}
      description={copy.nextSprint.createdIntro}
      onClose={onClose}
      actions={
        <button type="button" className="c1-btn-secondary" onClick={onClose} data-testid="next-sprint-done">
          {copy.nextSprint.later}
        </button>
      }
    >
      <div className="flex flex-wrap gap-2">
        <button type="button" className="c1-btn-primary" onClick={onUpload} data-testid="next-sprint-upload">
          <CloudUpload size={14} aria-hidden="true" /> {copy.sources.uploadHere}
        </button>
        <button type="button" className="c1-btn-secondary" disabled={!canMove} onClick={onMove} data-testid="next-sprint-move">
          <ArrowRightLeft size={14} aria-hidden="true" /> {copy.nextSprint.moveDocuments}
        </button>
      </div>
    </Dialog>
  )
}

/** Choose documents and move them to the sprint (their default sprint; nothing is analysed again). */
export function MoveDocumentsDialog({ pid, sprint, sources, onClose }: { pid: number; sprint: Sprint; sources: Source[]; onClose: () => void }) {
  const toasts = useToasts()
  const setSprint = useSetSourceSprint(pid)
  const [picked, setPicked] = useState<Set<number>>(new Set())
  const [busy, setBusy] = useState(false)
  const flip = (id: number) =>
    setPicked((old) => {
      const next = new Set(old)
      if (!next.delete(id)) next.add(id)
      return next
    })
  const submit = async () => {
    setBusy(true)
    let done = 0
    try {
      for (const id of picked) {
        await setSprint.mutateAsync({ sourceId: id, sprintId: sprint.id })
        done += 1
      }
      toasts.push(copy.nextSprint.moved(done, sprint.name), 'success')
      onClose()
    } catch (e) {
      toasts.push(copy.sources.moveFailed((e as Error).message), 'error')
      setBusy(false)
    }
  }
  return (
    <Dialog
      title={copy.nextSprint.moveTitle(sprint.name)}
      onClose={onClose}
      actions={
        <>
          <button type="button" className="c1-btn-secondary" onClick={onClose}>
            {copy.common.cancel}
          </button>
          <button type="button" className="c1-btn-primary" disabled={busy || picked.size === 0} onClick={() => void submit()} data-testid="move-documents-confirm">
            {busy && <Spinner className="h-3.5 w-3.5" />} {copy.nextSprint.moveButton(picked.size)}
          </button>
        </>
      }
    >
      <ul className="max-h-64 space-y-1 overflow-y-auto" aria-label={copy.nextSprint.documents} data-testid="move-documents-list">
        {sources.map((s) => (
          <li key={s.id}>
            <label className="flex items-center gap-2 text-xs text-heading">
              <input type="checkbox" checked={picked.has(s.id)} onChange={() => flip(s.id)} /> {s.filename}
            </label>
          </li>
        ))}
      </ul>
    </Dialog>
  )
}
