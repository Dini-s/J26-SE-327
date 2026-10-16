export const architectureStats = [
    {
        title: 'Architecture Health',
        value: '72',
        suffix: '/ 100',
        status: 'Medium',
        type: 'green',
        icon: 'health',
    },
    {
        title: 'Layer Violations',
        value: '4',
        status: 'High Priority',
        type: 'red',
        icon: 'warning',
    },
    {
        title: 'Circular Dependencies',
        value: '2',
        status: 'Detected',
        type: 'purple',
        icon: 'refresh',
    },
    {
        title: 'Dependency Hotspots',
        value: '5',
        status: 'Modules',
        type: 'orange',
        icon: 'dependency',
    },
    {
        title: 'High Coupling Modules',
        value: '8',
        status: 'Require Attention',
        type: 'purple',
        icon: 'coupling',
    },
    {
        title: 'Structural Complexity',
        value: '0.68',
        status: 'Medium',
        type: 'blue',
        icon: 'structure',
    },
];

export const architectureNodes = [
    {
        id: 'web-controller',
        name: 'WebController',
        package: 'com.petclinic.web',
        layer: 'Presentation',
        risk: 'Low',
        position: { x: 300, y: 40 },
    },
    {
        id: 'rest-controller',
        name: 'RestController',
        package: 'com.petclinic.api',
        layer: 'Presentation',
        risk: 'Low',
        position: { x: 570, y: 40 },
    },

    {
        id: 'pet-service',
        name: 'PetService',
        package: 'com.petclinic.pet',
        layer: 'Service',
        risk: 'Medium',
        position: { x: 230, y: 170 },
    },
    {
        id: 'visit-service',
        name: 'VisitService',
        package: 'com.petclinic.visit',
        layer: 'Service',
        risk: 'Medium',
        position: { x: 470, y: 170 },
    },
    {
        id: 'owner-service',
        name: 'OwnerService',
        package: 'com.petclinic.owner',
        layer: 'Service',
        risk: 'High',
        position: { x: 700, y: 170 },
    },

    {
        id: 'pet-repository',
        name: 'PetRepository',
        package: 'com.petclinic.repository',
        layer: 'Repository',
        risk: 'Low',
        position: { x: 230, y: 300 },
    },
    {
        id: 'visit-repository',
        name: 'VisitRepository',
        package: 'com.petclinic.repository',
        layer: 'Repository',
        risk: 'Medium',
        position: { x: 470, y: 300 },
    },
    {
        id: 'owner-repository',
        name: 'OwnerRepository',
        package: 'com.petclinic.repository',
        layer: 'Repository',
        risk: 'Medium',
        position: { x: 700, y: 300 },
    },

    {
        id: 'datasource',
        name: 'DataSource',
        package: 'com.petclinic.config',
        layer: 'Infrastructure',
        risk: 'Low',
        position: { x: 230, y: 430 },
    },
    {
        id: 'transaction-manager',
        name: 'TransactionManager',
        package: 'org.springframework',
        layer: 'Infrastructure',
        risk: 'Low',
        position: { x: 470, y: 430 },
    },
    {
        id: 'cache-manager',
        name: 'CacheManager',
        package: 'org.springframework',
        layer: 'Infrastructure',
        risk: 'Low',
        position: { x: 700, y: 430 },
    },

    {
        id: 'mysql',
        name: 'MySQL DB',
        package: 'Database',
        layer: 'External',
        risk: 'Low',
        position: { x: 350, y: 560 },
    },
    {
        id: 'email',
        name: 'Email Service',
        package: 'External API',
        layer: 'External',
        risk: 'Low',
        position: { x: 600, y: 560 },
    },
];

export const architectureEdges = [
    {
        id: 'e1',
        source: 'web-controller',
        target: 'pet-service',
    },
    {
        id: 'e2',
        source: 'web-controller',
        target: 'visit-service',
    },
    {
        id: 'e3',
        source: 'rest-controller',
        target: 'visit-service',
    },
    {
        id: 'e4',
        source: 'rest-controller',
        target: 'owner-service',
    },

    {
        id: 'e5',
        source: 'pet-service',
        target: 'pet-repository',
    },
    {
        id: 'e6',
        source: 'visit-service',
        target: 'visit-repository',
    },
    {
        id: 'e7',
        source: 'owner-service',
        target: 'owner-repository',
    },

    {
        id: 'e8',
        source: 'pet-service',
        target: 'visit-repository',
    },
    {
        id: 'e9',
        source: 'owner-service',
        target: 'visit-service',
        violation: true,
    },

    {
        id: 'e10',
        source: 'pet-repository',
        target: 'datasource',
    },
    {
        id: 'e11',
        source: 'visit-repository',
        target: 'transaction-manager',
    },
    {
        id: 'e12',
        source: 'owner-repository',
        target: 'cache-manager',
    },

    {
        id: 'e13',
        source: 'datasource',
        target: 'mysql',
    },
    {
        id: 'e14',
        source: 'transaction-manager',
        target: 'mysql',
    },
    {
        id: 'e15',
        source: 'cache-manager',
        target: 'email',
    },
];

export const selectedModule = {
    name: 'OwnerService',
    package: 'com.petclinic.owner',
    risk: 'HIGH',
    score: 81,
    rank: '2 / 38',
    trend: '+12%',
    lastAnalyzed: 'May 12, 2025',
    firstDetected: 'Apr 28, 2025',
};

export const keyIssues = [
    {
        name: 'Layer Violation',
        count: 1,
        level: 'High',
    },
    {
        name: 'High Coupling',
        count: 7,
        level: 'High',
    },
    {
        name: 'High Complexity',
        count: 5,
        level: 'Medium',
    },
    {
        name: 'High Code Churn',
        count: 3,
        level: 'Medium',
    },
];

export const topDependencies = [
    {
        name: 'VisitService',
        level: 'Strong',
    },
    {
        name: 'OwnerRepository',
        level: 'Strong',
    },
    {
        name: 'PetService',
        level: 'Medium',
    },
    {
        name: 'EmailService',
        level: 'Weak',
    },
    {
        name: 'TransactionManager',
        level: 'Weak',
    },
];

export const layerDistribution = [
    {
        name: 'Presentation',
        value: 14,
        percent: '14.3%',
    },
    {
        name: 'Service',
        value: 35,
        percent: '35.7%',
    },
    {
        name: 'Repository',
        value: 22,
        percent: '22.4%',
    },
    {
        name: 'Infrastructure',
        value: 15,
        percent: '15.3%',
    },
    {
        name: 'External',
        value: 12,
        percent: '12.2%',
    },
];

export const layerSummary = [
    {
        name: 'Presentation Layer',
        modules: 14,
        issues: 2,
    },
    {
        name: 'Service Layer',
        modules: 35,
        issues: 6,
    },
    {
        name: 'Repository Layer',
        modules: 22,
        issues: 3,
    },
    {
        name: 'Infrastructure Layer',
        modules: 15,
        issues: 1,
    },
    {
        name: 'External Systems',
        modules: 12,
        issues: 0,
    },
];

export const violationDistribution = [
    {
        name: 'Layer Violations',
        value: 4,
        percent: '57%',
    },
    {
        name: 'Circular Dependencies',
        value: 2,
        percent: '29%',
    },
    {
        name: 'Dependency Direction',
        value: 1,
        percent: '14%',
    },
];

export const architectureChanges = [
    {
        text: 'OwnerService depends on VisitService',
        time: '2h ago',
        type: 'red',
    },
    {
        text: 'New dependency: EmailService',
        time: '5h ago',
        type: 'orange',
    },
    {
        text: 'Layer violation introduced in PaymentService',
        time: '1d ago',
        type: 'red',
    },
    {
        text: 'Circular dependency resolved in UserService',
        time: '2d ago',
        type: 'green',
    },
];