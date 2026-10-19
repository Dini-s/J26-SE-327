import { useQueryClient } from '@tanstack/react-query'
import { Download, Plug, Unplug } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useJiraConnect, useJiraDisconnect, useJiraStatus } from '../api/hooks'
import { useToasts } from '../context/Toasts'
import { copy } from '../copy'
import { goTo } from '../lib/navigate'
import { ConfirmDialog } from './Dialog'
import { JiraIcon } from './JiraIcon'
import { JiraImportDialog } from './JiraImportDialog'
import { Spinner } from './ui'

/** Back from Jira the browser lands on the module with ?jira=connected or ?jira=error&reason=...: say what happened once and clean the address. */
export function useJiraReturn() {
  const [params, setParams] = useSearchParams()
  const toasts = useToasts()
  const qc = useQueryClient()
  const result = params.get('jira')
  const reason = params.get('reason')
  const handled = useRef('')
  useEffect(() => {
    if (result === null) return
    const mark = `${result}:${reason ?? ''}`
    if (handled.current !== mark) {
      handled.current = mark
      if (result === 'connected') toasts.push(copy.jira.returned.connected, 'success')
      else if (result === 'error') toasts.push(`${copy.jira.returned.error} ${copy.jira.reason[reason ?? ''] ?? ''}`.trim(), 'error')
      void qc.invalidateQueries({ queryKey: ['jira'] })
    }
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        next.delete('jira')
        next.delete('reason')
        return next
      },
      { replace: true },
    )
  }, [result, reason, setParams, toasts, qc])
}

const BTN = 'c1-btn-secondary'

/**
 * The Jira controls of a project in the state it is in: not set up on the server, not connected (Connect Jira: the browser goes to Jira and comes back),
 * connected (the site, Import from Jira, Disconnect) or expired (Reconnect). `card` is the Jira card of the Overview, `row` the connection row of Sources & Findings.
 */
export function JiraActions({ pid, variant }: { pid: number | undefined; variant: 'card' | 'row' }) {
  const toasts = useToasts()
  const status = useJiraStatus(pid)
  const connect = useJiraConnect(pid)
  const disconnect = useJiraDisconnect(pid)
  const [importing, setImporting] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const state = status.data?.state
  const card = variant === 'card'

  const onConnect = () =>
    connect.mutate(undefined, {
      onSuccess: (r) => goTo(r.authorize_url),
      onError: (e) => toasts.push(copy.jira.connectFailed(e.message), 'error'),
    })
  const onDisconnect = () =>
    disconnect.mutate(undefined, {
      onSuccess: () => {
        setConfirming(false)
        toasts.push(copy.jira.disconnected, 'success')
      },
      onError: (e) => {
        setConfirming(false)
        toasts.push(copy.jira.disconnectFailed(e.message), 'error')
      },
    })
  const connectButton = (label: string, primary = false) => (
    <button type="button" className={primary ? 'c1-btn-primary' : BTN} onClick={onConnect} disabled={connect.isPending} data-testid={primary ? 'jira-reconnect' : 'jira-connect'}>
      {connect.isPending ? <Spinner className="h-3.5 w-3.5" /> : <Plug size={14} aria-hidden="true" />} {label}
    </button>
  )
  const note = (text: string, id: string, tone = 'text-secondary-text') => (
    <span className={`text-[11.5px] ${tone}`} data-testid={id} role={id === 'jira-expired' ? 'alert' : undefined}>
      {text}
    </span>
  )

  const shown = state ?? (status.isError ? 'unavailable' : 'loading')
  const chip = (
    <span className="rounded-full border border-border bg-secondary-bg px-2 py-px text-[10.5px] font-semibold text-heading" data-testid="jira-state">
      {copy.jira.stateLabel[shown] ?? shown}
    </span>
  )

  return (
    <section
      className={card ? 'c1-card p-4' : 'c1-card flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5'}
      aria-label={copy.jira.cardTitle}
      data-testid={`jira-${variant}`}
      data-state={shown}
    >
      {card ? (
        <>
          <div className="flex items-center gap-2">
            <JiraIcon size={20} />
            <h2 className="text-sm font-semibold text-heading">{copy.jira.cardTitle}</h2>
            {chip}
          </div>
          <p className="mt-1 text-xs text-secondary-text">{copy.jira.cardIntro}</p>
        </>
      ) : (
        <span className="flex items-center gap-2">
          <JiraIcon size={18} />
          <span className="text-xs font-semibold text-heading">{copy.jira.cardTitle}</span>
          {chip}
        </span>
      )}
      <div className={card ? 'mt-3 flex flex-wrap items-center gap-2' : 'flex flex-wrap items-center gap-2'}>
      {pid === undefined || status.isLoading ? (
        <button type="button" className={BTN} disabled data-testid="jira-connect" aria-disabled="true">
          <Plug size={14} aria-hidden="true" /> {copy.jira.connect}
        </button>
      ) : status.isError || !status.data ? (
        <>
          <button type="button" className={BTN} disabled data-testid="jira-connect" aria-disabled="true">
            <Plug size={14} aria-hidden="true" /> {copy.jira.connect}
          </button>
          {note(copy.jira.unavailable, 'jira-note')}
        </>
      ) : state === 'not_configured' ? (
        <>
          <button type="button" className={BTN} disabled data-testid="jira-connect" aria-disabled="true" title={copy.jira.notConfigured}>
            <Plug size={14} aria-hidden="true" /> {copy.jira.connect}
          </button>
          {note(copy.jira.notConfigured, 'jira-note')}
        </>
      ) : state === 'not_connected' ? (
        connectButton(copy.jira.connect)
      ) : state === 'expired' ? (
        <>
          {note(copy.jira.expired, 'jira-expired', 'text-warning-text')}
          {connectButton(copy.jira.reconnect, true)}
          <button type="button" className="text-xs font-medium text-primary underline-offset-2 hover:underline" onClick={() => setConfirming(true)} data-testid="jira-disconnect">
            {copy.jira.disconnect}
          </button>
        </>
      ) : (
        <>
          <span className="inline-flex items-center gap-1.5 text-[11.5px] font-medium text-heading" data-testid="jira-site">
            <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
            {copy.jira.connectedTo(status.data.site?.name ?? copy.jira.name)}
          </span>
          {status.data.needs_reconnect && note(copy.jira.needsReconnect, 'jira-needs-reconnect', 'text-warning-text')}
          {status.data.needs_reconnect && connectButton(copy.jira.reconnect, true)}
          <button type="button" className="c1-btn-primary" onClick={() => setImporting(true)} data-testid="jira-import">
            <Download size={14} aria-hidden="true" /> {copy.jira.importFrom}
          </button>
          <button type="button" className="inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-2 hover:underline" onClick={() => setConfirming(true)} data-testid="jira-disconnect">
            <Unplug size={12} aria-hidden="true" /> {copy.jira.disconnect}
          </button>
        </>
      )}
      {importing && pid !== undefined && <JiraImportDialog pid={pid} onClose={() => setImporting(false)} />}
      {confirming && (
        <ConfirmDialog title={copy.jira.disconnectTitle} message={copy.jira.disconnectMessage} confirmLabel={copy.jira.disconnectConfirm} danger busy={disconnect.isPending} onCancel={() => setConfirming(false)} onConfirm={onDisconnect} />
      )}
      </div>
    </section>
  )
}
