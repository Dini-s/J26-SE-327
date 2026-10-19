/** The Jira mark (three stacked chevrons), drawn here so no image file is needed. Decorative: the text next to it says "Jira". */
export function JiraIcon({ size = 14, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={`shrink-0 ${className}`} aria-hidden="true" focusable="false" data-testid="jira-icon">
      <path fill="#2684FF" d="M11.53 2c0 2.4 1.97 4.35 4.35 4.35h1.78v1.7c0 2.4 1.94 4.34 4.34 4.35V2.84a.84.84 0 0 0-.84-.84H11.53z" />
      <path fill="#2684FF" opacity=".85" d="M6.77 6.8c0 2.4 1.95 4.34 4.35 4.34h1.78v1.72c0 2.4 1.94 4.34 4.34 4.34V7.64a.84.84 0 0 0-.84-.84H6.77z" />
      <path fill="#2684FF" opacity=".7" d="M2 11.6c0 2.4 1.95 4.34 4.35 4.34h1.78v1.72c0 2.39 1.94 4.34 4.34 4.34v-9.56a.84.84 0 0 0-.84-.84H2z" />
    </svg>
  )
}
