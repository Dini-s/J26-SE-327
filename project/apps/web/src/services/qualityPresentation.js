const labels = {
  ADEQUATE: "Adequate evidence", PARTIAL: "Partial evidence", INADEQUATE: "Insufficient evidence",
  NOT_ASSESSED: "Not assessed", FUNCTIONAL: "Functional", NON_FUNCTIONAL: "Non-functional",
  HIGH: "High", MEDIUM: "Medium", LOW: "Low", PASS: "Passed", FAIL: "Failed",
  UNMAPPED: "No linked result", NOT_EXECUTED: "Not executed", VALIDATED: "Execution confirmed",
};
export function humanize(value) {
  if (!value) return "Not available";
  return labels[value] || String(value).toLowerCase().replaceAll("_", " ").replace(/^./, (s) => s.toUpperCase());
}
export function number(value) { return value == null || !Number.isFinite(Number(value)) ? "—" : Number(value).toLocaleString(); }
export function percent(value) { return value == null || !Number.isFinite(Number(value)) ? "—" : `${Number(value).toFixed(1)}%`; }
export function score(value) { return value == null ? "—" : `${Number(value).toFixed(2)} / 1`; }
export function downloadJson(value, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
