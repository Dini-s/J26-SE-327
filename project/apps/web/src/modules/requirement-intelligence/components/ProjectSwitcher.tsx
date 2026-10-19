import { Archive, Check, ChevronDown, FolderKanban, Pencil, Plus, RotateCcw, Search } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { useArchiveProject, useCreateProject, useProjects, useRenameProject, useUnarchiveProject } from '../api/hooks'
import type { Project } from '../api/types'
import { copy } from '../copy'
import { useModule } from '../context/ModuleState'
import { useToasts } from '../context/Toasts'
import { ConfirmDialog, Dialog } from './Dialog'
import { Spinner } from './ui'

const NAME_MIN = 2
const NAME_MAX = 80

export function validProjectName(raw: string): string | null {
  const n = raw.trim().replace(/\s+/g, ' ')
  return n.length >= NAME_MIN && n.length <= NAME_MAX ? null : copy.project.nameRule
}

interface NameDialogProps {
  mode: 'new' | 'rename'
  initial: string
  busy: boolean
  serverError: string | null
  onSubmit: (name: string) => void
  onClose: () => void
}

/** Create or rename: one field, checked here (2 to 80 characters) and again by the service (a name already in use comes back as a message). */
function NameDialog({ mode, initial, busy, serverError, onSubmit, onClose }: NameDialogProps) {
  const [name, setName] = useState(initial)
  const [touched, setTouched] = useState(false)
  const problem = validProjectName(name)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (!problem) onSubmit(name.trim().replace(/\s+/g, ' '))
  }
  return (
    <Dialog
      title={mode === 'new' ? copy.project.newTitle : copy.project.renameTitle}
      onClose={onClose}
      actions={
        <>
          <button type="button" className="c1-btn-secondary" onClick={onClose}>
            {copy.common.cancel}
          </button>
          <button type="submit" form="project-name-form" className="c1-btn-primary" disabled={busy}>
            {busy && <Spinner className="h-3.5 w-3.5" />} {mode === 'new' ? copy.project.create : copy.common.save}
          </button>
        </>
      }
    >
      <form id="project-name-form" onSubmit={submit} noValidate>
        <label htmlFor="project-name" className="block text-xs font-medium text-heading">
          {copy.project.nameLabel}
        </label>
        <input
          id="project-name"
          data-autofocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={NAME_MAX + 20}
          autoComplete="off"
          aria-invalid={touched && !!problem}
          aria-describedby="project-name-hint"
          className="mt-1 w-full rounded-lg border border-border bg-white px-2.5 py-1.5 text-xs text-heading"
        />
        <p id="project-name-hint" role={touched && problem ? 'alert' : undefined} className={`mt-1 text-[11px] ${touched && problem ? 'text-danger-text' : 'text-secondary-text'}`}>
          {touched && problem ? problem : copy.project.nameRule}
        </p>
        {serverError && (
          <p role="alert" className="mt-2 rounded-lg border border-danger-border bg-danger-bg px-2.5 py-1.5 text-xs text-danger-text">
            {serverError}
          </p>
        )}
      </form>
    </Dialog>
  )
}

function Menu({ onPick, onNew, onRename, onArchive, onClose }: { onPick: (p: Project) => void; onNew: () => void; onRename: () => void; onArchive: () => void; onClose: () => void }) {
  const { project } = useModule()
  const toasts = useToasts()
  const [showArchived, setShowArchived] = useState(false)
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)
  const list = useProjects(showArchived)
  const unarchive = useUnarchiveProject()
  const search = useRef<HTMLInputElement>(null)
  useEffect(() => search.current?.focus(), [])

  const items = (list.data ?? []).filter((p) => p.name.toLowerCase().includes(q.trim().toLowerCase()))
  const at = Math.min(active, Math.max(0, items.length - 1))
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive(Math.min(items.length - 1, at + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive(Math.max(0, at - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const p = items[at]
      if (p && !p.archived) onPick(p)
    } else if (e.key === 'Escape') {
      e.stopPropagation()
      onClose()
    }
  }

  return (
    <div className="absolute left-0 top-full z-40 mt-1.5 w-[300px] max-w-[92vw] rounded-xl border border-border bg-white p-2 shadow-lg" data-testid="project-menu">
      <label className="relative block">
        <span className="sr-only">{copy.project.search}</span>
        <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" aria-hidden="true" />
        <input
          ref={search}
          type="search"
          role="combobox"
          aria-expanded="true"
          aria-controls="project-options"
          aria-activedescendant={items[at] ? `project-opt-${items[at]!.id}` : undefined}
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setActive(0)
          }}
          onKeyDown={onKey}
          placeholder={copy.project.search}
          className="w-full rounded-lg border border-border bg-secondary-bg py-1.5 pl-8 pr-2 text-xs text-heading"
        />
      </label>
      <ul id="project-options" role="listbox" aria-label={copy.project.listLabel} className="mt-1.5 max-h-56 overflow-y-auto">
        {items.length === 0 && <li className="px-2.5 py-2 text-xs text-secondary-text">{copy.project.none}</li>}
        {items.map((p, i) => (
          <li
            key={p.id}
            id={`project-opt-${p.id}`}
            role="option"
            aria-selected={p.id === project?.id}
            onMouseEnter={() => setActive(i)}
            onClick={() => !p.archived && onPick(p)}
            className={`flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-xs ${i === at ? 'bg-primary-light' : ''} ${p.archived ? 'text-muted' : 'text-heading'}`}
          >
            <span className="min-w-0 flex-1 truncate">{p.name}</span>
            {p.archived ? (
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded border border-border bg-white px-1.5 py-0.5 text-[11px] font-medium text-body hover:bg-secondary-bg"
                onClick={(e) => {
                  e.stopPropagation()
                  unarchive.mutate(p.id, {
                    onSuccess: () => toasts.push(copy.project.restored(p.name), 'success'),
                    onError: (err) => toasts.push(err.message, 'error'),
                  })
                }}
              >
                <RotateCcw size={11} aria-hidden="true" /> {copy.project.restore}
              </button>
            ) : (
              p.id === project?.id && <Check size={13} className="shrink-0 text-primary" aria-hidden="true" />
            )}
          </li>
        ))}
      </ul>
      <label className="mt-1 flex items-center gap-2 px-2.5 py-1 text-[11px] text-secondary-text">
        <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> {copy.project.showArchived}
      </label>
      <div className="mt-1 flex flex-wrap gap-1 border-t border-border pt-2">
        <button type="button" className="c1-btn-secondary !px-2.5 !py-1.5" onClick={onNew}>
          <Plus size={13} aria-hidden="true" /> {copy.project.newButton}
        </button>
        <button type="button" className="c1-btn-secondary !px-2.5 !py-1.5" disabled={!project} onClick={onRename}>
          <Pencil size={13} aria-hidden="true" /> {copy.project.rename}
        </button>
        <button type="button" className="c1-btn-secondary !px-2.5 !py-1.5" disabled={!project} onClick={onArchive}>
          <Archive size={13} aria-hidden="true" /> {copy.project.archive}
        </button>
      </div>
    </div>
  )
}

/** The project dropdown of the module header: search, switch, create, rename and archive. The choice is remembered. */
export function ProjectSwitcher() {
  const { project, selectProject, projectsLoading } = useModule()
  const toasts = useToasts()
  const [open, setOpen] = useState(false)
  const [dialog, setDialog] = useState<'new' | 'rename' | 'archive' | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const create = useCreateProject()
  const rename = useRenameProject()
  const archive = useArchiveProject()

  useEffect(() => {
    if (!open) return
    const outside = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [open])

  const closeMenu = () => {
    setOpen(false)
    trigger.current?.focus()
  }
  const openDialog = (d: 'new' | 'rename' | 'archive') => {
    setServerError(null)
    setOpen(false)
    setDialog(d)
  }

  return (
    <div className="relative" ref={wrap}>
      <button
        ref={trigger}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`${copy.project.label}: ${project?.name ?? copy.project.none}`}
        data-testid="project-trigger"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex max-w-[260px] items-center gap-2 rounded-lg border border-border bg-white px-3 py-1.5 text-xs font-medium text-heading hover:bg-primary-light"
      >
        <FolderKanban size={14} className="shrink-0 text-primary" aria-hidden="true" />
        <span className="truncate">{projectsLoading ? copy.common.loading : (project?.name ?? copy.project.none)}</span>
        <ChevronDown size={13} className="shrink-0 text-secondary-text" aria-hidden="true" />
      </button>
      {open && (
        <Menu
          onPick={(p) => {
            selectProject(p.id)
            closeMenu()
          }}
          onNew={() => openDialog('new')}
          onRename={() => openDialog('rename')}
          onArchive={() => openDialog('archive')}
          onClose={closeMenu}
        />
      )}
      {dialog === 'new' && (
        <NameDialog
          mode="new"
          initial=""
          busy={create.isPending}
          serverError={serverError}
          onClose={() => setDialog(null)}
          onSubmit={(name) =>
            create.mutate(name, {
              onSuccess: (p) => {
                selectProject(p.id)
                setDialog(null)
                toasts.push(copy.project.created(p.name), 'success')
              },
              onError: (e) => setServerError(e.message),
            })
          }
        />
      )}
      {dialog === 'rename' && project && (
        <NameDialog
          mode="rename"
          initial={project.name}
          busy={rename.isPending}
          serverError={serverError}
          onClose={() => setDialog(null)}
          onSubmit={(name) =>
            rename.mutate(
              { pid: project.id, name },
              {
                onSuccess: () => {
                  setDialog(null)
                  toasts.push(copy.project.renamed(name), 'success')
                },
                onError: (e) => setServerError(e.message),
              },
            )
          }
        />
      )}
      {dialog === 'archive' && project && (
        <ConfirmDialog
          title={copy.project.archiveTitle(project.name)}
          message={copy.project.archiveMessage}
          confirmLabel={copy.project.archive}
          busy={archive.isPending}
          onCancel={() => setDialog(null)}
          onConfirm={() =>
            archive.mutate(project.id, {
              onSuccess: () => {
                setDialog(null)
                toasts.push(copy.project.archived(project.name), 'success')
              },
              onError: (e) => {
                setDialog(null)
                toasts.push(e.message, 'error')
              },
            })
          }
        />
      )}
    </div>
  )
}
