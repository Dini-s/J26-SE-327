import { topRiskPackages } from "../../../data/riskModules";

const TopRiskPackages = () => {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-xs font-semibold text-slate-900">
        Top Risky Packages
      </h2>

      <div className="mt-4 space-y-3">
        {topRiskPackages.map((item) => (
          <div
            key={item.package}
            className="flex items-center justify-between gap-2"
          >
            <div className="min-w-0">
              <p className="truncate text-[11px] font-medium text-slate-700">
                {item.package}
              </p>

              <p className="mt-0.5 text-[10px] text-slate-400">
                {item.modules} modules
              </p>
            </div>

            <span
              className={`
                  rounded-md
                  px-2 py-1
                  text-[10px]
                  font-semibold
                  ${
                    item.score >= 0.7
                      ? "bg-red-50 text-red-500"
                      : "bg-orange-50 text-orange-500"
                  }
                `}
            >
              {item.score.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
};

export default TopRiskPackages;
