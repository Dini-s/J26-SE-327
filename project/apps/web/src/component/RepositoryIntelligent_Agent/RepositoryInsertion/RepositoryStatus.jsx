const statusStyles = {
  "Analysis Complete": "bg-emerald-50 text-emerald-600",
  Analyzing: "bg-purple-50 text-purple-600",
  Connected: "bg-blue-50 text-blue-600",
  "High Risk": "bg-red-50 text-red-500",
};

const RepositoryStatus = ({ status }) => {
  return (
    <span
      className={`
        inline-flex
        items-center
        gap-1.5
        whitespace-nowrap
        rounded-md
        px-2
        py-1
        text-[9px]
        font-medium
        ${statusStyles[status] || "bg-slate-50 text-slate-500"}
      `}
    >
      <span
        className={`
          h-1.5
          w-1.5
          rounded-full
          ${
            status === "High Risk"
              ? "bg-red-500"
              : status === "Analyzing"
                ? "bg-purple-500"
                : status === "Connected"
                  ? "bg-blue-500"
                  : "bg-emerald-500"
          }
        `}
      />

      {status}
    </span>
  );
};

export default RepositoryStatus;
