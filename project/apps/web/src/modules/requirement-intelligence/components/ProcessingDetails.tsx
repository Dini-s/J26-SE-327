import { Cpu } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Engine, Health } from '../api/types'
import { copy } from '../copy'
import { ENGINE_STATUS_TEXT, engineStatus, targetLabel, type EngineStatusState } from '../lib/engine'
import { EngineSwitch } from './EngineSwitch'

const DOT: Record<EngineStatusState, string> = { ready: 'bg-emerald-500', not_set_up: 'bg-slate-400', unreachable: 'bg-red-500', checking: 'bg-slate-400' }

/** Dispatch this on `window` to open the AI engine panel. */
export const OPEN_ENGINE_EVENT = 'c1:open-engine'

interface Props {
  engine?: Engine
  health?: Health
  /** The service did not answer. */
  offline: boolean
  /** The queue paused itself after repeated cloud failures. */
  cloudPaused: boolean
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 py-1 text-xs">
      <dt className="text-secondary-text">{label}</dt>
      <dd className="min-w-0 truncate text-right font-medium text-heading">{value}</dd>
    </div>
  )
}

/**
 * Compact "AI engine" pill. It opens "Processing details": the On device | Cloud switch, the cloud settings and the technical facts
 * (model, host, mode). Those facts are shown nowhere else in the module.
 */
export function ProcessingDetails({ engine, health, offline, cloudPaused }: Props) {
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)

  // "Open AI engine" buttons elsewhere (the unreachable notice) ask for this panel with an event
  useEffect(() => {
    const ask = () => setOpen(true)
    window.addEventListener(OPEN_ENGINE_EVENT, ask)
    return () => window.removeEventListener(OPEN_ENGINE_EVENT, ask)
  }, [])

  useEffect(() => {
    if (!open) return
    const outside = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (document.querySelector('[data-testid="cloud-popover"]')) return // the cloud settings close first
      setOpen(false)
      trigger.current?.focus()
    }
    document.addEventListener('mousedown', outside)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', outside)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  const status: EngineStatusState = offline ? 'unreachable' : engineStatus(engine, cloudPaused)
  const target = engine?.target ?? health?.generation_target
  const model = engine ? (engine.target === 'cloud' ? engine.cloud.model : engine.device.model) : (health?.model ?? '')
  const where = target ? targetLabel(target, engine?.cloud.host) : copy.common.unknown
  const statusText = offline ? copy.engine.serviceDown : ENGINE_STATUS_TEXT[status]

  return (
    <div className="relative" ref={wrap}>
      <button
        ref={trigger}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={`${copy.engine.pill}: ${statusText}`}
        data-testid="engine-pill"
        data-state={status}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium text-body hover:bg-primary-light"
      >
        <span className={`h-2 w-2 rounded-full ${DOT[status]}`} aria-hidden="true" />
        <Cpu size={13} className="text-secondary-text" aria-hidden="true" />
        <span>{copy.engine.pill}</span>
      </button>
      {open && (
        <div role="dialog" aria-label={copy.engine.detailsTitle} data-testid="processing-details" className="absolute right-0 top-full z-40 mt-1.5 w-[420px] max-w-[92vw] rounded-xl border border-border bg-white p-4 shadow-lg">
          <h2 className="text-sm font-semibold text-heading">{copy.engine.detailsTitle}</h2>
          <p className="mt-0.5 text-xs text-secondary-text">{copy.engine.detailsIntro}</p>
          <div className="mt-3">
            <EngineSwitch engine={engine} />
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs" role="status" data-testid="engine-status" data-state={status}>
            <span className={`h-2 w-2 rounded-full ${DOT[status]}`} aria-hidden="true" />
            <span className="font-medium text-heading">{statusText}</span>
            <span className="text-secondary-text">· {where}</span>
          </div>
          <dl className="mt-2 divide-y divide-border border-t border-border" data-testid="technical-details">
            <Row label={copy.engine.model} value={model || copy.common.unknown} />
            <Row label={copy.engine.host} value={engine?.target === 'cloud' ? (engine.cloud.host ?? copy.common.unknown) : copy.engine.thisDevice} />
            <Row label={copy.engine.mode} value={health?.generation_backend ?? copy.common.unknown} />
            <Row label={copy.engine.modelsLoaded} value={health ? (health.part_a_loaded ? copy.common.yes : copy.common.no) : copy.common.unknown} />
            <Row label={copy.engine.reachable} value={health ? (health.generation_reachable ? copy.common.yes : copy.common.no) : copy.common.unknown} />
          </dl>
          {engine?.target === 'cloud' && <p className="mt-2 text-[11px] text-secondary-text">{copy.engine.cloudNotice}</p>}
        </div>
      )}
    </div>
  )
}
