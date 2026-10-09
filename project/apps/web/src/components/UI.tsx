import type { ReactNode } from "react";

export function MetricCard({
  icon,
  label,
  value,
  detail,
  tone = "blue",
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  detail?: ReactNode;

  tone?: "blue" | "green" | "orange" | "red" | "purple";
}) {
  return (
    <article className="metric-card">
      <div className={`metric-icon ${tone}`}>{icon}</div>

      <div className="metric-copy">
        <span className="metric-label">{label}</span>

        <strong>{value}</strong>

        {detail ? <small>{detail}</small> : null}
      </div>
    </article>
  );
}

export function StatusPill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;

  tone?: "green" | "orange" | "red" | "blue" | "purple" | "neutral";
}) {
  return <span className={`status-pill ${tone}`}>{children}</span>;
}

export function EmptyAnalysis({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="empty-analysis">
      <div className="empty-symbol">—</div>

      <strong>{title}</strong>

      <p>{description}</p>
    </div>
  );
}

export function LoadingPanel({ message = "Loading…" }: { message?: string }) {
  return <section className="surface-card loading-card">{message}</section>;
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <section className="surface-card error-card">
      <strong>Unable to load data</strong>

      <p>{message}</p>

      <small>Confirm FastAPI is running at http://127.0.0.1:8000.</small>
    </section>
  );
}
