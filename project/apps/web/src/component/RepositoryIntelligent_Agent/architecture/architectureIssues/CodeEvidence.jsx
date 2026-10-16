import { AlertTriangle, ExternalLink } from "lucide-react";

const CodeEvidence = ({ evidence }) => {
  if (!evidence) return null;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-center justify-between">
        <h3 className="text-[12px] font-bold text-slate-800">Code Evidence</h3>

        <button className="flex items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-blue-600">
          View Full File
          <ExternalLink size={9} />
        </button>
      </div>

      <div
        className="
          mt-3
          overflow-hidden
          rounded-md
          bg-[#0f1b35]
          font-mono
        "
      >
        <div className="px-3 py-2 text-[12px] font-medium text-white">
          {evidence.file}
        </div>

        <div className="border-t border-white/10 py-2">
          {evidence.lines.map((line, index) => (
            <div
              key={index}
              className={`
                  flex
                  min-h-[18px]
                  px-3
                  text-[12px]
                  leading-4
                  ${
                    line.includes("paymentService.processPayment")
                      ? "bg-red-500/20 text-red-300"
                      : "text-slate-300"
                  }
                `}
            >
              <span className="mr-4 w-4 select-none text-right text-slate-500">
                {index + 1}
              </span>

              <code>{line || " "}</code>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-2 flex items-center gap-1.5 rounded-md bg-red-50 px-2 py-1.5 text-[11px] font-medium text-red-500">
        <AlertTriangle size={10} />
        Direct dependency on PaymentService detected
      </div>
    </section>
  );
};

export default CodeEvidence;
