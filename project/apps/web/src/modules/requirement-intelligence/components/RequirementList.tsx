import { AlertTriangle, FileText, Layers, Lock, ShieldAlert, type LucideIcon } from 'lucide-react'
import type { KeyboardEvent, ReactNode } from 'react'
import type { RequirementRow, SuggestAction } from '../api/types'
import { copy } from '../copy'
import { TYPE_LABEL, primaryType, sourceLabel, type PrimaryType } from '../lib/format'
import { JiraBadge } from './JiraBadge'
import { AiClarifyBadge, RiskBadge } from './ui'

export const TYPE_ICON: Record<PrimaryType, { icon: LucideIcon; tint: string }> = {
  conflict: { icon: ShieldAlert, tint: 'text-red-600' },
  ambiguity: { icon: AlertTriangle, tint: 'text-amber-600' },
  duplicate: { icon: Layers, tint: 'text-violet-600' },
  security: { icon: Lock, tint: 'text-sky-600' },
  none: { icon: FileText, tint: 'text-muted' },
}

const SUGGEST_CHIP: Record<SuggestAction, string> = {
  accept: 'border-success-border bg-success-bg text-success-text',
  edit: 'border-info-border bg-info-bg text-blue-800',
  reject: 'border-danger-border bg-danger-bg text-danger-text',
}

const DECISION_BADGE: Record<string, string> = {
  accepted: 'bg-success-bg text-success-text',
  edited: 'bg-info-bg text-blue-800',
  rejected: 'bg-danger-bg text-danger-text',
}

interface RowProps {
  row: RequirementRow
  selected: boolean
  onSelect: () => void
  /** Extra badges or buttons at the end of the row. */
  extra?: ReactNode
  /** Show the suggested decision on rows that are still pending. */
  showSuggestion?: boolean
  /** Name of the requirement's sprint, shown as a small chip. */
  sprintName?: string
  /** Selection mode: a checkbox in front of the row. */
  checked?: boolean
  onToggle?: () => void
}

export function RequirementRowItem({ row, selected, onSelect, extra, showSuggestion = false, sprintName, checked, onToggle }: RowProps) {
  const kind = primaryType(row.flags)
  const { icon: Icon, tint } = TYPE_ICON[kind]
  return (
    <li
      id={`row-${row.uid}`}
      role="option"
      aria-selected={selected}
      data-testid="finding-row"
      onClick={onSelect}
      className={`flex cursor-pointer items-start gap-3 border-b border-border border-l-[3px] px-4 py-3 transition-colors last:border-b-0 ${
        selected ? 'border-l-primary bg-primary-light' : 'border-l-transparent hover:bg-[#fafbff]'
      }`}
    >
      {onToggle && (
        <input
          type="checkbox"
          className="mt-1 shrink-0"
          checked={!!checked}
          aria-label={copy.select.row(row.id)}
          data-testid="row-check"
          onClick={(e) => e.stopPropagation()}
          onChange={onToggle}
        />
      )}
      <Icon size={20} className={`mt-0.5 shrink-0 ${tint}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-bold text-primary">{row.id}</span>
          <span className="text-secondary-text">{TYPE_LABEL[kind]}</span>
          {row.jira && <JiraBadge jira={row.jira} testid="row-jira" />}
          {sprintName && (
            <span data-testid="row-sprint" className="rounded-full border border-border bg-secondary-bg px-2 py-px text-[10px] text-heading">
              {sprintName}
            </span>
          )}
          {row.generation_state === 'needs_clarification' && <AiClarifyBadge />}
          {row.decision ? (
            <span data-testid="row-decision" className={`rounded px-1.5 py-px text-[10px] font-semibold uppercase ${DECISION_BADGE[row.decision]}`}>
              {copy.decision.word[row.decision]}
            </span>
          ) : showSuggestion ? (
            <span data-testid="row-suggestion" data-action={row.suggestion.action} title={row.suggestion.reasons.join(' ')} className={`rounded-full border px-2 py-px text-[10px] font-semibold ${SUGGEST_CHIP[row.suggestion.action]}`}>
              {copy.suggest.chip(copy.suggest.word[row.suggestion.action])}
            </span>
          ) : null}
        </div>
        <p className="mt-0.5 line-clamp-2 text-[13px] leading-snug text-heading">{row.text}</p>
        <p className="mt-1 truncate text-[10.5px] text-muted">{sourceLabel(row.source_file, row.page, row.paragraph)}</p>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1.5">
        <RiskBadge level={row.risk_level} />
        {extra}
      </div>
    </li>
  )
}

interface ListProps {
  rows: RequirementRow[]
  selectedUid: string | null
  onSelect: (uid: string) => void
  label: string
  /** Enter on the list (move focus to the detail). */
  onOpen?: () => void
  extra?: (row: RequirementRow) => ReactNode
  showSuggestion?: boolean
  sprintNames?: Map<number, string>
  selection?: { picked: Set<string>; toggle: (uid: string) => void }
}

/** Selectable list with the arrow keys; the selected row is `aria-activedescendant`. */
export function RequirementList({ rows, selectedUid, onSelect, label, onOpen, extra, showSuggestion, sprintNames, selection }: ListProps) {
  const move = (delta: number) => {
    if (!rows.length) return
    const i = rows.findIndex((r) => r.uid === selectedUid)
    const next = rows[Math.min(rows.length - 1, Math.max(0, i < 0 ? 0 : i + delta))]!
    onSelect(next.uid)
    document.getElementById(`row-${next.uid}`)?.scrollIntoView?.({ block: 'nearest' })
  }
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      move(1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      move(-1)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      onOpen?.()
    }
  }
  return (
    <ul role="listbox" tabIndex={0} aria-label={label} aria-activedescendant={selectedUid ? `row-${selectedUid}` : undefined} onKeyDown={onKey} className="max-h-[640px] overflow-y-auto focus-visible:outline-offset-[-2px]">
      {rows.map((r) => (
        <RequirementRowItem
          key={r.uid}
          row={r}
          selected={r.uid === selectedUid}
          onSelect={() => onSelect(r.uid)}
          extra={extra?.(r)}
          showSuggestion={showSuggestion}
          sprintName={r.sprint_id !== null ? sprintNames?.get(r.sprint_id) : undefined}
          checked={selection?.picked.has(r.uid)}
          onToggle={selection ? () => selection.toggle(r.uid) : undefined}
        />
      ))}
    </ul>
  )
}
