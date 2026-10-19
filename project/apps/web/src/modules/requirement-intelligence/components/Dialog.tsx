import { X } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'
import { copy } from '../copy'
import { Spinner } from './ui'

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'

interface Props {
  title: string
  onClose: () => void
  children: ReactNode
  /** Footer buttons. */
  actions?: ReactNode
  description?: string
}

/**
 * Modal dialog: focus moves in when it opens and comes back to the opener when it closes, Tab stays inside, Escape closes it.
 * Mount it only while it is open.
 */
export function Dialog({ title, onClose, children, actions, description }: Props) {
  const titleId = useId()
  const descId = useId()
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    const first = box.current?.querySelector<HTMLElement>('[data-autofocus]') ?? box.current?.querySelector<HTMLElement>(FOCUSABLE)
    first?.focus()
    return () => opener?.focus?.()
  }, [])

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      onClose()
      return
    }
    if (e.key !== 'Tab' || !box.current) return
    const items = Array.from(box.current.querySelectorAll<HTMLElement>(FOCUSABLE))
    if (!items.length) return
    const firstItem = items[0]!
    const lastItem = items[items.length - 1]!
    if (e.shiftKey && document.activeElement === firstItem) {
      e.preventDefault()
      lastItem.focus()
    } else if (!e.shiftKey && document.activeElement === lastItem) {
      e.preventDefault()
      firstItem.focus()
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/40 p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={box}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        onKeyDown={onKeyDown}
        className="w-full max-w-md rounded-xl border border-border bg-white p-5 shadow-xl"
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id={titleId} className="text-sm font-semibold text-heading">
            {title}
          </h2>
          <button type="button" aria-label={copy.common.close} onClick={onClose} className="rounded p-1 text-muted hover:bg-secondary-bg hover:text-heading">
            <X size={15} aria-hidden="true" />
          </button>
        </div>
        {description && (
          <p id={descId} className="mt-1.5 text-xs leading-relaxed text-secondary-text">
            {description}
          </p>
        )}
        <div className="mt-3">{children}</div>
        {actions && <div className="mt-4 flex flex-wrap items-center justify-end gap-2">{actions}</div>}
      </div>
    </div>
  )
}

interface ConfirmProps {
  title: string
  message: string
  confirmLabel: string
  busy?: boolean
  danger?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/** Yes / no question in a dialog; the cancel button has the first focus, so Enter never confirms by accident. */
export function ConfirmDialog({ title, message, confirmLabel, busy = false, danger = false, onConfirm, onCancel }: ConfirmProps) {
  return (
    <Dialog
      title={title}
      description={message}
      onClose={onCancel}
      actions={
        <>
          <button type="button" data-autofocus className="c1-btn-secondary" onClick={onCancel}>
            {copy.common.cancel}
          </button>
          <button type="button" className={danger ? 'c1-btn border border-danger-border bg-danger-bg text-danger-text hover:bg-red-100' : 'c1-btn-primary'} disabled={busy} onClick={onConfirm}>
            {busy && <Spinner className="h-3.5 w-3.5" />} {confirmLabel}
          </button>
        </>
      }
    >
      {null}
    </Dialog>
  )
}
