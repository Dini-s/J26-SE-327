import { ChevronDown, Download } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { downloadExport } from '../api/client'
import { copy } from '../copy'
import { useToasts } from '../context/Toasts'

/** Export menu: CSV for a spreadsheet, JSON for other tools. */
export function ExportMenu({ projectId, canExport }: { projectId?: number; canExport: boolean }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const toasts = useToasts()

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  const run = async (format: 'csv' | 'json') => {
    if (projectId === undefined) return
    setOpen(false)
    setBusy(true)
    try {
      await downloadExport(projectId, format)
      toasts.push(copy.handoff.exported(format.toUpperCase()), 'success')
    } catch (e) {
      toasts.push(e instanceof Error ? e.message : copy.handoff.exportFailed, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className="c1-btn-secondary !bg-white"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={!canExport || busy}
        title={canExport ? undefined : copy.handoff.exportDisabled}
        onClick={() => setOpen((o) => !o)}
      >
        <Download size={14} aria-hidden="true" />
        {copy.handoff.export}
        <ChevronDown size={13} aria-hidden="true" />
      </button>
      {open && (
        <div role="menu" aria-label={copy.handoff.exportFormat} className="absolute left-0 z-30 mt-1.5 w-48 rounded-lg border border-border bg-white p-1 shadow-lg">
          <button role="menuitem" type="button" className="block w-full rounded-md px-3 py-1.5 text-left text-xs text-heading hover:bg-primary-light" onClick={() => void run('csv')}>
            {copy.handoff.csv}
          </button>
          <button role="menuitem" type="button" className="block w-full rounded-md px-3 py-1.5 text-left text-xs text-heading hover:bg-primary-light" onClick={() => void run('json')}>
            {copy.handoff.json}
          </button>
        </div>
      )}
    </div>
  )
}
