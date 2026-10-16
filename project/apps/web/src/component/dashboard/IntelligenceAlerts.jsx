import React from "react";
import { AlertTriangle, Info } from "lucide-react";

import SectionHeader from "./SectionHeader";
import { alerts } from "../../data/dashboardData";

const severityStyles = {
  high: "text-red-600 bg-red-50",
  medium: "text-orange-600 bg-orange-50",
  low: "text-amber-600 bg-amber-50",
  info: "text-blue-600 bg-blue-50",
};

const IntelligenceAlerts = () => {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <SectionHeader title="INTELLIGENCE ALERT" />

      <div>
        {alerts.map((alert) => (
          <div
            key={alert.description}
            className="
              flex items-center gap-3
              border-b border-slate-100
              px-4 py-3
            "
          >
            <div
              className={`
                flex h-7 w-7
                shrink-0
                items-center justify-center
                rounded-full
                ${severityStyles[alert.type]}
              `}
            >
              {alert.type === "info" ? (
                <Info size={14} />
              ) : (
                <AlertTriangle size={14} />
              )}
            </div>

            <div className="min-w-0 flex-1">
              <p
                className={`
                  text-[10px]
                  font-semibold
                  ${severityStyles[alert.type].split(" ")[0]}
                `}
              >
                {alert.severity}
              </p>

              <p className="mt-0.5 text-[9px] leading-4 text-slate-500">
                {alert.description}
              </p>
            </div>

            <span className="hidden shrink-0 text-[9px] text-slate-400 sm:block">
              {alert.time}
            </span>

            <button
              className="
                rounded-full
                border border-slate-200
                px-2.5 py-1
                text-[9px]
                font-medium
                text-slate-500
                transition
                hover:border-indigo-200
                hover:text-indigo-600
              "
            >
              View
            </button>
          </div>
        ))}
      </div>
    </section>
  );
};

export default IntelligenceAlerts;
