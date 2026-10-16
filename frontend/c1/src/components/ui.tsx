import { Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import type { RiskLevel } from '../api/types'

const RISK_STYLE: Record<RiskLevel, string> = {
  HIGH: 'bg-risk-highBg text-risk-highText border-risk-highLine',
  MEDIUM: 'bg-risk-medBg text-risk-medText border-risk-medLine',
  LOW: 'bg-risk-lowBg text-risk-lowText border-risk-lowLine',
  NONE: 'bg-risk-noneBg text-risk-noneText border-risk-noneLine',
}

/** HIGH / MEDIUM / LOW / NONE pill. `long` adds the word RISK (detail header). */
export function RiskBadge({ level, long = false }: { level: RiskLevel; long?: boolean }) {
  return (
    <span
      data-testid="risk-badge"
      data-level={level}
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10.5px] font-bold tracking-wide ${RISK_STYLE[level]}`}
    >
      {long ? `${level} RISK` : level}
    </span>
  )
}

export function Spinner({ className = '', label }: { className?: string; label?: string }) {
  return <Loader2 className={`animate-spin ${className}`} aria-label={label} role={label ? 'img' : undefined} aria-hidden={label ? undefined : true} />
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />
}

/** Shown on a requirement when the AI model (not Part A) answered "needs clarification". */
export function AiClarifyBadge() {
  return (
    <span
      data-testid="ai-clarify-badge"
      title="The AI model, not Part A, asked for clarification of this requirement"
      className="inline-flex items-center rounded-full border border-ai-line bg-white px-2 py-px text-[10px] font-semibold text-ai-title"
    >
      AI asked for clarification
    </span>
  )
}

export function Tag({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'ai' | 'ok' }) {
  const t = { neutral: 'bg-risk-noneBg text-risk-noneText border-risk-noneLine', ai: 'bg-white text-ai-title border-ai-line', ok: 'bg-ok-bg text-ok-text border-ok-line' }[tone]
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10.5px] font-semibold ${t}`}>{children}</span>
}
