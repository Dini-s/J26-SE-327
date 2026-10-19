import { Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import type { RiskLevel } from '../api/types'
import { copy } from '../copy'

const RISK_STYLE: Record<RiskLevel, string> = {
  HIGH: 'bg-danger-bg text-danger-text border-danger-border',
  MEDIUM: 'bg-warning-bg text-warning-text border-warning-border',
  LOW: 'bg-success-bg text-success-text border-success-border',
  NONE: 'bg-secondary-bg text-neutral border-neutral-border',
}

/** HIGH / MEDIUM / LOW / NONE pill. `long` adds the word RISK (detail header). */
export function RiskBadge({ level, long = false }: { level: RiskLevel; long?: boolean }) {
  return (
    <span
      data-testid="risk-badge"
      data-level={level}
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10.5px] font-bold tracking-wide ${RISK_STYLE[level]}`}
    >
      {long ? copy.common.riskLong(level) : copy.common.risk[level]}
    </span>
  )
}

export function Spinner({ className = '', label }: { className?: string; label?: string }) {
  return <Loader2 className={`animate-spin ${className}`} aria-label={label} role={label ? 'img' : undefined} aria-hidden={label ? undefined : true} />
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`c1-skeleton ${className}`} aria-hidden="true" />
}

/** Shown on a requirement when the AI model (not the ambiguity check) answered "needs clarification". */
export function AiClarifyBadge() {
  return (
    <span
      data-testid="ai-clarify-badge"
      title={copy.common.aiAskedHint}
      className="inline-flex items-center rounded-full border border-ai-border bg-white px-2 py-px text-[10px] font-semibold text-ai-primary"
    >
      {copy.common.aiAsked}
    </span>
  )
}

export function Tag({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'ai' | 'ok' }) {
  const t = { neutral: 'bg-secondary-bg text-neutral border-neutral-border', ai: 'bg-white text-ai-primary border-ai-border', ok: 'bg-success-bg text-success-text border-success-border' }[tone]
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10.5px] font-semibold ${t}`}>{children}</span>
}
