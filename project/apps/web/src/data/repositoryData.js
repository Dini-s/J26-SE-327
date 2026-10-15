export const repositoryStats = [
    {
        title: 'Architectural Health',
        value: '72',
        suffix: '/100',
        description: '↑ 6.4% from last analysis',
        type: 'success',
        icon: 'health',
    },
    {
        title: 'Architecture Drift',
        value: '38%',
        description: 'Medium Risk',
        type: 'warning',
        icon: 'drift',
    },
    {
        title: 'High-Risk Modules',
        value: '6',
        description: '↑ 2 since last analysis',
        type: 'danger',
        icon: 'risk',
    },
    {
        title: 'Repository Risk Level',
        value: 'Medium',
        description: 'Trend: Stable',
        type: 'warning',
        icon: 'shield',
    },
    {
        title: 'Total Commits',
        value: '1,245',
        description: 'Last 12 months',
        type: 'info',
        icon: 'commits',
    },
    {
        title: 'Repository Size',
        value: '18.4 MB',
        description: 'Source Code',
        type: 'info',
        icon: 'size',
    },
];

export const riskTrendData = [
    { month: 'Dec', risk: 25 },
    { month: 'Jan', risk: 42 },
    { month: 'Feb', risk: 32 },
    { month: 'Mar', risk: 43 },
    { month: 'Apr', risk: 55 },
    { month: 'May', risk: 65 },
];

export const highRiskModules = [
    {
        name: 'PaymentService',
        package: 'com.petclinic.payment',
        risk: 'HIGH',
        drift: '89%',
        trend: 'up',
    },
    {
        name: 'UserService',
        package: 'com.petclinic.user',
        risk: 'HIGH',
        drift: '81%',
        trend: 'up',
    },
    {
        name: 'OrderService',
        package: 'com.petclinic.order',
        risk: 'MEDIUM',
        drift: '64%',
        trend: 'up',
    },
    {
        name: 'ProductService',
        package: 'com.petclinic.product',
        risk: 'MEDIUM',
        drift: '54%',
        trend: 'up',
    },
    {
        name: 'Logger',
        package: 'com.petclinic.util',
        risk: 'LOW',
        drift: '18%',
        trend: 'down',
    },
];

export const aiInsights = [
    {
        title: 'High code churn',
        description: '43 modifications in last 3 months',
        type: 'blue',
    },
    {
        title: 'High cyclomatic complexity',
        description: 'Complexity score: 18',
        type: 'purple',
    },
    {
        title: 'High coupling',
        description: '12 outgoing dependencies',
        type: 'purple',
    },
    {
        title: 'Layer violation detected',
        description: 'Depends on presentation layer',
        type: 'orange',
    },
];

export const evolutionData = [
    {
        label: 'Code Churn',
        value: '+24%',
        period: 'Last 6 Months',
        type: 'blue',
    },
    {
        label: 'Commit Frequency',
        value: '18',
        period: 'per week',
        type: 'green',
    },
    {
        label: 'Files Modified',
        value: '312',
        period: 'Last 6 Months',
        type: 'purple',
    },
    {
        label: 'Repository Growth',
        value: '+8.2%',
        period: 'Last 6 Months',
        type: 'orange',
    },
    {
        label: 'Refactoring Activity',
        value: '34',
        period: 'Last 6 Months',
        type: 'cyan',
    },
];

export const architectureIssues = [
    {
        name: 'Layer Violations',
        value: 4,
        percentage: 24,
    },
    {
        name: 'Circular Dependencies',
        value: 2,
        percentage: 12,
    },
    {
        name: 'High Coupling',
        value: 8,
        percentage: 47,
    },
    {
        name: 'Dependency Hotspots',
        value: 5,
        percentage: 29,
    },
    {
        name: 'Structural Complexity',
        value: 11,
        percentage: 65,
    },
];

export const recentCodeChanges = [
    {
        module: 'PaymentService',
        commit: 'a1b2c3d',
        description: 'Refactor payment validation logic',
        time: '2h ago',
        changes: '+143 / -27',
        type: 'danger',
    },
    {
        module: 'UserService',
        commit: 'd4e5f6g',
        description: 'Update user role handling',
        time: '5h ago',
        changes: '+89 / -13',
        type: 'danger',
    },
    {
        module: 'OrderService',
        commit: 'h7i8j9k',
        description: 'Improve order status update',
        time: '1d ago',
        changes: '+67 / -21',
        type: 'danger',
    },
    {
        module: 'ProductService',
        commit: 'l0m1n2o',
        description: 'Add product search optimization',
        time: '1d ago',
        changes: '+45 / -10',
        type: 'success',
    },
];

export const modelMetrics = {
    model: 'XGBoost',
    accuracy: '0.87',
    precision: '0.88',
    recall: '0.85',
    f1Score: '0.86',
    lastTrained: 'May 12, 2025',
};

export const dataSummary = [
    {
        label: 'Files Analyzed',
        value: '2,314',
    },
    {
        label: 'Classes',
        value: '987',
    },
    {
        label: 'Methods',
        value: '7,654',
    },
    {
        label: 'Dependencies',
        value: '3,842',
    },
    {
        label: 'Developers',
        value: '12',
    },
    {
        label: 'Commits',
        value: '1,245',
    },
];