import { HelpCircle, Info, PenLine, Sparkles } from 'lucide-react'
import type { Ref } from 'react'
import { useDecision, useGenerate, useRequirement } from '../api/hooks'
import { useToasts } from '../context/Toasts'
import type { DecisionIn } from '../api/types'
import { classifierConfidence, percent, sourceLabel } from '../lib/format'
import { DecisionPanel } from './DecisionPanel'
import { DraftCard } from './DraftCard'
import { ExplanationCard } from './ExplanationCard'
import { HighlightLegend, HighlightedText } from './HighlightedText'
import { AiClarifyBadge, RiskBadge, Skeleton } from './ui'

const CONFIDENCE_HELP =
  'Probability the FR/NFR classifier gives to the label it chose. It is a model probability, not a measured accuracy: the model is a baseline and its labels have not been verified for this document.'

/** "Model confidence": the real classifier probability with an explanation tooltip. */
export function ConfidenceChip({ fr_nfr, probability }: { fr_nfr: string; probability: number }) {
  const value = percent(classifierConfidence({ fr_nfr, nfr_probability: probability }))
  return (
    <span className="group relative inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-ai-title" tabIndex={0} aria-describedby="confidence-help" data-testid="confidence">
      <Sparkles size={18} aria-hidden="true" />
      <span>
        Model confidence {value}
        <span className="ml-1 font-normal text-ink-muted">({fr_nfr})</span>
      </span>
      <Info size={13} className="text-ink-faint" aria-hidden="true" />
      <span id="confidence-help" role="tooltip" className="pointer-events-none absolute right-0 top-full z-30 mt-2 hidden w-64 rounded-md bg-ink p-2.5 text-[11.5px] font-normal leading-snug text-white shadow-lg group-hover:block group-focus-visible:block">
        {CONFIDENCE_HELP}
      </span>
    </span>
  )
}

interface Props {
  uid: string | null
  projectId: number | undefined
  headingRef?: Ref<HTMLHeadingElement>
  /** The list is loading and no requirement is chosen yet: show a placeholder instead of the "select" hint. */
  waiting?: boolean
}

export function DetailPanel({ uid, projectId, headingRef, waiting = false }: Props) {
  const q = useRequirement(uid)
  const decision = useDecision(projectId)
  const generate = useGenerate()
  const toasts = useToasts()

  if (!uid && waiting) {
    return (
      <section className="p-6" aria-busy="true" aria-label="Loading requirement">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="mt-6 h-24 w-full" />
        <Skeleton className="mt-4 h-28 w-full" />
      </section>
    )
  }
  if (!uid) {
    return (
      <section className="flex min-h-[320px] items-center justify-center p-8 text-center text-[13.5px] text-ink-muted" aria-label="Requirement analysis">
        Select a requirement to see its analysis.
      </section>
    )
  }
  if (q.isLoading || (q.isFetching && !q.data)) {
    return (
      <section className="p-6" aria-busy="true" aria-label="Loading requirement">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="mt-6 h-24 w-full" />
        <Skeleton className="mt-4 h-28 w-full" />
        <Skeleton className="mt-4 h-40 w-full" />
      </section>
    )
  }
  if (q.isError || !q.data) {
    return (
      <section className="p-6" aria-label="Requirement analysis">
        <div role="alert" className="rounded-ctl border border-risk-highLine bg-risk-highBg p-4 text-[13px] text-risk-highText">
          Could not load this requirement: {q.error?.message ?? 'unknown error'}
          <button type="button" className="ml-3 font-semibold underline" onClick={() => void q.refetch()}>
            Retry
          </button>
        </div>
      </section>
    )
  }

  const d = q.data
  const onDecide = (body: DecisionIn) =>
    decision.mutate(
      { uid: d.uid, body },
      { onError: (e) => toasts.push(`Decision not saved: ${e.message}`, 'error'), onSuccess: () => toasts.push(`${d.id} marked ${body.decision}.`, 'success') },
    )
  const onGenerate = () => generate.mutate(d.uid, { onError: (e) => toasts.push(`Could not start generation: ${e.message}`, 'error') })
  const questions = d.generation.clarification_questions

  return (
    <section className="flex min-w-0 flex-col gap-4 p-5 xl:p-6" aria-label="Requirement analysis" data-testid="detail-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-[14px] font-bold text-brand-600" data-testid="detail-id">
            {d.id}
          </span>
          <RiskBadge level={d.risk.level} long />
          {d.generation.state === 'needs_clarification' && <AiClarifyBadge />}
        </div>
        <ConfidenceChip fr_nfr={d.classification.fr_nfr} probability={d.classification.nfr_probability} />
      </div>
      <h2 ref={headingRef} tabIndex={-1} className="-mt-1 text-[19px] font-medium text-ink outline-none">
        Requirement analysis
      </h2>

      <section className="rounded-card border border-line bg-[#fafbfe] p-5" aria-label="Original requirement">
        <div className="label-caps">Original requirement</div>
        <p className="mt-2.5 text-[15px] leading-relaxed text-ink" data-testid="original-text">
          <HighlightedText text={d.original_text} spans={d.ambiguity.weak_word_spans} vague={d.vague_terms} />
        </p>
        <HighlightLegend text={d.original_text} spans={d.ambiguity.weak_word_spans} vague={d.vague_terms} />
        <p className="mt-2 text-[10.5px] text-ink-faint">{sourceLabel(d.source.file, d.source.page, d.source.paragraph)}</p>
      </section>

      <ExplanationCard detail={d} />

      <section className="rounded-card border border-line bg-white p-5" aria-label="Follow-up questions" data-testid="followup-card">
        <div className="flex items-center gap-2">
          <HelpCircle size={17} className="text-brand-600" aria-hidden="true" />
          <span className="label-caps">Follow-up questions</span>
          {questions.length > 0 && <span className="rounded-full border border-ai-line px-2 py-0.5 text-[10.5px] font-semibold text-ai-title">Model-written</span>}
        </div>
        {questions.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-[13.5px] text-ink">
            {questions.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-[13px] text-ink-muted">
            {d.generation.state === 'done' ? 'The model had no follow-up questions for this requirement.' : 'Follow-up questions appear here when the model asks for clarification.'}
          </p>
        )}
        <p className="mt-2 text-[11px] text-ink-faint">The tool does not write a revised requirement. Use “Edit manually” below to write one.</p>
      </section>

      <DraftCard generation={d.generation} onGenerate={onGenerate} busy={generate.isPending} />

      <DecisionPanel key={d.uid} detail={d} pending={decision.isPending} onDecide={onDecide} />

      <section className="rounded-card border border-info-line bg-info-bg p-4" aria-label="Component boundary">
        <div className="flex items-start gap-3">
          <PenLine size={20} className="mt-0.5 shrink-0 text-brand-600" aria-hidden="true" />
          <div>
            <div className="text-[13.5px] font-semibold text-ink">Component boundary</div>
            <p className="mt-0.5 text-[12px] text-info-text">C1 sends this clarified requirement record to Component 3. Component 3 then creates RVUs and evaluates QA evidence.</p>
          </div>
        </div>
      </section>
    </section>
  )
}
