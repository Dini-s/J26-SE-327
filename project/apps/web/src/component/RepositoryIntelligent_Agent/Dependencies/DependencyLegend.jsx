const DependencyLegend = () => {
  return (
    <div className="absolute left-3 top-3 z-10 w-[125px] rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <h3 className="text-[10px] font-bold text-slate-700">Legend</h3>

      <p className="mt-3 text-[9px] font-semibold text-slate-400">Layer</p>

      {[
        ["bg-blue-500", "Presentation Layer"],
        ["bg-emerald-500", "Service Layer"],
        ["bg-purple-500", "Repository Layer"],
        ["bg-orange-500", "Infrastructure Layer"],
        ["bg-slate-400", "External Library"],
      ].map(([color, label]) => (
        <div key={label} className="mt-2 flex items-center gap-2">
          <span className={`h-2 w-2 rounded-sm ${color}`} />

          <span className="text-[9px] text-slate-600">{label}</span>
        </div>
      ))}

      <p className="mt-4 text-[9px] font-semibold text-slate-400">Relation</p>

      <div className="mt-2 space-y-2 text-[9px] text-slate-600">
        <p>→ Depends On</p>
        <p>→ Uses</p>
        <p>→ Implements</p>
        <p className="text-red-500">→ Circular Dependency</p>
      </div>

      <p className="mt-4 text-[9px] font-semibold text-slate-400">Risk Level</p>

      <div className="mt-2 space-y-2">
        <p className="text-[9px] text-red-500">● High</p>
        <p className="text-[9px] text-orange-500">● Medium</p>
        <p className="text-[9px] text-emerald-600">● Low</p>
      </div>
    </div>
  );
};

export default DependencyLegend;
