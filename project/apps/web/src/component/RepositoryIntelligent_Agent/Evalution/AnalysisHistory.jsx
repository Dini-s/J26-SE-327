import { analysisHistory } from "../../../data/evolutionData";

const AnalysisHistory = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-bold text-slate-900">
          Recent Analysis History
        </h2>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[550px]">
          <thead>
            <tr className="border-b border-slate-100 text-left text-[9px] text-slate-400">
              <th className="pb-2">Analysis ID</th>

              <th className="pb-2">Date & Time</th>

              <th className="pb-2">Health Score</th>

              <th className="pb-2">Drift Probability</th>

              <th className="pb-2">Status</th>
            </tr>
          </thead>

          <tbody>
            {analysisHistory.map((item) => (
              <tr key={item.id} className="border-b border-slate-50 text-[10px]">
                <td className="py-2 text-blue-600">{item.id}</td>

                <td className="py-2 text-slate-600">
                  {item.date}
                  <br />
                  {item.time}
                </td>

                <td className="py-2 font-medium text-slate-700">
                  {item.health}
                </td>

                <td className="py-2 text-slate-700">{item.drift}</td>

                <td className="py-2">
                  <span className="rounded-md bg-emerald-50 px-2 py-1 text-[9px] font-medium text-emerald-600">
                    {item.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button className="mt-3 text-[10px] font-medium text-blue-600">
        View Full History →
      </button>
    </section>
  );
};

export default AnalysisHistory;
