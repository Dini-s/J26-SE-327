import { ChevronDown, Download } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Health } from '../api/types'
import { downloadExport } from '../api/client'
import { useToasts } from '../context/Toasts'
import { ENGINE_TEXT, engineState, type EngineState } from '../lib/format'

const DOT: Record<EngineState, string> = { checking: 'bg-slate-400', ready: 'bg-emerald-500', offline: 'bg-amber-500', error: 'bg-red-500' }

export function StatusPill({ health, unreachable }: { health?: Health; unreachable: boolean }) {
  const state = engineState(health, unreachable)
  return (
    <div role="status" data-state={state} className="flex items-center gap-2 rounded-full border border-line bg-white px-3.5 py-1.5 text-[12.5px] font-medium text-ink-body">
      <span className={`h-2 w-2 rounded-full ${DOT[state]}`} aria-hidden="true" />
      {ENGINE_TEXT[state]}
      {health && health.generation_backend !== 'ollama' && (
        <span data-testid="engine-mode" className="rounded bg-amber-100 px-1.5 text-[11px] font-semibold text-amber-800">
          {health.generation_backend}
        </span>
      )}
    </div>
  )
}

export function Header({ health, unreachable, projectId, canExport }: { health?: Health; unreachable: boolean; projectId?: number; canExport: boolean }) {
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
      toasts.push(`Exported the analysis as ${format.toUpperCase()}.`, 'success')
    } catch (e) {
      toasts.push(e instanceof Error ? e.message : 'Export failed.', 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <header className="flex items-center justify-between gap-4 border-b border-line bg-white px-6 py-3.5 xl:px-9">
      <nav aria-label="Breadcrumb" className="min-w-0 truncate text-[13.5px]">
        <span className="text-ink-muted">USI Framework</span>
        <span className="mx-2 text-ink-faint">/</span>
        <span className="font-semibold text-ink">Requirement Intelligence</span>
      </nav>
      <div className="flex items-center gap-3">
        <StatusPill health={health} unreachable={unreachable} />
        <div className="relative" ref={ref}>
          <button
            type="button"
            className="btn-secondary !bg-white !py-2"
            aria-haspopup="menu"
            aria-expanded={open}
            disabled={!canExport || busy}
            title={canExport ? undefined : 'Run an analysis first'}
            onClick={() => setOpen((o) => !o)}
          >
            <Download size={17} />
            Export analysis
            <ChevronDown size={15} />
          </button>
          {open && (
            <div role="menu" aria-label="Export format" className="absolute right-0 z-30 mt-2 w-44 rounded-ctl border border-line bg-white p-1 shadow-card">
              <button role="menuitem" type="button" className="block w-full rounded-md px-3 py-2 text-left text-[13px] text-ink hover:bg-brand-50" onClick={() => void run('csv')}>
                CSV (spreadsheet)
              </button>
              <button role="menuitem" type="button" className="block w-full rounded-md px-3 py-2 text-left text-[13px] text-ink hover:bg-brand-50" onClick={() => void run('json')}>
                JSON (for Component 3)
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
