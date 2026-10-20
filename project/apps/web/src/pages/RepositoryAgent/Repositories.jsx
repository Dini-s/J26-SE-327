import { useMemo, useState } from "react";
import RepositoryPageHeader from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/RepositoryPageHeader";
import { 
  repositoryStats,
  repositories as initialRepositories,
 } from "../../data/repositories";
import RepositoryStatCard from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/RepositoryStatCard";
import RepositoryFilters from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/RepositoryFilters";
import RepositoryTable from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/RepositoryTable";
import RepositoryPagination from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/RepositoryPagination";
import AddRepositoryPanel from "../../component/RepositoryIntelligent_Agent/RepositoryInsertion/AddRepositoryPanel";

const Repositories = () => {
  const [repositories, setRepositories] = useState(initialRepositories);

  const [search, setSearch] = useState("");

  const [addPanelOpen, setAddPanelOpen] = useState(false);

  const [currentPage, setCurrentPage] = useState(1);

  const filteredRepositories = useMemo(() => {
    const query = search.toLowerCase().trim();

    if (!query) {
      return repositories;
    }

    return repositories.filter(
      (repository) =>
        repository.name.toLowerCase().includes(query) ||
        repository.provider.toLowerCase().includes(query) ||
        repository.language.toLowerCase().includes(query) ||
        repository.technology.toLowerCase().includes(query),
    );
  }, [repositories, search]);

  const handleView = (repository) => {
    console.log("View repository:", repository);
  };

  const handleAnalyze = (repository) => {
    setRepositories((prev) =>
      prev.map((item) =>
        item.id === repository.id
          ? {
              ...item,
              status: "Analyzing",
              lastAnalyzed: "In Progress",
              time: "",
            }
          : item,
      ),
    );

    // Prototype simulation
    setTimeout(() => {
      setRepositories((prev) =>
        prev.map((item) =>
          item.id === repository.id
            ? {
                ...item,
                status: "Analysis Complete",
                lastAnalyzed: "May 12, 2025",
                time: "10:24 AM",
              }
            : item,
        ),
      );
    }, 2500);
  };

  const handleAddRepository = (form) => {
    const newRepository = {
      id: Date.now(),
      name: form.name,
      url: form.url.replace(/^https?:\/\//, ""),
      provider: form.provider,
      branch: form.branch,
      language: "Unknown",
      technology: "Unknown",
      status: "Connected",
      lastAnalyzed: "Not Analyzed",
      time: "",
      providerType: form.provider.toLowerCase(),
    };

    setRepositories((prev) => [newRepository, ...prev]);
  };

  return (
    <div className="mx-auto w-full max-w-[1600px]">
      {/* Header */}
      <RepositoryPageHeader onAddRepository={() => setAddPanelOpen(true)} />

      {/* Statistics */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {repositoryStats.map((stat) => (
          <RepositoryStatCard key={stat.title} {...stat} />
        ))}
      </div>

      {/* Main table card */}
      <section className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <RepositoryFilters search={search} setSearch={setSearch} />

        <RepositoryTable
          repositories={filteredRepositories}
          onView={handleView}
          onAnalyze={handleAnalyze}
        />

        <RepositoryPagination
          currentPage={currentPage}
          totalPages={2}
          onPageChange={setCurrentPage}
        />
      </section>

      {/* Add Repository Drawer */}
      <AddRepositoryPanel
        open={addPanelOpen}
        onClose={() => setAddPanelOpen(false)}
        onAdd={handleAddRepository}
      />
    </div>
  );
};

export default Repositories;
