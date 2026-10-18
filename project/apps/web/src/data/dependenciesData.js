export const dependencySummary = {
    total: "1,842",
    modules: 98,
    highCoupling: 12,
    circular: 5,
    health: 72,
    orphan: 8,
};

export const dependencyStats = [
    {
        title: "Total Dependencies",
        value: "1,842",
        subtitle: "8.6% vs last analysis",
        trend: "up",
        icon: "link",
        color: "blue",
    },
    {
        title: "Modules",
        value: "98",
        subtitle: "No change",
        trend: "neutral",
        icon: "cube",
        color: "blue",
    },
    {
        title: "High Coupling Modules",
        value: "12",
        subtitle: "2 vs last analysis",
        trend: "up",
        icon: "coupling",
        color: "orange",
    },
    {
        title: "Circular Dependencies",
        value: "5",
        subtitle: "1 vs last analysis",
        trend: "down",
        icon: "refresh",
        color: "red",
    },
    {
        title: "Dependency Health",
        value: "72",
        subtitle: "6.4% vs last analysis",
        trend: "up",
        icon: "health",
        color: "green",
        health: true,
    },
    {
        title: "Orphan Modules",
        value: "8",
        subtitle: "2 vs last analysis",
        trend: "down",
        icon: "orphan",
        color: "purple",
    },
];

export const dependencies = [
    {
        name: "OwnerRepository",
        strength: "Strong",
        type: "outgoing",
        color: "purple",
    },
    {
        name: "PetService",
        strength: "Medium",
        type: "outgoing",
        color: "orange",
    },
    {
        name: "VisitService",
        strength: "Medium",
        type: "outgoing",
        color: "orange",
    },
    {
        name: "EmailService",
        strength: "Low",
        type: "outgoing",
        color: "green",
    },
    {
        name: "AuditService",
        strength: "Low",
        type: "outgoing",
        color: "green",
    },
];

export const circularDependencies = [
    {
        path: "OwnerService → AuditService → OwnerService",
        severity: "High",
        modules: 2,
    },
    {
        path: "PetService → OwnerService → PetService",
        severity: "High",
        modules: 2,
    },
    {
        path: "VisitService → OwnerService → VisitService",
        severity: "Medium",
        modules: 2,
    },
    {
        path: "EmailService → NotificationService → EmailService",
        severity: "Low",
        modules: 2,
    },
    {
        path: "ReportService → DataService → ReportService",
        severity: "Low",
        modules: 2,
    },
];

export const highDependencyModules = [
    {
        name: "OwnerService",
        afferent: 9,
        efferent: 14,
        instability: "0.61",
        risk: "High",
    },
    {
        name: "PetService",
        afferent: 8,
        efferent: 12,
        instability: "0.60",
        risk: "High",
    },
    {
        name: "VisitService",
        afferent: 7,
        efferent: 10,
        instability: "0.59",
        risk: "Medium",
    },
    {
        name: "OrderService",
        afferent: 6,
        efferent: 9,
        instability: "0.60",
        risk: "Medium",
    },
    {
        name: "ReportService",
        afferent: 5,
        efferent: 8,
        instability: "0.62",
        risk: "Medium",
    },
];

export const orphanModules = [
    {
        name: "OldReportGenerator",
        issue: "No incoming dependencies",
    },
    {
        name: "LegacyExportService",
        issue: "Not used by any module",
    },
    {
        name: "TestDataBuilder",
        issue: "Not used in production code",
    },
    {
        name: "DummyPaymentGateway",
        issue: "No incoming dependencies",
    },
];