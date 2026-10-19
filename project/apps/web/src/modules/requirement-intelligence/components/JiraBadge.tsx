import { ExternalLink } from 'lucide-react'
import type { JiraRef } from '../api/types'
import { copy } from '../copy'
import { JiraIcon } from './JiraIcon'

/** The Jira icon and the issue key ("ABC-12"): the requirement was imported from that issue. */
export function JiraBadge({ jira, testid = 'jira-badge' }: { jira: JiraRef; testid?: string }) {
  return (
    <span
      data-testid={testid}
      title={copy.jira.statusLine(jira.type, jira.status) || undefined}
      aria-label={copy.jira.badgeLabel(jira.key)}
      className="inline-flex items-center gap-1 rounded-full border border-info-border bg-info-bg px-2 py-px text-[10px] font-semibold text-blue-800"
    >
      <JiraIcon size={11} />
      {jira.key}
    </span>
  )
}

/** The badge, the type and status of the issue, and a link to it in Jira (only when the address is known). */
export function JiraOrigin({ jira }: { jira: JiraRef }) {
  const line = copy.jira.statusLine(jira.type, jira.status)
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1" data-testid="detail-jira">
      <JiraBadge jira={jira} testid="detail-jira-badge" />
      {line && (
        <span className="text-[11px] text-secondary-text" data-testid="detail-jira-status">
          {line}
        </span>
      )}
      {jira.url && (
        <a href={jira.url} target="_blank" rel="noopener noreferrer" aria-label={copy.jira.openInJiraLabel(jira.key)} className="inline-flex items-center gap-1 text-[11px] font-medium text-primary underline-offset-2 hover:underline">
          {copy.jira.openInJira} <ExternalLink size={11} aria-hidden="true" />
        </a>
      )}
    </span>
  )
}
