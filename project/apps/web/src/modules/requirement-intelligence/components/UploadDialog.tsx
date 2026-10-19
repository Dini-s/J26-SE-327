import { CloudUpload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useCreateSprint, useUpload } from '../api/hooks'
import type { SourceType, Sprint } from '../api/types'
import { ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES } from '../config'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { Dialog } from './Dialog'
import { FIELD } from './PlanDialogs'
import { Spinner } from './ui'

const NEW = '__new'

interface Props {
  pid: number
  sprints: Sprint[]
  /** The sprint chosen when the dialog opens ("Upload here"); without it the sprint is left to Automatic. */
  sprintId?: number
  onClose: () => void
  /** Called after the files were stored. */
  onUploaded?: () => void
}

/**
 * Add documents: the files (or typed requirements), what kind of document they are, and where they belong.
 * The sprint can be chosen, created on the spot, or left to "Automatic" (the sprint named in the file, else the current sprint).
 */
export function UploadDialog({ pid, sprints, sprintId: initialSprint, onClose, onUploaded }: Props) {
  const toasts = useToasts()
  const upload = useUpload(pid)
  const createSprint = useCreateSprint(pid)
  const input = useRef<HTMLInputElement>(null)
  const [type, setType] = useState<'srs' | 'brd' | 'manual'>('srs')
  const [files, setFiles] = useState<File[]>([])
  const [manual, setManual] = useState('')
  const [sprint, setSprint] = useState(initialSprint !== undefined && sprints.some((s) => s.id === initialSprint) ? String(initialSprint) : '')
  const [sprintName, setSprintName] = useState('')
  const [error, setError] = useState('')
  const busy = upload.isPending || createSprint.isPending

  const choose = (picked: File[]) => {
    const ok: File[] = []
    for (const f of picked) {
      const ext = f.name.includes('.') ? '.' + f.name.split('.').pop()!.toLowerCase() : ''
      if (!(ALLOWED_EXTENSIONS as readonly string[]).includes(ext)) toasts.push(copy.sources.badType(f.name, ext || copy.common.none, ALLOWED_EXTENSIONS.join(', ')), 'error')
      else if (f.size > MAX_UPLOAD_BYTES) toasts.push(copy.sources.tooLarge(f.name, MAX_UPLOAD_BYTES / (1024 * 1024)), 'error')
      else ok.push(f)
    }
    if (ok.length) setFiles((old) => [...old, ...ok])
  }

  const submit = async () => {
    let toSend = files
    if (type === 'manual') {
      if (!manual.trim()) return setError(copy.sources.manualEmpty)
      const stamp = new Date().toISOString().slice(0, 19).replace('T', ' ').replace(/:/g, '-')
      toSend = [new File([`${manual.trim()}\n`], copy.sources.manualName(stamp), { type: 'text/plain' })]
    } else if (toSend.length === 0) {
      return setError(copy.sources.uploadNeedFiles)
    }
    if (sprint === NEW && !sprintName.trim()) return setError(copy.sources.uploadNeedName)
    setError('')
    try {
      let sprintId = sprint && sprint !== NEW ? Number(sprint) : undefined
      if (sprint === NEW) sprintId = (await createSprint.mutateAsync({ name: sprintName.trim() })).id
      const sourceType: SourceType = type === 'manual' ? 'other' : type
      const r = await upload.mutateAsync({ files: toSend, sourceType, sprintId })
      r.rejected.forEach((x) => toasts.push(x.message, 'error'))
      if (r.accepted.length) toasts.push(copy.sources.added(r.accepted.length), 'success')
      if (r.sprint_detected) toasts.push(copy.sources.uploadDetected(r.detected.map((d) => d.name).join(', ')), 'success')
      if (r.accepted.length) {
        onUploaded?.()
        onClose()
      }
    } catch (e) {
      toasts.push(copy.sources.uploadFailed((e as Error).message), 'error')
    }
  }

  return (
    <Dialog
      title={copy.sources.uploadTitle}
      description={copy.sources.uploadIntro}
      onClose={onClose}
      actions={
        <>
          <button type="button" className="c1-btn-secondary" onClick={onClose}>
            {copy.common.cancel}
          </button>
          <button type="button" className="c1-btn-primary" disabled={busy} onClick={() => void submit()} data-testid="upload-submit">
            {busy && <Spinner className="h-3.5 w-3.5" />} {type === 'manual' ? copy.sources.manualAdd : copy.sources.uploadButton}
          </button>
        </>
      }
    >
      <label className="block text-xs text-secondary-text">
        {copy.sources.typeLabel}
        <select value={type} onChange={(e) => setType(e.target.value as 'srs' | 'brd' | 'manual')} data-testid="source-type-select" className={FIELD}>
          <option value="srs">{copy.sources.type.srs}</option>
          <option value="brd">{copy.sources.type.brd}</option>
          <option value="manual">{copy.sources.manual}</option>
          <option value="jira" disabled>
            {copy.sources.jira}
          </option>
        </select>
      </label>

      {type === 'manual' ? (
        <div className="mt-3" data-testid="manual-entry">
          <label htmlFor="manual-text" className="block text-xs text-secondary-text">
            {copy.sources.manualLabel}
          </label>
          <textarea id="manual-text" value={manual} onChange={(e) => setManual(e.target.value)} rows={5} maxLength={200000} placeholder={copy.sources.manualPlaceholder} className={FIELD} />
          <p className="mt-1 text-[11px] text-secondary-text">{copy.sources.manualHint}</p>
        </div>
      ) : (
        <div className="mt-3">
          <span className="block text-xs text-secondary-text">{copy.sources.filesLabel}</span>
          <input
            ref={input}
            type="file"
            multiple
            hidden
            accept={ALLOWED_EXTENSIONS.join(',')}
            aria-label={copy.sources.chooseFiles}
            data-testid="file-input"
            onChange={(e) => {
              const picked = Array.from(e.target.files ?? [])
              e.target.value = ''
              if (picked.length) choose(picked)
            }}
          />
          <div className="mt-1 flex items-center gap-3">
            <button type="button" className="c1-btn-secondary" onClick={() => input.current?.click()}>
              <CloudUpload size={15} aria-hidden="true" /> {copy.sources.chooseMore}
            </button>
            <span className="min-w-0 truncate text-[11.5px] text-secondary-text" data-testid="chosen-files">
              {files.length ? files.map((f) => f.name).join(', ') : copy.sources.noFilesYet}
            </span>
          </div>
        </div>
      )}

      <div className="mt-3">
        <label className="block text-xs text-secondary-text">
          {copy.sources.sprintSelect}
          <select value={sprint} onChange={(e) => setSprint(e.target.value)} className={FIELD} data-testid="upload-sprint">
            <option value="">{copy.sources.sprintAuto}</option>
            {sprints.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
            <option value={NEW}>{copy.sources.sprintNew}</option>
          </select>
        </label>
        {sprint === NEW && (
          <label className="mt-2 block text-xs text-secondary-text">
            {copy.sources.sprintNewName}
            <input value={sprintName} onChange={(e) => setSprintName(e.target.value)} maxLength={80} className={FIELD} />
          </label>
        )}
      </div>
      {sprint === '' && <p className="mt-1.5 text-[11px] text-secondary-text">{copy.sources.sprintAutoHint}</p>}
      {error && (
        <p role="alert" className="mt-2 text-[11px] text-danger-text">
          {error}
        </p>
      )}
    </Dialog>
  )
}
