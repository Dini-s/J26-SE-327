// Architecture issue records must come from the backend analyzer.
// Do not add mock findings here; ArchitectureIssues.jsx consumes
// analysisResults.architecture_findings from RepositoryContext.
export const issueSummary = {
    total: 0,
    high: 0,
    architectureHealth: null,
};

export const issues = [];
export const recommendations = [];
