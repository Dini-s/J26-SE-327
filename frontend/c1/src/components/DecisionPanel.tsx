import { Check, History, Pencil, X } from 'lucide-react'
import { useState } from 'react'
import type { DecisionIn, RequirementDetail } from '../api/types'

const WORD: Record<string, string> = { accepted: 'Accepted', edited: 'Edited', rejected: 'Rejected' }

const same = (a: string, b: string) => a.split(/\s+/).filter(Boolean).join(' ') === b.split(/\s+/).filter(Boolean).join(' ')

/** Accept / Edit manually / Reject, an editor for a clarified text, and the decision history. Mount with key={uid} so the editor resets per requirement. */
export function DecisionPanel({ detail: d, pending, onDecide }: { detail: RequirementDetail; pending: boolean; onDecide: (body: DecisionIn) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(d.decision?.edited_text ?? d.original_text)
  const [note, setNote] = useState('')
  const [confirmAccept, setConfirmAccept] = useState(false)
  const [keepUnchanged, setKeepUnchanged] = useState(false)
  const cur = d.decision
  const noteValue = note.trim() ? note.trim() : null
  // the model asked questions and the user has not rewritten the text: accepting is allowed, but ask once
  const asked = d.generation.state === 'needs_clarification' && d.generation.clarification_questions.length > 0 && cur?.decision !== 'edited'
  const unchanged = same(draft, d.original_text)

  return (
    <section className="rounded-card border border-line bg-white p-5" aria-label="Decision" data-testid="decision-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="label-caps">Your decision</div>
          <p className="mt-1 max-w-[560px] text-[12px] leading-snug text-ink-muted" data-testid="decision-help">
            <strong>Accept</strong>: the requirement is fine as written. <strong>Edit manually</strong>: write a clearer version; the original is kept. <strong>Reject</strong>: it is not a usable
            requirement. Accepted and edited requirements are the ones passed on to Component 3.
          </p>
          <p className="mt-1 text-[13px] text-ink" data-testid="decision-status">
            {cur ? (
              <>
                <strong>{WORD[cur.decision]}</strong>
                {cur.note ? <span className="text-ink-body"> · {cur.note}</span> : null}
              </>
            ) : (
              <span className="text-ink-muted">No decision yet</span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-primary !px-3.5 !py-2 !text-[13px]" disabled={pending} onClick={() => (asked ? setConfirmAccept(true) : onDecide({ decision: 'accepted', note: noteValue }))}>
            <Check size={15} aria-hidden="true" /> Accept
          </button>
          <button type="button" className="btn-secondary !px-3.5 !py-2 !text-[13px]" disabled={pending} aria-expanded={editing} onClick={() => setEditing((e) => !e)}>
            <Pencil size={14} aria-hidden="true" /> Edit manually
          </button>
          <button
            type="button"
            className="btn !border !border-risk-highLine !bg-white !px-3.5 !py-2 !text-[13px] !text-risk-highText hover:!bg-risk-highBg"
            disabled={pending}
            onClick={() => onDecide({ decision: 'rejected', note: noteValue })}
          >
            <X size={15} aria-hidden="true" /> Reject
          </button>
        </div>
      </div>

      {confirmAccept && (
        <div role="group" aria-label="Confirm accept" data-testid="accept-confirm" className="mt-3 flex flex-wrap items-center gap-3 rounded-ctl border border-risk-medLine bg-risk-medBg px-3 py-2 text-[13px] text-risk-medText">
          <span className="flex-1">The AI asked for clarification. Accept anyway?</span>
          <button
            type="button"
            className="btn-primary !px-3 !py-1.5 !text-[12.5px]"
            disabled={pending}
            onClick={() => {
              setConfirmAccept(false)
              onDecide({ decision: 'accepted', note: noteValue })
            }}
          >
            Accept anyway
          </button>
          <button type="button" className="btn-secondary !px-3 !py-1.5 !text-[12.5px]" onClick={() => setConfirmAccept(false)}>
            Cancel
          </button>
        </div>
      )}

      <label className="mt-3 block text-[12px] text-ink-muted">
        Note (optional)
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={2000}
          className="mt-1 w-full rounded-ctl border border-line bg-[#f7f8fc] px-3 py-2 text-[13px] text-ink"
          placeholder="Why this decision?"
        />
      </label>

      {editing && (
        <div className="mt-3">
          <label className="block text-[12px] font-medium text-ink">
            Clarified requirement text
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={4}
              maxLength={5000}
              className="mt-1 w-full rounded-ctl border border-line bg-white px-3 py-2 text-[13.5px] text-ink"
            />
          </label>
          <p className="mt-1 text-[11px] text-ink-muted">Your text is saved as an “edited” decision. The original text is kept unchanged.</p>
          {unchanged && (
            <div className="mt-2 rounded-ctl border border-line bg-[#f7f8fc] px-3 py-2 text-[12px] text-ink-body" data-testid="unchanged-note">
              This text is the same as the original, so it would not be an edit. Change it, or tick the box to accept it as it is.
              <label className="mt-1 flex items-center gap-2 font-medium text-ink">
                <input type="checkbox" checked={keepUnchanged} onChange={(e) => setKeepUnchanged(e.target.checked)} />
                Keep the text unchanged (record as Accepted)
              </label>
            </div>
          )}
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className="btn-primary !px-3.5 !py-2 !text-[13px]"
              disabled={pending || !draft.trim() || (unchanged && !keepUnchanged)}
              onClick={() => {
                if (unchanged) onDecide({ decision: 'accepted', note: noteValue })
                else onDecide({ decision: 'edited', edited_text: draft.trim(), note: noteValue })
                setEditing(false)
                setKeepUnchanged(false)
              }}
            >
              {unchanged ? 'Accept unchanged text' : 'Save clarified text'}
            </button>
            <button type="button" className="btn-secondary !px-3.5 !py-2 !text-[13px]" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {cur?.decision === 'edited' && cur.edited_text && (
        <div className="mt-4 rounded-ctl border border-ok-line bg-ok-bg p-3 text-[13.5px] text-ink" data-testid="edited-text">
          <div className="label-caps !text-ok-text">Clarified text</div>
          <p className="mt-1">{cur.edited_text}</p>
          <p className="mt-1 text-[11.5px] text-ink-muted">Press Regenerate on the task draft to write a draft from this text. The original wording stays visible above.</p>
        </div>
      )}

      {d.decision_history.length > 0 && (
        <details className="mt-4" data-testid="decision-history">
          <summary className="flex cursor-pointer items-center gap-1.5 text-[12px] font-medium text-ink-body">
            <History size={14} aria-hidden="true" /> Decision history ({d.decision_history.length})
          </summary>
          <ol className="mt-2 space-y-1.5 text-[12px] text-ink-body">
            {[...d.decision_history].reverse().map((h, i) => (
              <li key={`${h.created_at}-${i}`} className="rounded border border-line px-2.5 py-1.5">
                <strong>{WORD[h.decision]}</strong> · {new Date(h.created_at).toLocaleString()}
                {h.note ? ` · ${h.note}` : ''}
                {h.edited_text ? <span className="block text-ink-muted">“{h.edited_text}”</span> : null}
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}
