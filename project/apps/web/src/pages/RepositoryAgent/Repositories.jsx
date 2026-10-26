import { useCallback, useEffect, useMemo, useState } from "react";

import RepositoryPageHeader from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/RepositoryPageHeader";
import { repositoryStats as initialStats } from "../../data/repositories";
import RepositoryStatCard from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/RepositoryStatCard";
import RepositoryFilters from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/RepositoryFilters";
import RepositoryTable from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/RepositoryTable";
import RepositoryPagination from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/RepositoryPagination";
import AddRepositoryPanel from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/AddRepositoryPanel";

import {
  getRepositories,
  analyzeRepository,
  registerRepository,
  cloneRepository,
} from "../../services/repositoryApi";
import { useRepository } from "../../context/RepositoryContext";

const PAGE_SIZE = 8;

const formatDate = (value) => {
  if (!value) return "Not Analyzed";

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not Analyzed"
    : date.toLocaleDateString();
};

const mapRepository = (repository) => ({
  ...repository,
  // Preserve the backend UUID; never replace it with a numeric mock ID.
  id: repository.id,
  lastAnalyzed:
    repository.status === "Analysis Complete"
      ? "Analysis Complete"
      : "Not Analyzed",
  time: "",
  language: repository.language ?? "Unknown",
  technology: repository.technology ?? "Unknown",
  providerType: repository.provider.toLowerCase().replace(/\s+/g, ""),
});

const Repositories = () => {
  const [repositories, setRepositories] = useState([]);
  const [search, setSearch] = useState("");
  const [addPanelOpen, setAddPanelOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analysisResults, setAnalysisResults] = useState(null);
  const [analysisRepository, setAnalysisRepository] = useState(null);
  const [analyzingId, setAnalyzingId] = useState(null);

  const {
    selectRepository,
    setAnalysisResults: setSharedAnalysisResults,
    setAnalyzing: setSharedAnalyzing,
    setAnalysisError: setSharedAnalysisError,
  } = useRepository();

  const loadRepositories = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const data = await getRepositories();
      setRepositories(data.map(mapRepository));
    } catch (err) {
      setError(err.message || "Could not load repositories.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRepositories();
  }, [loadRepositories]);

  const filteredRepositories = useMemo(() => {
    const query = search.toLowerCase().trim();

    if (!query) return repositories;

    return repositories.filter((repository) =>
      [
        repository.name,
        repository.provider,
        repository.branch,
        repository.url,
        repository.status,
      ].some((value) =>
        String(value ?? "")
          .toLowerCase()
          .includes(query),
      ),
    );
  }, [repositories, search]);

  const totalPages = Math.max(
    1,
    Math.ceil(filteredRepositories.length / PAGE_SIZE),
  );

  const paginatedRepositories = filteredRepositories.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );

  const stats = useMemo(() => {
    const total = repositories.length;
    const analyzed = repositories.filter(
      (repository) => repository.status === "Analysis Complete",
    ).length;
    const analyzing = repositories.filter(
      (repository) =>
        repository.status === "Analyzing" || repository.status === "Cloning",
    ).length;
    const notAnalyzed = repositories.filter(
      (repository) =>
        repository.status === "Registered" || repository.status === "Failed",
    ).length;

    return initialStats.map((stat) => {
      if (stat.title === "Total Repositories") {
        return { ...stat, value: String(total) };
      }
      if (stat.title === "Analyzed") {
        return { ...stat, value: String(analyzed) };
      }
      if (stat.title === "Analyzing") {
        return { ...stat, value: String(analyzing) };
      }
      if (stat.title === "Not Analyzed") {
        return { ...stat, value: String(notAnalyzed) };
      }
      return { ...stat, value: "—" };
    });
  }, [repositories]);

  const handleView = (repository) => {
    setAnalysisRepository(repository);
    selectRepository(repository);
    setSharedAnalyzing(true);
    setSharedAnalysisError("");
    setAnalysisResults(null);
    setError("");
    selectRepository(repository);
  };

  const handleAnalyze = async (repository) => {
    if (!repository.id) {
      setError(
        "This repository has no backend ID. Refresh the repository list.",
      );
      return;
    }

    setAnalyzingId(repository.id);
    setError("");
    setAnalysisRepository(repository);
    setAnalysisResults(null);

    setRepositories((previous) =>
      previous.map((item) =>
        item.id === repository.id ? { ...item, status: "Analyzing" } : item,
      ),
    );

    try {
      // Clone first if the repository is not yet available locally.
      if (
        repository.status === "Registered" ||
        repository.status === "Failed"
      ) {
        await cloneRepository(repository.id);
      }

      const result = await analyzeRepository(repository.id);
      setSharedAnalysisResults(result);

      setAnalysisResults(result);
      setRepositories((previous) =>
        previous.map((item) =>
          item.id === repository.id
            ? {
                ...item,
                language: result.language ?? "Unknown",
                technology: result.technology ?? "Unknown",
              }
            : item,
        ),
      );
    } catch (err) {
      setError(err.message || "Repository analysis failed.");
      setRepositories((previous) =>
        previous.map((item) =>
          item.id === repository.id ? { ...item, status: "Failed" } : item,
        ),
      );
      setSharedAnalysisError(err.message || "Repository analysis failed.");
    } finally {
      setAnalyzingId(null);
      setSharedAnalyzing(false);
    }
  };

  const handleAddRepository = async (form) => {
    setError("");

    try {
      const registered = await registerRepository({
        name: form.name,
        url: /^https:\/\//i.test(form.url)
          ? form.url.trim()
          : `https://${form.url.trim()}`,
        provider: form.provider,
        branch: form.branch || "main",
      });

      setRepositories((previous) => [mapRepository(registered), ...previous]);
      setCurrentPage(1);
      setAddPanelOpen(false);
    } catch (err) {
      setError(err.message || "Could not register repository.");
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1600px] space-y-4">
      <RepositoryPageHeader onAddRepository={() => setAddPanelOpen(true)} />

      {error && (
        <div
          role="alert"
          className="flex items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          <span>{error}</span>
          <button
            type="button"
            className="font-semibold"
            onClick={() => setError("")}
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {stats.map((stat) => (
          <RepositoryStatCard key={stat.title} {...stat} />
        ))}
      </div>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <RepositoryFilters search={search} setSearch={setSearch} />

        {loading ? (
          <p className="p-6 text-sm text-slate-500">
            Loading repositories from the API…
          </p>
        ) : (
          <RepositoryTable
            repositories={paginatedRepositories}
            onView={handleView}
            onAnalyze={handleAnalyze}
          />
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-4 py-3">
          <p className="text-sm text-slate-500">
            {filteredRepositories.length} repositories
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
              className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-sm text-slate-600">
              Page {currentPage} of {totalPages}
            </span>
            <button
              type="button"
              disabled={currentPage >= totalPages}
              onClick={() =>
                setCurrentPage((page) => Math.min(totalPages, page + 1))
              }
              className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>

        <div className="border-t border-slate-100 p-3">
          <button
            type="button"
            onClick={loadRepositories}
            className="rounded-md border px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Refresh repositories
          </button>
        </div>
      </section>

      {analysisRepository && (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                {analysisRepository.name}
              </h2>
              <p className="mt-1 break-all text-sm text-slate-500">
                {analysisRepository.url}
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setAnalysisRepository(null);
                setAnalysisResults(null);
              }}
              className="rounded-md border px-3 py-1.5 text-sm"
            >
              Close
            </button>
          </div>

          {!analysisResults ? (
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm text-slate-500">
                {analyzingId === analysisRepository.id
                  ? "Analysis is running…"
                  : "Run analysis to retrieve package-level results."}
              </p>
              <button
                type="button"
                disabled={analyzingId === analysisRepository.id}
                onClick={() => handleAnalyze(analysisRepository)}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {analyzingId === analysisRepository.id
                  ? "Analyzing…"
                  : "Run Analysis"}
              </button>
            </div>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                {[
                  ["Packages", analysisResults.summary?.packages ?? 0],
                  [
                    "Dependency edges",
                    analysisResults.summary?.dependency_edges ?? 0,
                  ],
                  [
                    "Packages predicted as proxy class 1",
                    (analysisResults.proxy_predictions ?? []).filter(
                      (item) => item.predicted_proxy_label === 1,
                    ).length,
                  ],
                  [
                    "Files with evolution",
                    analysisResults.summary?.files_with_evolution ?? 0,
                  ],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs text-slate-500">{label}</p>
                    <p className="mt-1 text-xl font-semibold text-slate-900">
                      {value}
                    </p>
                  </div>
                ))}
              </div>

              <h3 className="mb-2 font-semibold text-slate-900">
                Package proxy predictions
              </h3>
              <p className="mb-3 text-xs text-amber-700">
                Exploratory architecture-change proxy predictions, not validated
                architecture-drift detection.
              </p>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="p-3">Package</th>
                      <th className="p-3">Java files</th>
                      <th className="p-3">Coupling</th>
                      <th className="p-3">Instability</th>
                      <th className="p-3">Proxy probability</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(analysisResults.proxy_predictions ?? []).map(
                      (prediction) => {
                        const architecture = analysisResults.architecture?.find(
                          (item) =>
                            item.package_path === prediction.package_path,
                        );

                        return (
                          <tr
                            key={prediction.package_path}
                            className="border-t border-slate-100"
                          >
                            <td className="p-3 font-medium text-slate-800">
                              {prediction.package_path}
                            </td>
                            <td className="p-3">
                              {architecture?.java_files ?? "—"}
                            </td>
                            <td className="p-3">
                              {architecture?.total_coupling ?? "—"}
                            </td>
                            <td className="p-3">
                              {architecture?.instability ?? "—"}
                            </td>
                            <td className="p-3">
                              {(prediction.proxy_probability * 100).toFixed(2)}%
                            </td>
                          </tr>
                        );
                      },
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      <AddRepositoryPanel
        open={addPanelOpen}
        onClose={() => setAddPanelOpen(false)}
        onAdd={handleAddRepository}
      />
    </div>
  );
};

export default Repositories;
