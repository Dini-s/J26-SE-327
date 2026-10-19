import { AlertTriangle, Check, Clock, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Pipeline } from '../api/types'
import { copy } from '../copy'

type Stage = keyof Pipeline

const LINK: Record<Stage, string> = {
  collect: '/requirement/sources',
  identify: '/requirement/sources',
  analyse: '/requirement/sources',
  improve: '/requirement/review',
  share: '/requirement#knowledge-graph',
}
const ORDER: Stage[] = ['collect', 'identify', 'analyse', 'improve', 'share']

type State = Pipeline['improve']['state']

const LOOK: Record<State, { ring: string; text: string; icon: typeof Check }> = {
  done: { ring: 'border-emerald-500 bg-emerald-500 text-white', text: 'text-emerald-700', icon: Check },
  active: { ring: 'border-primary bg-primary-light text-primary', text: 'text-primary', icon: Loader2 },
  waiting: { ring: 'border-border bg-white text-muted', text: 'text-secondary-text', icon: Clock },
  attention: { ring: 'border-amber-500 bg-amber-50 text-amber-600', text: 'text-amber-700', icon: AlertTriangle },
  failed: { ring: 'border-red-500 bg-red-50 text-red-600', text: 'text-red-700', icon: AlertTriangle },
}

const time = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })

/** Where a stage opens: the failed drafts when some failed, otherwise its usual page. */
export function stageLink(stage: Stage, p: Pipeline): string {
  if (stage === 'improve' && p.improve.drafts.failed > 0 && p.improve.drafts.waiting === 0) return '/requirement/drafts?filter=failed'
  return LINK[stage]
}

/** The one-line live detail of each stage, from the numbers of the overview. */
export function stageDetail(stage: Stage, p: Pipeline): string {
  const t = copy.overview.process
  switch (stage) {
    case 'collect':
      return t.collect(p.collect.documents)
    case 'identify':
      return t.identify(p.identify.requirements)
    case 'analyse':
      return t.analyse(p.analyse.analysed, p.analyse.total, p.analyse.failed)
    case 'improve':
      return t.improve(p.improve.decided, p.improve.requirements, p.improve.drafts_written, p.improve.drafts.waiting, p.improve.drafts.failed)
    case 'share': {
      const label = t.share[p.share.sync_state]
      if (typeof label === 'function') return p.share.last_synced_at ? label(time(p.share.last_synced_at)) : t.syncedNever
      return label ?? p.share.sync_state
    }
  }
}

/** Collect > Identify > Analyse > Improve > Share: where the project stands, one step each with its state and a live detail; each step opens its page. */
export function ProcessStrip({ pipeline }: { pipeline: Pipeline }) {
  return (
    <section className="c1-card p-4" aria-label={copy.overview.process.title} data-testid="process-strip">
      <h2 className="sr-only">{copy.overview.process.title}</h2>
      <ol className="grid grid-cols-1 gap-3 sm:grid-cols-5 sm:gap-0">
        {ORDER.map((stage, i) => {
          const state = pipeline[stage].state
          const look = LOOK[state]
          const Icon = look.icon
          const name = copy.overview.process.stages[stage]
          const detail = stageDetail(stage, pipeline)
          return (
            <li key={stage} className="relative sm:px-2" data-testid="process-stage" data-stage={stage} data-state={state}>
              {i > 0 && <span className="absolute left-0 top-[15px] hidden h-px w-[calc(50%-18px)] bg-border sm:block" aria-hidden="true" />}
              {i < ORDER.length - 1 && <span className="absolute right-0 top-[15px] hidden h-px w-[calc(50%-18px)] bg-border sm:block" aria-hidden="true" />}
              <Link to={stageLink(stage, pipeline)} className="flex items-start gap-3 rounded-lg focus-visible:outline-offset-2 sm:flex-col sm:items-center sm:text-center" aria-label={copy.overview.process.stageLine(name, copy.overview.process.states[state], detail)}>
                <span className={`relative z-10 flex h-[31px] w-[31px] shrink-0 items-center justify-center rounded-full border-2 ${look.ring}`}>
                  <Icon size={15} className={state === 'active' ? 'animate-spin' : undefined} aria-hidden="true" />
                </span>
                <span className="min-w-0">
                  <span className="block text-xs font-semibold text-heading">{name}</span>
                  <span className={`block text-[11px] font-medium ${look.text}`} data-testid="stage-state">
                    {copy.overview.process.states[state]}
                  </span>
                  <span className="mx-auto block max-w-[15rem] text-balance break-words text-[11.5px] text-secondary-text [overflow-wrap:anywhere]" data-testid="stage-detail">
                    {detail}
                  </span>
                </span>
              </Link>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
