import { HelpCircle, Sparkles } from 'lucide-react'
import { useRef, type Ref } from 'react'
import { useGenerate, useRemoveDecision, useRequirement, useSetDecision } from '../api/hooks'
import type { DecisionIn } from '../api/types'
import { copy } from '../copy'
import { useToasts } from '../context/Toasts'
import { sourceLabel } from '../lib/format'
import { DecisionCard } from './DecisionCard'
import { DraftCard } from './DraftCard'
import { IssueIndicator, RelatedRequirements } from './ExplanationCard'
import { JiraOrigin } from './JiraBadge'
import { HighlightLegend, HighlightedText } from './HighlightedText'
import { AiClarifyBadge, RiskBadge, Skeleton } from './ui'

/** Whether the requirement is functional or non-functional, and nothing more (no score is shown). */
export function KindChip({ fr_nfr }: { fr_nfr: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-ai-border bg-white px-2.5 py-0.5 text-[11px] font-semibold text-ai-primary" data-testid="requirement-kind">
      <Sparkles size={13} aria-hidden="true" />
      {copy.analysis.kind[fr_nfr] ?? fr_nfr}
    </span>
  )
}

interface Props {
  uid: string | null
  projectId: number | undefined
  /** review: analysis, questions, draft and decision. drafts: the requirement, questions and the draft only. */
  mode: 'review' | 'drafts'
  headingRef?: Ref<HTMLHeadingElement>
  /** The list is loading and nothing is chosen yet: show a placeholder instead of the hint. */
  waiting?: boolean
}

export function RequirementView({ uid, projectId, mode, headingRef, waiting = false }: Props) {
  const q = useRequirement(uid)
  const setDecision = useSetDecision(projectId)
  const removeDecision = useRemoveDecision(projectId)
  const generate = useGenerate()
  const toasts = useToasts()
  const draftRef = useRef<HTMLDivElement>(null)

  if (!uid && waiting) {
    return (
      <section className="p-5" aria-busy="true" aria-label={copy.review.loadingOne}>
        <Skeleton className="h-6 w-40" />
        <Skeleton className="mt-5 h-24 w-full" />
        <Skeleton className="mt-4 h-28 w-full" />
      </section>
    )
  }
  if (!uid) {
    return (
      <section className="flex min-h-[260px] items-center justify-center p-8 text-center text-xs text-secondary-text" aria-label={copy.review.detailLabel}>
        {copy.review.selectHint}
      </section>
    )
  }
  if (q.isLoading || (q.isFetching && !q.data)) {
    return (
      <section className="p-5" aria-busy="true" aria-label={copy.review.loadingOne}>
        <Skeleton className="h-6 w-40" />
        <Skeleton className="mt-5 h-24 w-full" />
        <Skeleton className="mt-4 h-28 w-full" />
        <Skeleton className="mt-4 h-40 w-full" />
      </section>
    )
  }
  if (q.isError || !q.data) {
    return (
      <section className="p-5" aria-label={copy.review.detailLabel}>
        <div role="alert" className="rounded-lg border border-danger-border bg-danger-bg p-4 text-xs text-danger-text">
          {copy.review.loadFailed(q.error?.message ?? copy.common.unknown)}
          <button type="button" className="ml-3 font-semibold underline" onClick={() => void q.refetch()}>
            {copy.common.retry}
          </button>
        </div>
      </section>
    )
  }

  const d = q.data
  const onDecide = async (body: DecisionIn): Promise<boolean> => {
    try {
      await setDecision.mutateAsync({ uid: d.uid, body })
      toasts.push(copy.decision.saved(d.id, copy.decision.word[body.decision].toLowerCase()), 'success')
      if (body.decision === 'edited')
        draftRef.current?.scrollIntoView?.({
          block: 'nearest',
          behavior: 'smooth',
        })
      return true
    } catch (e) {
      toasts.push(copy.decision.saveFailed((e as Error).message), 'error')
      return false
    }
  }
  const onRemove = async (): Promise<boolean> => {
    try {
      await removeDecision.mutateAsync(d.uid)
      toasts.push(copy.decision.removed(d.id), 'success')
      return true
    } catch (e) {
      toasts.push(copy.decision.removeFailed((e as Error).message), 'error')
      return false
    }
  }
  const onGenerate = () =>
    generate.mutate(d.uid, {
      onError: (e) => toasts.push(copy.drafts.startFailed(e.message), 'error'),
    })
  const questions = d.generation.clarification_questions
  // the follow-up card appears only for a requirement the AI could not turn into a draft without asking something
  const needsFollowUp = questions.length > 0 || d.generation.state === 'needs_clarification'

  return (
    <section className="flex min-w-0 flex-col gap-3 p-4 xl:p-5" aria-label={copy.review.detailLabel} data-testid="detail-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-sm font-bold text-primary" data-testid="detail-id">
            {d.id}
          </span>
          <RiskBadge level={d.risk.level} long />
          {d.generation.state === 'needs_clarification' && <AiClarifyBadge />}
          {d.jira && <JiraOrigin jira={d.jira} />}
        </div>
        <KindChip fr_nfr={d.classification.fr_nfr} />
      </div>
      <h2 ref={headingRef} tabIndex={-1} className="sr-only">
        {copy.review.detailLabel}
      </h2>

      <section className="relative rounded-xl border border-border bg-[#fafbfe] p-4" aria-label={copy.review.original}>
        {mode === 'review' && d.decision === null && <IssueIndicator detail={d} />} {/* only until the requirement is marked or edited */}
        <div className="c1-label">{copy.review.original}</div>
        <p className="mt-2 pr-10 text-sm leading-relaxed text-heading" data-testid="original-text">
          <HighlightedText text={d.original_text} spans={d.ambiguity.weak_word_spans} vague={d.vague_terms} />
        </p>
        <HighlightLegend text={d.original_text} spans={d.ambiguity.weak_word_spans} vague={d.vague_terms} />
        <p className="mt-2 text-[10.5px] text-muted">{sourceLabel(d.source.file, d.source.page, d.source.paragraph)}</p>
      </section>

      {mode === 'review' && <RelatedRequirements detail={d} />}

      <div ref={draftRef}>
        <DraftCard
          generation={d.generation}
          onGenerate={onGenerate}
          busy={generate.isPending}
          updating={d.decision?.decision === 'edited'}
          sameText={mode === 'review' && d.generation.state === 'needs_clarification' && d.decision?.decision !== 'edited'}
        />
      </div>

      {needsFollowUp && (
        <section className="rounded-xl border border-border bg-white p-4" aria-label={copy.review.questions} data-testid="followup-card">
          <div className="flex items-center gap-2">
            <HelpCircle size={16} className="text-primary" aria-hidden="true" />
            <span className="c1-label">{copy.review.questions}</span>
            {questions.length > 0 && <span className="rounded-full border border-ai-border px-2 py-0.5 text-[10.5px] font-semibold text-ai-primary">{copy.review.aiWritten}</span>}
          </div>
          {questions.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-heading">
              {questions.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs text-secondary-text">{d.generation.state === 'done' ? copy.review.noQuestions : copy.review.questionsLater}</p>
          )}
          {mode === 'review' && <p className="mt-2 text-[11px] text-muted">{copy.review.noRewrite}</p>}
        </section>
      )}

      {mode === 'review' && <DecisionCard key={d.uid} detail={d} busy={setDecision.isPending || removeDecision.isPending} onDecide={onDecide} onRemove={onRemove} />}
    </section>
  )
}
