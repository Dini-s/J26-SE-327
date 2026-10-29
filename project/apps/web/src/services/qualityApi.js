const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/quality";
async function request(path, options) {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: {
            "Content-Type": "application/json",
            ...(options?.headers ?? {}),
        },
        ...options,
    });
    if (!response.ok) {
        const body = await response.text();
        throw new Error(`API ${response.status}: ` + (body || response.statusText));
    }
    return (await response.json());
}
export const qualityApi = {
    bootstrap: () => request("/bootstrap", {
        method: "POST",
    }),
    status: () => request("/debug/status"),
    getOverview: () => request("/intelligence/overview"),
    getRequirements: () => request("/intelligence/requirements"),
    getRequirement: (requirementId) => request("/intelligence/" + "requirements/" + encodeURIComponent(requirementId)),
    runAnalysis: () => request("/analyze", {
        method: "POST",
    }),
    normalizeEvidence: () => request("/evidence/normalize", {
        method: "POST",
    }),
    getRevalidation: () => request("/revalidation"),
    runRevalidation: () => request("/revalidation/run", {
        method: "POST",
    }),
    getReports: () => request("/intelligence/reports"),
    exportSummary: () => request("/export/summary"),
};
