import RepositoryRow from "./RepositoryRow";

const RepositoryTable = ({ repositories, onView, onAnalyze }) => {
  return (
    <div className="overflow-x-auto">
      {/* Header */}
      <div
        className="
          grid
          min-w-[1050px]
          grid-cols-[2.1fr_1fr_0.7fr_1.3fr_1.1fr_1fr_0.8fr]
          items-center
          bg-slate-50
          px-4
          py-3
          text-[10px]
          font-semibold
          uppercase
          tracking-wide
          text-slate-500
        "
      >
        <span>Repository</span>
        <span>Provider</span>
        <span>Branch</span>
        <span>Language / Tech</span>
        <span>Status</span>
        <span>Last Analyzed</span>
        <span>Actions</span>
      </div>

      {/* Rows */}
      {repositories.map((repository) => (
        <RepositoryRow
          key={repository.id}
          repository={repository}
          onView={onView}
          onAnalyze={onAnalyze}
        />
      ))}
    </div>
  );
};

export default RepositoryTable;
