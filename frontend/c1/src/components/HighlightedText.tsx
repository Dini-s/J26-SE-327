import type { VagueTerm, WeakWordSpan } from '../api/types'
import { markSegments } from '../lib/format'

const WEAK = 'rounded bg-hit-bg px-1 font-semibold text-hit-text'
const VAGUE = 'rounded border-b-2 border-dotted border-violet-500 bg-violet-50 px-1 font-medium text-violet-800'

/** The requirement text with Part A weak words (solid) and rule-based vague terms (dotted violet) marked; they come from separate API fields. */
export function HighlightedText({ text, spans, vague = [] }: { text: string; spans: WeakWordSpan[]; vague?: VagueTerm[] }) {
  return (
    <>
      {markSegments(text, spans, vague).map((s, i) =>
        s.kind === 'weak' ? (
          <mark key={i} data-kind="weak" className={WEAK} title="Weak word (QuRE list)">
            {s.text}
          </mark>
        ) : s.kind === 'vague' ? (
          <mark key={i} data-kind="vague" className={VAGUE} title="Vague term (rule-based)">
            {s.text}
          </mark>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </>
  )
}

/** Explains the two highlight styles; shows only the styles that appear in the text. */
export function HighlightLegend({ text, spans, vague = [] }: { text: string; spans: WeakWordSpan[]; vague?: VagueTerm[] }) {
  const kinds = new Set(markSegments(text, spans, vague).map((s) => s.kind))
  const weak = kinds.has('weak')
  const isVague = kinds.has('vague')
  if (!weak && !isVague) return null
  return (
    <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10.5px] text-ink-muted" data-testid="highlight-legend">
      {weak && (
        <span className="inline-flex items-center gap-1.5">
          <span className={`${WEAK} !px-1.5 text-[10px]`} aria-hidden="true">
            abc
          </span>
          Weak word (QuRE list)
        </span>
      )}
      {isVague && (
        <span className="inline-flex items-center gap-1.5">
          <span className={`${VAGUE} !px-1.5 text-[10px]`} aria-hidden="true">
            abc
          </span>
          Vague term (rule-based)
        </span>
      )}
    </p>
  )
}
