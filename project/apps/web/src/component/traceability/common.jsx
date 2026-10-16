import { Card as UiCard, EmptyState, MeterBar, PageHeader, Stat } from "./ui";

/** Thin adapters so every C4 page shares the one look defined in ui.jsx. */
export function Card({ title, subtitle, ...props }) {
  return <UiCard title={title} description={subtitle} {...props} />;
}

export function KpiCard({ title, value, hint, tone = "indigo", icon }) {
  return <Stat label={title} value={value} hint={hint} tone={tone === "orange" ? "amber" : tone} icon={icon} loading={value === "-"} />;
}

export function Bar({ value, tone = "indigo", max = 1 }) {
  return <MeterBar value={value} max={max} tone={tone === "orange" ? "amber" : tone} />;
}

export function Empty({ children }) {
  return <EmptyState title={children} />;
}

export function TraceHeader({ title, subtitle, ...props }) {
  return <PageHeader page={title} title={title} description={subtitle} {...props} />;
}
