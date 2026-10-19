import { Check, Lightbulb, Pencil, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import type { DecisionIn, DecisionKind, RequirementDetail } from '../api/types'
import { copy } from '../copy'
import { ConfirmDialog } from './Dialog'
import { Spinner } from './ui'

const same = (a: string, b: string) => a.split(/\s+/).filter(Boolean).join(' ') === b.split(/\s+/).filter(Boolean).join(' ')

const BADGE: Record<DecisionKind, string> = {
  accepted: 'border-success-border bg-success-bg text-success-text',
  edited: 'border-info-border bg-info-bg text-blue-800',
  rejected: 'border-danger-border bg-danger-bg text-danger-text',
}

interface Props {
  detail: RequirementDetail
  /** A save or a removal is in flight. */
  busy: boolean
  /** Resolves true when the service stored the decision (the card then shows the status). */
  onDecide: (body: DecisionIn) => Promise<boolean>
  onRemove: () => Promise<boolean>
}

/**
 * One decision per requirement. Before a decision: Accept / Edit manually / Reject with an optional note. After it: a status card with only
 * "Change decision" and "Remove decision". Mount with key={uid} so the editor resets per requirement.
 */
export function DecisionCard({ detail: d, busy, onDecide, onRemove }: Props) {
  const cur = d.decision
  const [changing, setChanging] = useState(false)
  const [confirmRemove, setConfirmRemove] = useState(false)

  if (cur && !changing) {
    return (
      <section className="rounded-xl border border-border bg-white p-4" aria-label={copy.decision.title} data-testid="decision-card" data-status={cur.decision}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="c1-label">{copy.decision.title}</span>
            <span data-testid="decision-status" className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${BADGE[cur.decision]}`}>
              {copy.decision.word[cur.decision]}
            </span>
            <span className="text-[11px] text-secondary-text" data-testid="decision-date">
              {copy.decision.decidedOn(new Date(cur.updated_at).toLocaleString())}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="c1-btn-secondary" disabled={busy} onClick={() => setChanging(true)}>
              <Pencil size={13} aria-hidden="true" /> {copy.decision.change}
            </button>
            <button type="button" className="c1-btn border border-danger-border bg-white text-danger-text hover:bg-danger-bg" disabled={busy} onClick={() => setConfirmRemove(true)}>
              <Trash2 size={13} aria-hidden="true" /> {copy.decision.remove}
            </button>
          </div>
        </div>
        {cur.note && (
          <p className="mt-2 text-xs text-heading" data-testid="decision-note">
            <span className="text-secondary-text">{copy.decision.noteLabel}: </span>
            {cur.note}
          </p>
        )}
        {cur.decision === 'edited' && cur.edited_text && (
          <div className="mt-3 rounded-lg border border-success-border bg-success-bg p-3 text-xs text-heading" data-testid="edited-text">
            <div className="c1-label !text-success-text">{copy.decision.editedText}</div>
            <p className="mt-1 text-[13px]">{cur.edited_text}</p>
            <p className="mt-1 text-[11px] text-secondary-text">{copy.decision.editedHint}</p>
          </div>
        )}
        {confirmRemove && (
          <ConfirmDialog
            title={copy.decision.removeTitle}
            message={copy.decision.removeMessage}
            confirmLabel={copy.decision.remove}
            danger
            busy={busy}
            onCancel={() => setConfirmRemove(false)}
            onConfirm={async () => {
              const ok = await onRemove()
              if (ok) setConfirmRemove(false)
            }}
          />
        )}
      </section>
    )
  }

  return <DecisionForm detail={d} busy={busy} onDecide={onDecide} onCancel={cur ? () => setChanging(false) : undefined} onDone={() => setChanging(false)} />
}

function DecisionForm({ detail: d, busy, onDecide, onCancel, onDone }: { detail: RequirementDetail; busy: boolean; onDecide: (b: DecisionIn) => Promise<boolean>; onCancel?: () => void; onDone: () => void }) {
  const cur = d.decision
  const [editing, setEditing] = useState(cur?.decision === 'edited')
  const [draft, setDraft] = useState(cur?.edited_text ?? d.original_text)
  const [note, setNote] = useState(cur?.note ?? '')
  const [confirmAccept, setConfirmAccept] = useState<'asked' | 'suggested' | null>(null)
  const [keepUnchanged, setKeepUnchanged] = useState(false)
  const noteValue = note.trim() ? note.trim() : null
  // the model asked questions and the user has not rewritten the text: accepting is allowed, but ask once
  const asked = d.generation.state === 'needs_clarification' && d.generation.clarification_questions.length > 0
  const unchanged = same(draft, d.original_text)
  const hint = d.suggestion

  // "Use this suggestion" only pre-selects: accept asks to confirm, edit opens the box with the original text, reject fills the comment. Nothing is saved.
  const useSuggestion = () => {
    if (hint.action === 'accept') {
      setConfirmAccept('suggested')
    } else if (hint.action === 'edit') {
      setDraft(d.original_text)
      setEditing(true)
    } else {
      setNote(hint.reasons.join(' ').slice(0, 2000))
    }
  }

  const send = async (body: DecisionIn) => {
    if (await onDecide(body)) onDone()
  }

  return (
    <section className="rounded-xl border border-border bg-white p-4" aria-label={copy.decision.title} data-testid="decision-card" data-status="none">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="c1-label">{cur ? copy.decision.changeTitle : copy.decision.title}</div>
          <p className="mt-1 max-w-[560px] text-[11.5px] leading-snug text-secondary-text" data-testid="decision-help">
            {copy.decision.help}
          </p>
          {!cur && (
            <p className="mt-1 text-xs text-secondary-text" data-testid="decision-pending">
              {copy.decision.none}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="c1-btn-primary" disabled={busy} onClick={() => (asked ? setConfirmAccept('asked') : void send({ decision: 'accepted', note: noteValue }))}>
            <Check size={14} aria-hidden="true" /> {copy.decision.accept}
          </button>
          <button type="button" className="c1-btn-secondary" disabled={busy} aria-expanded={editing} onClick={() => setEditing((e) => !e)}>
            <Pencil size={13} aria-hidden="true" /> {copy.decision.edit}
          </button>
          <button
            type="button"
            className="c1-btn border border-danger-border bg-white text-danger-text hover:bg-danger-bg"
            disabled={busy}
            onClick={() => void send({ decision: 'rejected', note: noteValue })}
          >
            <X size={14} aria-hidden="true" /> {copy.decision.reject}
          </button>
          {onCancel && (
            <button type="button" className="c1-btn-secondary" disabled={busy} onClick={onCancel}>
              {copy.common.cancel}
            </button>
          )}
        </div>
      </div>

      <section className="mt-3 rounded-lg border border-ai-border bg-white px-3 py-2.5" aria-label={copy.suggest.panelTitle} data-testid="suggestion-panel" data-action={hint.action}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Lightbulb size={14} className="text-ai-primary" aria-hidden="true" />
            <span className="c1-label">{copy.suggest.panelTitle}</span>
            <span className="text-xs font-semibold text-heading" data-testid="suggestion-action">
              {copy.suggest.chip(copy.suggest.word[hint.action])}
            </span>
          </div>
          <button type="button" className="c1-btn-secondary !px-3 !py-1" disabled={busy} onClick={useSuggestion}>
            {copy.suggest.use}
          </button>
        </div>
        <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-xs text-body" data-testid="suggestion-reasons">
          {hint.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        <p className="mt-1 text-[11px] text-muted">{copy.suggest.panelHint}</p>
      </section>

      {!cur && d.generation.state === 'needs_clarification' && (
        <p className="mt-3 rounded-lg border border-warning-border bg-warning-bg px-3 py-2 text-xs text-warning-text" data-testid="clarify-hint">
          {copy.decision.clarifyHint}
        </p>
      )}

      {confirmAccept && (
        <div role="group" aria-label={copy.decision.confirmAcceptLabel} data-testid="accept-confirm" className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-warning-border bg-warning-bg px-3 py-2 text-xs text-warning-text">
          <span className="flex-1">{confirmAccept === 'suggested' ? copy.decision.confirmSuggested : copy.decision.confirmAccept}</span>
          <button
            type="button"
            className="c1-btn-primary !px-3 !py-1.5"
            disabled={busy}
            onClick={() => {
              setConfirmAccept(null)
              void send({ decision: 'accepted', note: noteValue })
            }}
          >
            {confirmAccept === 'suggested' ? copy.decision.accept : copy.decision.acceptAnyway}
          </button>
          <button type="button" className="c1-btn-secondary !px-3 !py-1.5" onClick={() => setConfirmAccept(null)}>
            {copy.common.cancel}
          </button>
        </div>
      )}

      <label className="mt-3 block text-xs text-secondary-text">
        {copy.decision.noteField}
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={2000}
          className="mt-1 w-full rounded-lg border border-border bg-secondary-bg px-3 py-1.5 text-xs text-heading"
          placeholder={copy.decision.notePlaceholder}
        />
      </label>

      {editing && (
        <div className="mt-3">
          <label className="block text-xs font-medium text-heading">
            {copy.decision.textField}
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={4} maxLength={5000} className="mt-1 w-full rounded-lg border border-border bg-white px-3 py-2 text-[13px] text-heading" />
          </label>
          <p className="mt-1 text-[11px] text-secondary-text">{copy.decision.textHint}</p>
          {unchanged && (
            <div className="mt-2 rounded-lg border border-border bg-secondary-bg px-3 py-2 text-xs text-body" data-testid="unchanged-note">
              {copy.decision.unchanged}
              <label className="mt-1 flex items-center gap-2 font-medium text-heading">
                <input type="checkbox" checked={keepUnchanged} onChange={(e) => setKeepUnchanged(e.target.checked)} />
                {copy.decision.keepUnchanged}
              </label>
            </div>
          )}
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className="c1-btn-primary"
              disabled={busy || !draft.trim() || (unchanged && !keepUnchanged)}
              onClick={() => {
                void send(unchanged ? { decision: 'accepted', note: noteValue } : { decision: 'edited', edited_text: draft.trim(), note: noteValue })
                setKeepUnchanged(false)
              }}
            >
              {busy && <Spinner className="h-3.5 w-3.5" />} {unchanged ? copy.decision.acceptUnchanged : copy.decision.saveAndUpdate}
            </button>
            <button type="button" className="c1-btn-secondary" onClick={() => setEditing(false)}>
              {copy.common.cancel}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
