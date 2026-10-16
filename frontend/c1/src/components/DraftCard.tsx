import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Clock, Code2, HelpCircle, RefreshCw, XCircle } from 'lucide-react'
import type { Generation } from '../api/types'
import { GENERATION_LABEL, isGenerating } from '../lib/format'
import { Spinner, Tag } from './ui'

/** The API starts the message of a failed draft with this when the model server could not be reached. */
export const ENGINE_UNAVAILABLE = 'AI engine unavailable'

function provenance(g: Generation): string {
  if (g.backend === 'mock') return 'Test text from the mock backend, not written by a language model.'
  if (g.backend === 'replay') return 'Stored output of an earlier model run (replay), not generated just now.'
  const by = g.model || 'the model'
  const place = g.generated_on === 'cloud' ? ` on cloud${g.endpoint_host ? ` (${g.endpoint_host})` : ''}` : g.generated_on === 'device' ? ' on device' : ''
  return `Written by ${by}${place}`
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-3">
      <div className="label-caps">{title}</div>
      <div className="mt-1 text-[13.5px] leading-relaxed text-ink">{children}</div>
    </div>
  )
}

/** Task draft (user story, technical task, acceptance criteria, rationale) in one of the seven generation states. */
export function DraftCard({ generation: g, onGenerate, busy }: { generation: Generation; onGenerate: () => void; busy: boolean }) {
  const generating = isGenerating(g.state)
  const hasDraft = g.state === 'done'
  const extraNumbers = (g.state === 'done' || g.state === 'needs_clarification') && (g.numbers_not_in_source ?? []).length > 0 ? g.numbers_not_in_source : []
  const fromClarified = (g.state === 'done' || g.state === 'needs_clarification') && g.generated_from === 'clarified'
  const unavailable = g.state === 'failed' && g.message.startsWith(ENGINE_UNAVAILABLE)
  const label = g.state === 'not_requested' ? 'Generate draft' : unavailable ? 'Retry' : 'Regenerate'
  return (
    <section className="rounded-card border border-info-line bg-info-bg/60 p-5" aria-label="Task draft" data-testid="draft-card" data-state={g.state}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Code2 size={17} className="text-info-text" aria-hidden="true" />
          <span className="label-caps !text-info-text">Task draft</span>
          <Tag tone="ai">{GENERATION_LABEL[g.state]}</Tag>
          {fromClarified && (
            <span data-testid="from-clarified" className="rounded-full border border-ok-line bg-ok-bg px-2.5 py-0.5 text-[10.5px] font-semibold text-ok-text">
              Generated from your clarified text
            </span>
          )}
        </div>
        <button type="button" className="btn-secondary !px-3 !py-1.5 !text-[12.5px]" disabled={generating || busy} onClick={onGenerate}>
          {generating || busy ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw size={14} aria-hidden="true" />}
          {label}
        </button>
      </div>

      {extraNumbers.length > 0 && (
        <p className="mt-3 rounded-ctl border border-line bg-white/70 px-3 py-2 text-[12px] text-ink-body" data-testid="numbers-note">
          Contains number(s) not in the source: verify ({extraNumbers.join(', ')})
        </p>
      )}

      {g.state === 'not_requested' && <p className="mt-3 text-[13px] text-ink-body">Not generated yet. Click Generate draft to write one.</p>}

      {g.state === 'queued' && (
        <p className="mt-3 flex items-center gap-2 text-[13px] text-ink-body" role="status">
          <Clock size={15} aria-hidden="true" /> Waiting in the generation queue…
        </p>
      )}

      {g.state === 'running' && (
        <p className="mt-3 flex items-center gap-2 text-[13px] text-ink-body" role="status">
          <Spinner className="h-4 w-4 text-brand-600" /> Generating… The model is writing a draft; this can take tens of seconds. You can keep working.
        </p>
      )}

      {hasDraft && (
        <>
          <Block title="User story">{g.user_story}</Block>
          <Block title="Technical task">{g.technical_task}</Block>
          <Block title="Acceptance criteria">
            <ol className="list-decimal space-y-1 pl-5">
              {g.acceptance_criteria.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ol>
          </Block>
          <Block title="Rationale">{g.rationale}</Block>
          <p className="mt-3 flex items-center gap-1.5 text-[11px] text-ink-muted">
            <CheckCircle2 size={13} aria-hidden="true" /> <span data-testid="provenance">{provenance(g)}</span> · {g.attempts} {g.attempts === 1 ? 'attempt' : 'attempts'}; check it before using it.
          </p>
        </>
      )}

      {g.state === 'needs_clarification' && (
        <div className="mt-3 flex gap-2 rounded-ctl border border-risk-medLine bg-risk-medBg p-3 text-[13px] text-risk-medText" role="status">
          <HelpCircle size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
          <div>
            The model could not write a draft because the requirement needs clarification. See the follow-up questions above.
            {g.rationale && <p className="mt-1 text-[12.5px]">Rationale: {g.rationale}</p>}
          </div>
        </div>
      )}

      {g.state === 'failed' && (
        <div className="mt-3 flex gap-2 rounded-ctl border border-risk-highLine bg-risk-highBg p-3 text-[13px] text-risk-highText" role="alert">
          <XCircle size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
          <div>
            {unavailable ? (
              <>
                <strong>AI engine unavailable.</strong> {g.message.slice(ENGINE_UNAVAILABLE.length).replace(/^:\s*/, '') || 'The model server did not answer.'}
                <p className="mt-1 text-[12.5px]">Part A results above are not affected. Start the model server, then press Retry.</p>
              </>
            ) : (
              <>
                <strong>Generation failed.</strong> {g.message || 'No reason was given.'}
              </>
            )}
          </div>
        </div>
      )}

      {g.state === 'manual_review' && (
        <div className="mt-3 rounded-ctl border border-risk-medLine bg-risk-medBg p-3 text-[13px] text-risk-medText" role="alert">
          <div className="flex gap-2">
            <AlertTriangle size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
            <div>
              <strong>Manual review needed.</strong> The model's reply did not pass the format checks after {g.attempts} attempts, so no draft is shown.
              {g.message && <p className="mt-1 text-[12.5px]">{g.message}</p>}
            </div>
          </div>
          {g.raw_output && (
            <details className="mt-2 text-[12px]">
              <summary className="cursor-pointer font-medium">Last raw reply</summary>
              <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-white/70 p-2">{g.raw_output}</pre>
            </details>
          )}
        </div>
      )}
    </section>
  )
}
