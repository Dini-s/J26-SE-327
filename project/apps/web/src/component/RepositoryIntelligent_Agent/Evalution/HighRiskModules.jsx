
import { Eye } from "lucide-react";
import { highRiskModules } from "../../../data/evolutionData";
import { useNavigate } from "react-router-dom";

const HighRiskModules = () => {
  const navigate = useNavigate();

  const moveRiskModule = () => {
    navigate("/repository/risk-models");
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-slate-900">
          High Risk Modules (Based on HRIM)
        </h2>

        <button
          onClick={moveRiskModule}
          className="text-[10px] font-medium text-blue-600"
        >
          View All Modules →
        </button>
      </div>

      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[600px] border-collapse">
          <thead>
            <tr className="border-b border-slate-100 text-left text-[11px] text-slate-400">
              <th className="pb-2">Module</th>
              <th className="pb-2">Drift Probability</th>
              <th className="pb-2">Risk Level</th>
              <th className="pb-2">Architecture Health</th>
              <th className="pb-2">Ca</th>
              <th className="pb-2">Ce</th>
              <th className="pb-2">Instability</th>
              <th className="pb-2">Actions</th>
            </tr>
          </thead>

          <tbody>
            {highRiskModules.map((module) => (
              <tr
                key={module.module}
                className="border-b border-slate-50 text-[10px] hover:bg-slate-50"
              >
                <td className="py-2 font-medium text-slate-700">
                  {module.module}
                </td>

                <td className="py-2 font-semibold text-slate-700">
                  {module.drift}
                </td>

                <td className="py-2">
                  <span
                    className={`
                      rounded-md px-2 py-1
                      text-[11px] font-semibold
                      ${
                        module.risk === "High"
                          ? "bg-red-50 text-red-500"
                          : "bg-orange-50 text-orange-500"
                      }
                    `}
                  >
                    {module.risk}
                  </span>
                </td>

                <td className="py-2">{module.health}</td>

                <td className="py-2">{module.ca}</td>

                <td className="py-2">{module.ce}</td>

                <td className="py-2">{module.instability}</td>

                <td className="py-2">
                  <button
                    className="
                      rounded-md
                      border border-slate-200
                      p-1.5
                      text-slate-500
                      hover:bg-blue-50
                      hover:text-blue-600
                    "
                  >
                    <Eye size={11} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};

export default HighRiskModules;
