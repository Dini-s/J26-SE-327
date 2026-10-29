export const stats = [
    {
        title: 'Overall Health',
        value: '78%',
        status: 'Good',
        statusType: 'success',
        icon: 'health',
        progress: 78,
    },
    {
        title: 'Active Agent',
        value: '3',
        status: 'Running',
        statusType: 'success',
        icon: 'agent',
        trend: 'wave',
    },
    {
        title: 'Open Issues',
        value: '12',
        status: 'Needs Attention',
        statusType: 'warning',
        icon: 'warning',
        trend: 'warning',
    },
];

export const intelligenceComponents = [
    {
        number: '01',
        title: 'Requirement Intelligence',
        description:
            'Requirement understanding, ambiguity detection, tasks, user stories and acceptance criteria.',
        progress: 82,
        status: 'Operational',
        statusType: 'success',
    },
    {
        number: '02',
        title: 'Repository Intelligence',
        description:
            'Repository understanding, architecture risk, evolution, dependencies and drift prediction.',
        progress: 76,
        status: 'Operational',
        statusType: 'success',
    },
    {
        number: '03',
        title: 'Quality & Testing Intelligence',
        description:
            'Requirement validation, implementation evidence, testing evidence and satisfaction analysis.',
        progress: 70,
        status: 'Operational',
        statusType: 'success',
    },
    {
        number: '04',
        title: 'Traceability Intelligence',
        description:
            'Trace recovery, continuous verification, link decay and change-impact analysis.',
        progress: 68,
        status: 'Attention',
        statusType: 'warning',
    },
];

export const agents = [
    {
        name: 'comp 1',
        component: 'Requirement Intelligence',
    },
    {
        name: 'comp 2',
        component: 'Repository Intelligence',
    },
    {
        name: 'comp 3',
        component: 'Quality & Testing Intelligence',
    },
    {
        name: 'comp 4',
        component: 'Traceability Intelligence',
    },
];

export const insights = [
    'Repository risk information is available for Quality & Testing analysis.',
    'Repository entities can connect to requirement and task entities through USKG.',
    'Traceability can consume repository evolution and architecture information.',
    'Cross-component reasoning is enabled through the shared knowledge graph.',
];

export const graphStats = [
    {
        label: 'Node',
        value: '25,910',
    },
    {
        label: 'Relationship Type',
        value: '18',
    },
    {
        label: 'Entity Type',
        value: '12',
    },
];

export const alerts = [
    {
        severity: 'High Risk',
        description:
            'Security vulnerability detected in authentication module',
        time: '10m ago',
        type: 'high',
    },
    {
        severity: 'Medium Risk',
        description:
            'Code complexity is above threshold in PaymentService',
        time: '25m ago',
        type: 'medium',
    },
    {
        severity: 'Low Risk',
        description:
            'Outdated dependency detected in UI component',
        time: '1h ago',
        type: 'low',
    },
    {
        severity: 'Info',
        description:
            'Repository sync completed successfully',
        time: '2h ago',
        type: 'info',
    },
];

export const activities = [
    {
        title: 'Repository indexed',
        description: 'Pet Clinic',
        time: '8m ago',
        type: 'repository',
    },
    {
        title: 'AI Analysis completed',
        description: 'Component 2',
        time: '1h ago',
        type: 'analysis',
    },
    {
        title: 'New issue detected',
        description: 'Comp 3 - Testing',
        time: '1 day ago',
        type: 'issue',
    },
    {
        title: 'Trace link updated',
        description: 'REQ-102 ↔ DEF-201',
        time: '1 day ago',
        type: 'trace',
    },
];