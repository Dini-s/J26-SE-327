import { FileText, Plus, RefreshCw } from "lucide-react";

const QuickActions = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <h3 className="text-[12px] font-bold text-slate-800">Quick Actions</h3>

      <div className="mt-3 grid grid-cols-2 gap-2 ">
        <Action icon={Plus} size={20} label="Create Refactoring Task" />

        <Action icon={Plus} size={20} label="Add to Watchlist" />

        <Action icon={FileText} size={20} label="Generate Detailed Report" />

        <Action icon={RefreshCw} size={20} label="Re-analyze Module" />
      </div>
    </section>
  );
};

const Action = ({ icon: Icon, label }) => {
  return (
    <button
      type="button"
      className="
        flex
        items-center
        justify-center
        gap-1
        rounded-md
        border
        border-blue-100
        bg-blue-50/30
        px-2
        py-2
        text-[9px]
        font-semibold
        text-blue-600
        transition
        hover:bg-blue-50
      "
    >
      <Icon size={10} />

      {label}
    </button>
  );
};

export default QuickActions;
