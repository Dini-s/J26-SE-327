
import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  BrainCircuit,
  CheckCircle2,
  Code2,
  Database,
  FileCode2,
  GitBranch,
  Layers3,
  LoaderCircle,
  Network,
  Package,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import { useRepository } from "../../../context/RepositoryContext";

const FEATURE_GROUPS = [
  {
    key: "semantic",
    label: "Semantic Intelligence",
    technology: "GraphCodeBERT",
    description: "Code semantics and representations",
    icon: BrainCircuit,
  },
  {
    key: "evolution",
    label: "Evolution Intelligence",
    technology: "Repository History",
    description: "Commit and change metrics",
    icon: Activity,
  },
  {
    key: "structural",
    label: "Structural Intelligence",
    technology: "Architecture Metrics",
    description: "Package-level characteristics",
    icon: Layers3,
  },
  {
    key: "graph",
    label: "Dependency Intelligence",
    technology: "Dependency Graph",
    description: "Package relationships",
    icon: GitBranch,
  },
];

const formatNumber = (value) => {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    !Number.isFinite(Number(value))
  ) {
    return "—";
  }

  return Number(value).toLocaleString();
};

const HRIMModelSummary = () => {
  const {
    selectedRepository,
    analysisResults,
    analyzing,
    analysisError,
  } = useRepository();

  // Values returned by the backend API.
  const results = analysisResults ?? {};
  const summary = results.summary ?? {};

  const multimodalData =
    results.multimodal_proxy_predictions ?? {};

  const predictions = Array.isArray(multimodalData.predictions)
    ? multimodalData.predictions
    : [];

  // Repository overview.
  const packageCount =
    summary.packages ??
    results.total_packages ??
    results.packages_analyzed ??
    null;

  const dependencyCount = summary.dependency_edges ?? null;

  const architecturePackages =
    summary.architecture_packages ?? null;

  const evolutionFileCount =
    summary.files_with_evolution ??
    results.file_evolution_count ??
    null;

  // Model configuration.
  const modelName =
    multimodalData.model_type ?? "Multimodal HRIM";

  const featureGroups =
    predictions.find((item) => item.feature_groups)?.feature_groups ??
    {};

  const featureDimensions =
    multimodalData.feature_dimensions ??
    predictions.find((item => item.feature_dimensions != null))
      ?.feature_dimensions ??
    Object.values(featureGroups).reduce(
      (total, count) => total + (Number(count) || 0),
      0
    );

  const temporalAlignmentVerified =
    multimodalData.temporal_alignment_verified === true;

  const isExploratory =
    multimodalData.status === "exploratory" ||
    predictions.some(
      (item) =>
        item.target === "architecture_change_proxy_label"
    );

  // Prefer the backend status, but show the live UI state
  // while the request is running or has failed.
  const status = analyzing
    ? "Analyzing"
    : analysisError
      ? "Failed"
      : results.status || (analysisResults ? "Completed" : "Not started");

  const metrics = [
    {
      label: "Packages Analyzed",
      value: formatNumber(packageCount),
      description: "Repository packages",
      icon: Package,
    },
    {
      label: "Dependency Edges",
      value: formatNumber(dependencyCount),
      description: "Detected relationships",
      icon: Network,
    },
    {
      label: "Files with Evolution",
      value: formatNumber(evolutionFileCount),
      description: "Files represented in history",
      icon: FileCode2,
    },
    {
      label: "Multimodal Predictions",
      value: formatNumber(predictions.length),
      description: "Package-level outputs",
      icon: Activity,
    },
  ];

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">

      {/* Header */}
      <header className="relative overflow-hidden border-b border-slate-100 bg-gradient-to-br from-white via-white to-indigo-50/70 px-5 py-6 sm:px-7">
        <div className="pointer-events-none absolute -right-12 -top-16 h-48 w-48 rounded-full bg-indigo-100/50 blur-3xl" />

        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 items-start gap-3.5">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-lg shadow-indigo-200/60">
              <BrainCircuit size={24} strokeWidth={1.8} />
            </div>

            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold tracking-tight text-slate-900">
                  HRIM Model Summary
                </h2>

                <span className="inline-flex items-center gap-1 rounded-full border border-indigo-100 bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-indigo-700">
                  <Sparkles size={11} />
                  Intelligence
                </span>
              </div>

              <p className="mt-1.5 text-sm leading-6 text-slate-500">
                Hybrid Repository Intelligence Model
              </p>

              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                <span className="text-slate-400">Repository</span>
                <span className="max-w-full break-all rounded-md border border-slate-200 bg-white/80 px-2 py-1 font-medium text-slate-700">
                  {selectedRepository?.name ||
                    "No repository selected"}
                </span>
              </div>

              {results.repository_id && (
                <p className="mt-2 break-all text-[10px] text-slate-400">
                  ID: {results.repository_id}
                </p>
              )}
            </div>
          </div>

          <StatusBadge
            analyzing={analyzing}
            error={analysisError}
            hasResults={Boolean(analysisResults)}
            status={status}
          />
        </div>

        {/* Backend technology metadata */}
        <div className="relative mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <InfoTile
            icon={Code2}
            label="Language"
            value={results.language ?? "—"}
          />

          <InfoTile
            icon={Database}
            label="Technology"
            value={results.technology ?? "—"}
          />
        </div>
      </header>

      <div className="space-y-8 p-5 sm:p-7">

        {/* Repository metrics */}
        <section>
          <SectionHeading
            eyebrow="OVERVIEW"
            title="Repository Analytics"
            description="Statistics retrieved from the latest repository analysis."
          />

          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {metrics.map(
              ({ label, value, description, icon: Icon }) => (
                <article
                  key={label}
                  className="group min-w-0 rounded-xl border border-slate-200/80 bg-white p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md hover:shadow-indigo-100/40 sm:p-5"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 transition-colors group-hover:bg-indigo-100">
                      <Icon size={19} strokeWidth={1.8} />
                    </div>

                    <ArrowUpRight
                      size={15}
                      className="text-slate-300 transition-colors group-hover:text-indigo-500"
                    />
                  </div>

                  <p className="mt-5 break-words text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
                    {value}
                  </p>

                  <p className="mt-2 text-xs font-semibold text-slate-700">
                    {label}
                  </p>

                  <p className="mt-1 text-xs leading-5 text-slate-400">
                    {description}
                  </p>
                </article>
              )
            )}
          </div>

          {architecturePackages !== null && (
            <div className="mt-3 flex items-center gap-3 rounded-xl border border-slate-200/80 bg-slate-50/70 px-4 py-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-indigo-600 shadow-sm">
                <Layers3 size={18} />
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-slate-700">
                  Architecture Packages
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Packages included in architecture analysis
                </p>
              </div>

              <span className="text-lg font-semibold tabular-nums text-slate-900">
                {formatNumber(architecturePackages)}
              </span>
            </div>
          )}
        </section>

        {/* Model configuration */}
        <section>
          <SectionHeading
            eyebrow="MODEL CONFIGURATION"
            title="Multimodal HRIM"
            description="Configuration and feature dimensions returned by the backend."
          />

          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <InfoTile
              icon={BrainCircuit}
              label="Model Type"
              value={modelName}
            />

            <InfoTile
              icon={Layers3}
              label="Combined Feature Dimensions"
              value={`${formatNumber(featureDimensions)} dimensions`}
            />
          </div>
        </section>

        {/* Feature composition */}
        <section>
          <SectionHeading
            eyebrow="MODEL ARCHITECTURE"
            title="Feature Composition"
            description="Semantic, evolutionary, structural, and graph-based feature groups."
          />

          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {FEATURE_GROUPS.map(
              ({
                key,
                label,
                technology,
                description,
                icon: Icon,
              }) => {
                const dimensions =
                  Number(featureGroups[key]) || 0;

                const percentage =
                  Number(featureDimensions) > 0
                    ? (dimensions / Number(featureDimensions)) * 100
                    : 0;

                return (
                  <article
                    key={key}
                    className="min-w-0 rounded-xl border border-slate-200/80 bg-white p-4 transition-colors hover:border-indigo-200 sm:p-5"
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-slate-600 ring-1 ring-slate-200/80">
                        <Icon size={20} strokeWidth={1.8} />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <h4 className="text-sm font-semibold text-slate-800">
                            {label}
                          </h4>

                          <span className="rounded-md bg-indigo-50 px-2 py-1 text-xs font-semibold tabular-nums text-indigo-700">
                            {formatNumber(dimensions)}
                          </span>
                        </div>

                        <p className="mt-1 text-xs font-medium text-slate-500">
                          {technology}
                        </p>

                        <p className="mt-2 text-xs leading-5 text-slate-400">
                          {description}
                        </p>
                      </div>
                    </div>

                    <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-indigo-500 transition-all duration-500"
                        style={{
                          width: `${Math.min(100, percentage)}%`,
                        }}
                      />
                    </div>

                    <div className="mt-2 flex items-center justify-between gap-2">
                      <span className="text-[11px] text-slate-400">
                        Feature contribution
                      </span>
                      <span className="text-xs font-semibold tabular-nums text-slate-600">
                        {percentage.toFixed(2)}%
                      </span>
                    </div>
                  </article>
                );
              }
            )}
          </div>
        </section>

        {/* Model validation notice */}
        {isExploratory && (
          <section className="overflow-hidden rounded-xl border border-amber-200/80 bg-amber-50/50">
            <div className="flex items-start gap-3.5 p-4 sm:p-5">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
                <ShieldAlert size={20} />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-amber-950">
                    Exploratory Model
                  </h3>

                  <span className="rounded-full border border-amber-200 bg-white/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
                    Validation Pending
                  </span>
                </div>

                <p className="mt-2 text-xs leading-5 text-amber-900/80">
                  {multimodalData?.caveat ??
                    "Predictions use an exploratory architecture-change proxy target and should not be interpreted as validated architecture-drift detections."}
                </p>

                <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <ValidationItem
                    label="Temporal Alignment"
                    value={
                      temporalAlignmentVerified
                        ? "Verified"
                        : "Not Verified"
                    }
                    verified={temporalAlignmentVerified}
                  />

                  <ValidationItem
                    label="Prediction Target"
                    value="Exploratory Proxy"
                    verified={false}
                  />
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Loading and error states */}
        {analyzing && (
          <FeedbackMessage
            type="loading"
            message="Analyzing repository data. Results will update when processing finishes."
          />
        )}

        {analysisResults && !analysisError && !analyzing && (
          <FeedbackMessage
            type="success"
            message="Repository analysis results received successfully."
          />
        )}

        {analysisError && (
          <FeedbackMessage
            type="error"
            message={analysisError}
          />
        )}
      </div>
    </section>
  );
};

const SectionHeading = ({ eyebrow, title, description }) => (
  <div className="min-w-0">
    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-indigo-600">
      {eyebrow}
    </p>

    <h3 className="mt-1.5 text-base font-semibold tracking-tight text-slate-900">
      {title}
    </h3>

    <p className="mt-1.5 text-xs leading-5 text-slate-500">
      {description}
    </p>
  </div>
);

const InfoTile = ({ icon: Icon, label, value }) => (
  <div className="flex min-w-0 items-center gap-3 rounded-xl border border-slate-200/80 bg-white/80 p-3.5">
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
      <Icon size={17} />
    </div>

    <div className="min-w-0">
      <p className="text-[11px] text-slate-400">{label}</p>
      <p className="mt-1 break-words text-xs font-semibold text-slate-800">
        {value}
      </p>
    </div>
  </div>
);

const StatusBadge = ({
  analyzing,
  error,
  hasResults,
  status,
}) => {
  const styles = analyzing
    ? "border-indigo-200 bg-indigo-50 text-indigo-700"
    : error
      ? "border-red-200 bg-red-50 text-red-700"
      : hasResults
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-slate-200 bg-white text-slate-600";

  const Icon = analyzing
    ? LoaderCircle
    : error
      ? AlertCircle
      : hasResults
        ? CheckCircle2
        : Activity;

  return (
    <span
      role="status"
      className={`inline-flex w-fit shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${styles}`}
    >
      <Icon
        size={14}
        className={analyzing ? "animate-spin" : ""}
      />
      {status}
    </span>
  );
};

const ValidationItem = ({ label, value, verified }) => (
  <div className="flex items-center justify-between gap-3 rounded-lg border border-amber-200/70 bg-white/70 px-3 py-2.5">
    <span className="text-xs text-slate-600">{label}</span>

    <span
      className={`shrink-0 text-xs font-semibold ${
        verified ? "text-emerald-700" : "text-amber-800"
      }`}
    >
      {value}
    </span>
  </div>
);

const FeedbackMessage = ({ type, message }) => {
  const styles = {
    loading: "border-indigo-100 bg-indigo-50 text-indigo-700",
    success: "border-emerald-100 bg-emerald-50 text-emerald-700",
    error: "border-red-100 bg-red-50 text-red-700",
  };

  const Icon =
    type === "loading"
      ? LoaderCircle
      : type === "success"
        ? CheckCircle2
        : AlertCircle;

  return (
    <div
      role={type === "error" ? "alert" : "status"}
      className={`flex items-start gap-2.5 rounded-xl border px-4 py-3 text-xs leading-5 ${styles[type]}`}
    >
      <Icon
        size={16}
        className={`mt-0.5 shrink-0 ${
          type === "loading" ? "animate-spin" : ""
        }`}
      />
      <span>{message}</span>
    </div>
  );
};

export default HRIMModelSummary;
