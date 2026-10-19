import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Clock, Code2, HelpCircle, RefreshCw, XCircle } from 'lucide-react'
import type { Generation } from '../api/types'
import { copy } from '../copy'
import { GENERATION_LABEL, isGenerating } from '../lib/format'
import { Spinner, Tag } from './ui'

/** The service starts the message of a failed draft with this when the model server could not be reached. */
export const ENGINE_UNAVAILABLE = 'AI engine unavailable'

/** Where a draft came from, in product words. The model name and host are only shown in Processing details. */
export function provenance(g: Generation): string {
  if (g.backend === 'mock') return copy.drafts.provMock
  if (g.backend === 'replay') return copy.drafts.provReplay
  return g.generated_on === 'cloud' ? copy.drafts.provCloud : g.generated_on === 'device' ? copy.drafts.provDevice : copy.drafts.provAi
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-3">
      <div className="c1-label">{title}</div>
      <div className="mt-1 text-[13px] leading-relaxed text-heading">{children}</div>
    </div>
  )
}

interface Props {
  generation: Generation
  onGenerate: () => void
  busy: boolean
  /** A new draft is being written from the user's edited text. */
  updating?: boolean
  /** The draft asks for clarification and the text is still the original: writing again would give the same result. */
  sameText?: boolean
}

/** Task draft (user story, task, acceptance criteria, rationale) in one of the seven draft states. */
export function DraftCard({ generation: g, onGenerate, busy, updating = false, sameText = false }: Props) {
  const generating = isGenerating(g.state)
  const hasDraft = g.state === 'done'
  const extraNumbers = (g.state === 'done' || g.state === 'needs_clarification') && (g.numbers_not_in_source ?? []).length > 0 ? g.numbers_not_in_source : []
  const fromClarified = (g.state === 'done' || g.state === 'needs_clarification') && g.generated_from === 'clarified'
  const unavailable = g.state === 'failed' && g.message.startsWith(ENGINE_UNAVAILABLE)
  const label = g.state === 'not_requested' ? copy.drafts.generate : unavailable ? copy.common.retry : copy.drafts.regenerate
  return (
    <section className="rounded-xl border border-info-border bg-info-bg/60 p-4" aria-label={copy.drafts.cardLabel} data-testid="draft-card" data-state={g.state}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Code2 size={16} className="text-blue-800" aria-hidden="true" />
          <span className="c1-label !text-blue-800">{copy.drafts.cardLabel}</span>
          <Tag tone="ai">{GENERATION_LABEL[g.state]}</Tag>
          {fromClarified && (
            <span data-testid="from-clarified" className="rounded-full border border-success-border bg-success-bg px-2.5 py-0.5 text-[10.5px] font-semibold text-success-text">
              {copy.drafts.fromClarified}
            </span>
          )}
        </div>
        <button type="button" className="c1-btn-secondary !px-3 !py-1.5" disabled={generating || busy || sameText} onClick={onGenerate}>
          {generating || busy ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw size={13} aria-hidden="true" />}
          {label}
        </button>
      </div>

      {sameText && (
        <p className="mt-3 text-xs text-body" data-testid="same-text-note">
          {copy.drafts.sameTextSameResult}
        </p>
      )}

      {extraNumbers.length > 0 && (
        <p className="mt-3 rounded-lg border border-border bg-white/70 px-3 py-2 text-xs text-body" data-testid="numbers-note">
          {copy.drafts.numbersNote(extraNumbers.join(', '))}
        </p>
      )}

      {g.state === 'not_requested' && <p className="mt-3 text-xs text-body">{copy.drafts.notGenerated}</p>}

      {updating && generating && (
        <p className="mt-3 flex items-center gap-2 text-xs text-body" role="status" data-testid="draft-updating">
          <Spinner className="h-4 w-4 text-primary" /> {copy.drafts.updating}
        </p>
      )}

      {!updating && g.state === 'queued' && (
        <p className="mt-3 flex items-center gap-2 text-xs text-body" role="status">
          <Clock size={14} aria-hidden="true" /> {copy.drafts.queued}
        </p>
      )}

      {!updating && g.state === 'running' && (
        <p className="mt-3 flex items-center gap-2 text-xs text-body" role="status">
          <Spinner className="h-4 w-4 text-primary" /> {copy.drafts.running}
        </p>
      )}

      {hasDraft && (
        <>
          <Block title={copy.drafts.userStory}>{g.user_story}</Block>
          <Block title={copy.drafts.task}>{g.technical_task}</Block>
          <Block title={copy.drafts.criteria}>
            <ol className="list-decimal space-y-1 pl-5">
              {g.acceptance_criteria.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ol>
          </Block>
          <Block title={copy.drafts.rationale}>{g.rationale}</Block>
          <p className="mt-3 flex items-center gap-1.5 text-[11px] text-secondary-text">
            <CheckCircle2 size={13} aria-hidden="true" /> <span data-testid="provenance">{provenance(g)}</span> · {copy.drafts.checkIt}
          </p>
        </>
      )}

      {g.state === 'needs_clarification' && (
        <div className="mt-3 flex gap-2 rounded-lg border border-warning-border bg-warning-bg p-3 text-xs text-warning-text" role="status">
          <HelpCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <div>
            {copy.drafts.needsClarification}
            {g.rationale && <p className="mt-1">{copy.drafts.rationaleLine(g.rationale)}</p>}
          </div>
        </div>
      )}

      {g.state === 'failed' && (
        <div className="mt-3 flex gap-2 rounded-lg border border-danger-border bg-danger-bg p-3 text-xs text-danger-text" role="alert">
          <XCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <div>
            <p className="mb-1 font-medium" data-testid="failure-reason">
              {copy.drafts.reasonLine(copy.drafts.reason[g.failure_reason ?? 'unknown'] ?? copy.drafts.reason.unknown!)}
            </p>
            {unavailable ? (
              <>
                <strong>{copy.drafts.engineUnavailable}</strong> {g.message.slice(ENGINE_UNAVAILABLE.length).replace(/^:\s*/, '') || copy.drafts.serverSilent}
                <p className="mt-1">{copy.drafts.engineUnavailableHint}</p>
              </>
            ) : (
              <>
                <strong>{copy.drafts.failed}</strong> {g.message || copy.drafts.noReason}
              </>
            )}
          </div>
        </div>
      )}

      {g.state === 'manual_review' && (
        <div className="mt-3 rounded-lg border border-warning-border bg-warning-bg p-3 text-xs text-warning-text" role="alert">
          <div className="flex gap-2">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <div>
              <strong>{copy.drafts.manualTitle}</strong> {copy.drafts.manualBody(g.attempts)}
              {g.message && <p className="mt-1">{g.message}</p>}
            </div>
          </div>
          {g.raw_output && (
            <details className="mt-2 text-xs">
              <summary className="cursor-pointer font-medium">{copy.drafts.rawReply}</summary>
              <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-white/70 p-2">{g.raw_output}</pre>
            </details>
          )}
        </div>
      )}
    </section>
  )
}
