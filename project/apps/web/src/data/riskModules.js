export const riskStats = [
    {
        title: 'High-Risk Modules',
        value: '6',
        description: '↑ 2 since last analysis',
        type: 'red',
        icon: 'warning',
    },
    {
        title: 'Medium-Risk Modules',
        value: '8',
        description: 'No change',
        type: 'orange',
        icon: 'shield',
    },
    {
        title: 'Low-Risk Modules',
        value: '24',
        description: '↓ 3 since last analysis',
        type: 'green',
        icon: 'shield',
    },
    {
        title: 'Average Drift Probability',
        value: '38%',
        description: 'Medium Risk',
        type: 'purple',
        icon: 'drift',
    },
    {
        title: 'Most Critical Module',
        value: 'PaymentService',
        description: '89% Drift Probability',
        type: 'red',
        icon: 'critical',
    },
    {
        title: 'Total Modules Analyzed',
        value: '38',
        description: '100% of repository',
        type: 'blue',
        icon: 'cube',
    },
];

export const riskModules = [
    {
        id: 1,
        name: 'PaymentService',
        package: 'com.petclinic.payment',
        risk: 'HIGH',
        drift: 89,
        complexity: 'High',
        coupling: 'High',
        churn: 'High',
        trend: [55, 62, 58, 73, 68, 82, 89],
    },
    {
        id: 2,
        name: 'UserService',
        package: 'com.petclinic.user',
        risk: 'HIGH',
        drift: 81,
        complexity: 'High',
        coupling: 'High',
        churn: 'High',
        trend: [48, 54, 51, 63, 61, 74, 81],
    },
    {
        id: 3,
        name: 'OrderService',
        package: 'com.petclinic.order',
        risk: 'MEDIUM',
        drift: 64,
        complexity: 'Medium',
        coupling: 'High',
        churn: 'Medium',
        trend: [40, 44, 42, 51, 48, 58, 64],
    },
    {
        id: 4,
        name: 'ProductService',
        package: 'com.petclinic.product',
        risk: 'MEDIUM',
        drift: 54,
        complexity: 'Medium',
        coupling: 'Medium',
        churn: 'Medium',
        trend: [35, 39, 37, 44, 41, 49, 54],
    },
    {
        id: 5,
        name: 'InventoryService',
        package: 'com.petclinic.inventory',
        risk: 'MEDIUM',
        drift: 47,
        complexity: 'Medium',
        coupling: 'Medium',
        churn: 'Low',
        trend: [30, 35, 32, 39, 36, 42, 47],
    },
    {
        id: 6,
        name: 'VisitService',
        package: 'com.petclinic.visit',
        risk: 'MEDIUM',
        drift: 42,
        complexity: 'Medium',
        coupling: 'Medium',
        churn: 'Low',
        trend: [28, 30, 31, 35, 33, 39, 42],
    },
    {
        id: 7,
        name: 'Logger',
        package: 'com.petclinic.util',
        risk: 'LOW',
        drift: 18,
        complexity: 'Low',
        coupling: 'Low',
        churn: 'Low',
        trend: [18, 20, 18, 19, 18, 17, 18],
    },
    {
        id: 8,
        name: 'EmailService',
        package: 'com.petclinic.email',
        risk: 'LOW',
        drift: 16,
        complexity: 'Low',
        coupling: 'Low',
        churn: 'Low',
        trend: [14, 16, 15, 17, 15, 16, 16],
    },
];

export const riskFactors = [
    {
        name: 'Code Churn',
        value: 0.28,
        level: 'Very High',
        type: 'high',
    },
    {
        name: 'Cyclomatic Complexity',
        value: 0.21,
        level: 'High',
        type: 'high',
    },
    {
        name: 'Coupling',
        value: 0.18,
        level: 'High',
        type: 'high',
    },
    {
        name: 'Dependencies',
        value: 0.13,
        level: 'Medium',
        type: 'medium',
    },
    {
        name: 'Layer Violation',
        value: 0.11,
        level: 'Medium',
        type: 'medium',
    },
    {
        name: 'Change Frequency',
        value: 0.07,
        level: 'Low',
        type: 'low',
    },
    {
        name: 'Other Factors',
        value: 0.02,
        level: 'Low',
        type: 'low',
    },
];

export const riskDistribution = [
    {
        name: 'High Risk',
        value: 6,
    },
    {
        name: 'Medium Risk',
        value: 8,
    },
    {
        name: 'Low Risk',
        value: 24,
    },
];

export const driftDistribution = [
    {
        range: '0-20%',
        value: 5,
    },
    {
        range: '20-40%',
        value: 14,
    },
    {
        range: '40-60%',
        value: 8,
    },
    {
        range: '60-80%',
        value: 4,
    },
    {
        range: '80-100%',
        value: 2,
    },
];

export const topRiskPackages = [
    {
        package: 'com.petclinic.payment',
        modules: 2,
        score: 0.85,
    },
    {
        package: 'com.petclinic.user',
        modules: 3,
        score: 0.72,
    },
    {
        package: 'com.petclinic.order',
        modules: 2,
        score: 0.61,
    },
    {
        package: 'com.petclinic.product',
        modules: 2,
        score: 0.54,
    },
    {
        package: 'com.petclinic.inventory',
        modules: 1,
        score: 0.47,
    },
];

export const riskInsights = [
    {
        text: 'PaymentService has the highest architecture drift probability due to high churn and strong coupling.',
        type: 'red',
    },
    {
        text: '5 modules show increasing drift trend in the last 30 days.',
        type: 'orange',
    },
    {
        text: 'Most risky packages are in the service layer.',
        type: 'green',
    },
];