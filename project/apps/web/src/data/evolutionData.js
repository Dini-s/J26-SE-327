export const evolutionStats = [
    {
        title: 'Architecture Health Score',
        value: '72',
        suffix: '/ 100',
        change: '▲ 6.4% vs last analysis',
        type: 'purple',
        icon: 'health',
    },
    {
        title: 'Drift Probability (HRIM)',
        value: '0.68',
        suffix: '',
        change: '▲ 0.08 vs last analysis',
        badge: 'High Risk',
        type: 'red',
        icon: 'drift',
    },
    {
        title: 'Total Modules',
        value: '98',
        suffix: '',
        change: '▲ 4 vs last analysis',
        type: 'blue',
        icon: 'module',
    },
    {
        title: 'Lines of Code',
        value: '125,342',
        suffix: '',
        change: '▲ 2.7% vs last analysis',
        type: 'green',
        icon: 'code',
    },
    {
        title: 'Total Commits',
        value: '1,245',
        suffix: '',
        change: '▲ 12 vs last analysis',
        type: 'orange',
        icon: 'commit',
    },
    {
        title: 'Active Developers',
        value: '12',
        suffix: '',
        change: '↓ 2 vs last analysis',
        type: 'purple',
        icon: 'developers',
    },
];

export const evolutionTrend = [
    {
        month: 'Dec 2024',
        score: 57,
    },
    {
        month: 'Jan 2025',
        score: 66,
    },
    {
        month: 'Feb 2025',
        score: 80,
    },
    {
        month: 'Mar 2025',
        score: 81,
    },
    {
        month: 'Apr 2025',
        score: 64,
    },
    {
        month: 'May 2025',
        score: 75,
    },
    {
        month: 'Jun 2025',
        score: 75,
    },
];

export const softwareMetrics = [
    {
        name: 'Cyclomatic Complexity',
        value: '8.42',
        subtitle: 'Avg per Module',
        change: '▲ 7.1%',
        level: 'High',
    },
    {
        name: 'Coupling (Ca)',
        value: '9.76',
        subtitle: 'Avg',
        change: '▲ 5.3%',
        level: 'High',
    },
    {
        name: 'Efferent Coupling (Ce)',
        value: '12.45',
        subtitle: 'Avg',
        change: '▲ 8.0%',
        level: 'High',
    },
    {
        name: 'Instability (I)',
        value: '0.61',
        subtitle: 'Avg',
        change: '▲ 4.5%',
        level: 'Medium',
    },
    {
        name: 'Abstractness (A)',
        value: '0.28',
        subtitle: 'Avg',
        change: '▼ 3.2%',
        level: 'Low',
    },
    {
        name: 'Lack of Cohesion (LCOM)',
        value: '0.42',
        subtitle: 'Avg per Module',
        change: '▲ 2.1%',
        level: 'Medium',
    },
    {
        name: 'Depth of Inheritance (DIT)',
        value: '2.35',
        subtitle: 'Avg',
        change: '▼ 1.3%',
        level: 'Low',
    },
    {
        name: 'Maintainability Index',
        value: '68.27',
        subtitle: 'Avg',
        change: '▲ 3.6%',
        level: 'Medium',
    },
];

export const highRiskModules = [
    {
        module: 'PaymentService',
        drift: '0.89',
        risk: 'High',
        health: '45 / 100',
        ca: '12.3',
        ce: '18.7',
        instability: '0.78',
    },
    {
        module: 'OwnerService',
        drift: '0.81',
        risk: 'High',
        health: '48 / 100',
        ca: '11.6',
        ce: '16.2',
        instability: '0.73',
    },
    {
        module: 'VisitService',
        drift: '0.74',
        risk: 'High',
        health: '52 / 100',
        ca: '10.4',
        ce: '14.8',
        instability: '0.65',
    },
    {
        module: 'ReportService',
        drift: '0.62',
        risk: 'Medium',
        health: '64 / 100',
        ca: '8.9',
        ce: '12.3',
        instability: '0.59',
    },
    {
        module: 'NotificationService',
        drift: '0.58',
        risk: 'Medium',
        health: '66 / 100',
        ca: '7.4',
        ce: '10.6',
        instability: '0.52',
    },
];

export const churnData = [
    {
        name: 'Added',
        value: 45231,
        percent: 36,
    },
    {
        name: 'Modified',
        value: 62874,
        percent: 50,
    },
    {
        name: 'Deleted',
        value: 17237,
        percent: 14,
    },
];

export const topMetrics = [
    {
        rank: 1,
        module: 'PaymentService',
        value: 22,
    },
    {
        rank: 2,
        module: 'BillingService',
        value: 18,
    },
    {
        rank: 3,
        module: 'OrderService',
        value: 16,
    },
    {
        rank: 4,
        module: 'OwnerService',
        value: 15,
    },
    {
        rank: 5,
        module: 'VisitService',
        value: 14,
    },
];

export const architectureIssues = [
    {
        name: 'High Impact',
        value: 12,
        percent: 37,
    },
    {
        name: 'Medium Impact',
        value: 14,
        percent: 44,
    },
    {
        name: 'Low Impact',
        value: 6,
        percent: 19,
    },
];

export const dependencies = [
    {
        name: 'Total Dependencies',
        value: '1,842',
        percent: '',
    },
    {
        name: 'Internal Dependencies',
        value: '1,523',
        percent: '83%',
    },
    {
        name: 'External Dependencies',
        value: '319',
        percent: '17%',
    },
    {
        name: 'Circular Dependencies',
        value: '5',
        percent: '',
    },
];

export const analysisHistory = [
    {
        id: 'AN-20250512-0945',
        date: 'May 12, 2025',
        time: '09:45 AM',
        health: '72 / 100',
        drift: '0.68',
        status: 'Completed',
    },
    {
        id: 'AN-20250505-0930',
        date: 'May 05, 2025',
        time: '09:30 AM',
        health: '68 / 100',
        drift: '0.60',
        status: 'Completed',
    },
    {
        id: 'AN-20250428-0915',
        date: 'Apr 28, 2025',
        time: '09:15 AM',
        health: '65 / 100',
        drift: '0.55',
        status: 'Completed',
    },
    {
        id: 'AN-20250421-0900',
        date: 'Apr 21, 2025',
        time: '09:00 AM',
        health: '61 / 100',
        drift: '0.48',
        status: 'Completed',
    },
];