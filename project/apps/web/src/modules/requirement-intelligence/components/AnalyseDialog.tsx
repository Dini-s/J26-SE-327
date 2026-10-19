import { useState } from 'react'
import type { Policy } from '../api/types'
import { copy } from '../copy'
import { Dialog } from './Dialog'
import { Sparkles } from 'lucide-react'

const POLICIES: Policy[] = ['smart', 'all', 'manual']

interface Props {
  /** Names of the documents that will be analysed. */
  names: string[]
  /** True when a document is analysed again (its decisions are kept where the text did not change). */
  again: boolean
  /** The remembered choice. */
  policy: Policy
  onCancel: () => void
  onConfirm: (policy: Policy) => void
}

/** Asked before every analysis: which task drafts to write afterwards. The choice is remembered for the next time. */
export function AnalyseDialog({ names, again, policy, onCancel, onConfirm }: Props) {
  const [choice, setChoice] = useState<Policy>(policy)
  const title = names.length === 1 ? (again ? copy.sources.reanalyseTitle(names[0]!) : copy.sources.analyseTitle(names[0]!)) : copy.sources.analyseManyTitle(names.length)
  return (
    <Dialog
      title={title}
      description={again ? copy.sources.reanalyseMessage : undefined}
      onClose={onCancel}
      actions={
        <>
          <button type="button" className="c1-btn-secondary" onClick={onCancel}>
            {copy.common.cancel}
          </button>
          <button type="button" className="c1-btn-primary" onClick={() => onConfirm(choice)} data-testid="analyse-confirm">
            <Sparkles size={14} aria-hidden="true" /> {copy.sources.analyseConfirm}
          </button>
        </>
      }
    >
      <fieldset data-testid="analyse-policy">
        <legend className="text-xs font-medium text-heading">{copy.sources.draftsQuestion}</legend>
        <div className="mt-2 space-y-2">
          {POLICIES.map((p) => (
            <label key={p} className={`flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 text-xs ${choice === p ? 'border-primary bg-primary-light' : 'border-border bg-white'}`}>
              <input type="radio" name="draft-policy" className="mt-0.5" checked={choice === p} onChange={() => setChoice(p)} data-testid={`policy-${p}`} />
              <span>
                <span className="block font-medium text-heading">{copy.drafts.policy[p].label}</span>
                <span className="block text-secondary-text">{copy.drafts.policy[p].help}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
    </Dialog>
  )
}
