export const linkLabel = (status) => ({ verified: "Approved", pending_review: "Needs review", deferred: "Deferred", rejected: "Rejected", decayed: "Broken" }[status] || "Approved");
export const linkTone = (status) => ({ verified: "green", pending_review: "amber", deferred: "slate", rejected: "red", decayed: "red" }[status] || "green");
export const linkColor = (status) => ({ pending_review: "#d97706", deferred: "#64748b", rejected: "#94a3b8", decayed: "#ef4444" }[status] || "#6366f1");
