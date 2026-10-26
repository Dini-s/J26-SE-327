import { RefreshCw, Play, Database, ChevronDown } from "lucide-react";
import { useRepository } from "../../../context/RepositoryContext";

const RepositoryHeader = () => {
  const {
    repositories = [],
    selectedRepository,
    selectRepository,
    analyzeRepository,
    refreshRepositories,
    analyzing,
    loadingRepositories,
    analysisError,
  } = useRepository();
  const handleAnalyze = () => analyzeRepository().catch(() => {});
  const handleRefresh = () => refreshRepositories().catch(() => {});
  return (
    <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <h1 className="text-xl font-bold text-slate-900 sm:text-2xl">
          Repository Intelligence Dashboard
        </h1>
        <p className="mt-1 text-xs text-slate-500">
          AI-powered semantic repository and architecture intelligence
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-[11px] text-slate-700 shadow-sm">
          <Database size={14} className="text-indigo-600" />
          <select
            aria-label="Select repository"
            className="max-w-[210px] bg-transparent outline-none"
            value={selectedRepository?.id || ""}
            onChange={(e) =>
              selectRepository(
                repositories.find((r) => r.id === e.target.value) || null,
              )
            }
            disabled={loadingRepositories || repositories.length === 0}
          >
            {repositories.length === 0 && (
              <option value="">
                {loadingRepositories
                  ? "Loading repositories…"
                  : "No repositories found"}
              </option>
            )}
            {repositories.map((repo) => (
              <option key={repo.id} value={repo.id}>
                {repo.name || repo.url || repo.id}
              </option>
            ))}
          </select>
          <ChevronDown size={13} />
        </label>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={loadingRepositories}
          className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-[10px] font-medium text-slate-700 shadow-sm hover:border-indigo-200 disabled:opacity-50"
        >
          <RefreshCw
            size={14}
            className={loadingRepositories ? "animate-spin" : ""}
          />
          {loadingRepositories ? "Refreshing…" : "Refresh"}
        </button>
        <button
          type="button"
          onClick={handleAnalyze}
          disabled={!selectedRepository?.id || analyzing}
          className="flex h-9 items-center gap-2 rounded-lg bg-indigo-600 px-4 text-[10px] font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Play size={13} fill="currentColor" />
          {analyzing ? "Analyzing…" : "Analyze Repository"}
        </button>
      </div>
      {analysisError && (
        <p role="alert" className="basis-full text-xs text-red-600">
          {analysisError}
        </p>
      )}
    </div>
  );
};
export default RepositoryHeader;
