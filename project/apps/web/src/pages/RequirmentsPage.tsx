import {
  FileText,
  Layers3,
  PieChart,
  Search,
  ShieldCheck,
  Waves,
} from "lucide-react";

import { useEffect, useMemo, useState } from "react";

import { useNavigate } from "react-router-dom";

import {
  ErrorPanel,
  LoadingPanel,
  MetricCard,
  StatusPill,
} from "../components/UI";

import { getOverview, getRequirements } from "../services/qualityApi";

import type { OverviewStats, Requirement } from "../types/quality";

export function RequirementsPage() {
  const navigate = useNavigate();

  const [overview, setOverview] = useState<OverviewStats | null>(null);

  const [requirements, setRequirements] = useState<Requirement[]>([]);

  const [selected, setSelected] = useState<Requirement | null>(null);

  const [query, setQuery] = useState("");

  const [typeFilter, setTypeFilter] = useState("ALL");

  const [riskFilter, setRiskFilter] = useState("ALL");

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);

        const [overviewData, requirementData] = await Promise.all([
          getOverview(),
          getRequirements(),
        ]);

        setOverview(overviewData);

        setRequirements(requirementData);

        setSelected(requirementData[0] ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, []);

  const filtered = useMemo(() => {
    const lowered = query.trim().toLowerCase();

    return requirements.filter((item) => {
      const matchesQuery =
        !lowered ||
        (`${item.requirement_id} ` + `${item.title} ` + item.text)
          .toLowerCase()
          .includes(lowered);

      const matchesType = typeFilter === "ALL" || item.type === typeFilter;

      const matchesRisk = riskFilter === "ALL" || item.risk === riskFilter;

      return matchesQuery && matchesType && matchesRisk;
    });
  }, [query, requirements, riskFilter, typeFilter]);

  if (loading) {
    return <LoadingPanel message="Loading requirements…" />;
  }

  if (error || !overview) {
    return <ErrorPanel message={error ?? "Requirements unavailable."} />;
  }

  return (
    <>
      <div className="page-title-row">
        <div>
          <h1>Requirements</h1>

          <p>
            All requirements analyzed by Quality & Testing Intelligence (C3)
          </p>
        </div>
      </div>

      <section className="metric-grid five">
        <MetricCard
          icon={<FileText size={29} />}
          label="Total Requirements"
          value={overview.requirements}
          tone="purple"
        />

        <MetricCard
          icon={<Layers3 size={29} />}
          label="Total RVUs"
          value={overview.rvus}
          tone="purple"
        />

        <MetricCard
          icon={<ShieldCheck size={29} />}
          label="Adequate RVUs"
          value="—"
          detail="Pending adequacy analysis"
          tone="purple"
        />

        <MetricCard
          icon={<PieChart size={29} />}
          label="Overall RVC"
          value="—"
          detail="Pending validation analysis"
          tone="purple"
        />

        <MetricCard
          icon={<Waves size={29} />}
          label="Avg. Experimental RVES"
          value="—"
          detail="Pending validation analysis"
          tone="purple"
        />
      </section>

      <section className="requirements-workspace">
        <div className="requirements-main">
          <div className="requirements-toolbar">
            <label className="search-box">
              <Search size={18} />

              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search requirements..."
              />
            </label>

            <select
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value)}
            >
              <option value="ALL">Type: All</option>

              <option value="FUNCTIONAL">Functional</option>

              <option value="NON_FUNCTIONAL">Non-Functional</option>
            </select>

            <select
              value={riskFilter}
              onChange={(event) => setRiskFilter(event.target.value)}
            >
              <option value="ALL">Risk: All</option>

              <option value="HIGH">High</option>

              <option value="MEDIUM">Medium</option>

              <option value="LOW">Low</option>
            </select>
          </div>

          <div className="surface-card requirements-table-wrap">
            <table className="data-table requirements-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Requirement</th>
                  <th>Type</th>
                  <th>Risk</th>
                  <th>RVUs</th>
                  <th>Adequate RVUs</th>
                  <th>RVC</th>
                  <th>RVES</th>
                  <th>Status</th>
                  <th>Version</th>
                </tr>
              </thead>

              <tbody>
                {filtered.map((requirement) => (
                  <tr
                    key={requirement.requirement_id}
                    className={
                      selected?.requirement_id === requirement.requirement_id
                        ? "selected-row"
                        : ""
                    }
                    onClick={() => setSelected(requirement)}
                    onDoubleClick={() =>
                      navigate(
                        `/quality/requirements/` + requirement.requirement_id,
                      )
                    }
                  >
                    <td className="link-cell">{requirement.requirement_id}</td>

                    <td>{requirement.title}</td>

                    <td>
                      <StatusPill
                        tone={
                          requirement.type === "FUNCTIONAL" ? "blue" : "purple"
                        }
                      >
                        {requirement.type === "FUNCTIONAL"
                          ? "Functional"
                          : requirement.subtype}
                      </StatusPill>
                    </td>

                    <td>
                      <StatusPill
                        tone={
                          requirement.risk === "HIGH"
                            ? "red"
                            : requirement.risk === "MEDIUM"
                              ? "orange"
                              : "green"
                        }
                      >
                        {requirement.risk}
                      </StatusPill>
                    </td>

                    <td>{requirement.rvu_count ?? 0}</td>

                    {/* These columns stay intentionally empty until adequacy exists. */}
                    <td>—</td>
                    <td>—</td>
                    <td>—</td>

                    <td>
                      <StatusPill tone="neutral">Pending</StatusPill>
                    </td>

                    <td>v{requirement.version}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="table-footer">
              Showing {filtered.length} of {requirements.length} requirements
            </div>
          </div>
        </div>

        <aside className="surface-card selection-summary">
          <div className="selection-title">
            <FileText size={22} />

            <strong>Selection Summary</strong>
          </div>

          {selected ? (
            <>
              <button
                className="selection-id"
                type="button"
                onClick={() =>
                  navigate(`/quality/requirements/` + selected.requirement_id)
                }
              >
                {selected.requirement_id}
              </button>

              <p>{selected.title}</p>

              <div className="selection-rule" />

              <SummaryLine label="RVC" value="—" />

              <SummaryLine label="RVES" value="—" />

              <SummaryLine label="Status" value="Pending" />

              <SummaryLine label="Risk" value={selected.risk} />

              <button
                className="primary-button full"
                type="button"
                onClick={() =>
                  navigate(`/quality/requirements/` + selected.requirement_id)
                }
              >
                Open Requirement
              </button>
            </>
          ) : (
            <p>Select a requirement.</p>
          )}
        </aside>
      </section>
    </>
  );
}

function SummaryLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="summary-line">
      <span>{label}</span>

      <strong>{value}</strong>
    </div>
  );
}
