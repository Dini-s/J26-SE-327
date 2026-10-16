export const issueSummary = {
    total: 12,
    high: 4,
    architectureHealth: 72,
};

export const issues = [
    {
        id: 'ISS-001',
        title: 'Circular Dependency',
        subtitle:
            'petclinic.order ↔ petclinic.payment',
        description:
            'Circular dependency detected between OrderService and PaymentService.',
        severity: 'High',
        status: 'Open',
        type: 'Design Violation',
        layer: 'Service',
        confidence: 92,
        date: 'May 12, 2025',
        icon: 'link',

        summary:
            'OrderService and PaymentService have a circular dependency, creating tight coupling and increasing maintenance risk.',

        detected: 'May 12, 2025 09:32 AM',

        dependency: {
            source: 'OrderService',
            sourcePackage: 'petclinic.order',
            target: 'PaymentService',
            targetPackage: 'petclinic.payment',
        },

        evidence: {
            file: 'OrderService.java',
            lines: [
                '@Autowired',
                'private PaymentService paymentService;',
                '',
                'public void processOrder(Order order) {',
                '    paymentService.processPayment(order);',
                '}',
            ],
        },

        recommendations: [
            'Apply dependency inversion using an interface.',
            'Introduce a mediator or event-driven approach.',
            'Refactor to break the circular dependency.',
        ],
    },

    {
        id: 'ISS-002',
        title: 'Layer Violation',
        subtitle:
            'petclinic.web → petclinic.repository',
        description:
            'Web layer is directly accessing repository layer, violating layered architecture.',
        severity: 'High',
        status: 'Open',
        type: 'Architecture',
        layer: 'Presentation',
        confidence: 89,
        date: 'May 12, 2025',
        icon: 'layers',

        summary:
            'The presentation layer directly accesses repository components instead of going through the service layer.',

        detected: 'May 12, 2025 09:18 AM',

        dependency: {
            source: 'WebController',
            sourcePackage: 'petclinic.web',
            target: 'PetRepository',
            targetPackage: 'petclinic.repository',
        },

        evidence: {
            file: 'WebController.java',
            lines: [
                '@Autowired',
                'private PetRepository repository;',
                '',
                'public Pet findPet(Long id) {',
                '    return repository.findById(id);',
                '}',
            ],
        },

        recommendations: [
            'Move repository access into the service layer.',
            'Expose a service interface to controllers.',
            'Enforce architectural layer boundaries.',
        ],
    },

    {
        id: 'ISS-003',
        title: 'God Class Detected',
        subtitle:
            'petclinic.owner.OwnerService (42 methods)',
        description:
            'Class with too many responsibilities found.',
        severity: 'High',
        status: 'Open',
        type: 'Code Smell',
        layer: 'Service',
        confidence: 87,
        date: 'May 12, 2025',
        icon: 'warning',

        summary:
            'OwnerService contains too many responsibilities and should be decomposed into smaller cohesive services.',

        detected: 'May 12, 2025 08:54 AM',

        recommendations: [
            'Split responsibilities into focused services.',
            'Apply the Single Responsibility Principle.',
            'Move unrelated operations into dedicated components.',
        ],
    },

    {
        id: 'ISS-004',
        title: 'High Coupling',
        subtitle:
            'petclinic.pet ↔ petclinic.visit',
        description:
            'Coupling between PetService and VisitService is too high (0.78).',
        severity: 'Medium',
        status: 'Open',
        type: 'Quality Risk',
        layer: 'Service',
        confidence: 76,
        date: 'May 12, 2025',
        icon: 'link',

        summary:
            'PetService and VisitService have strong coupling that may make future changes more difficult.',

        detected: 'May 12, 2025 08:42 AM',

        recommendations: [
            'Reduce direct service-to-service dependencies.',
            'Introduce an abstraction between the services.',
            'Review shared domain responsibilities.',
        ],
    },

    {
        id: 'ISS-005',
        title: 'Missing Dependency Inversion',
        subtitle:
            'petclinic.payment.impl',
        description:
            'Concrete implementation used instead of interface.',
        severity: 'Medium',
        status: 'Open',
        type: 'Design Violation',
        layer: 'Service',
        confidence: 78,
        date: 'May 12, 2025',
        icon: 'folder',

        summary:
            'A concrete implementation is referenced directly, reducing flexibility and testability.',

        detected: 'May 12, 2025 08:31 AM',

        recommendations: [
            'Introduce an interface for the dependency.',
            'Inject the abstraction rather than the implementation.',
        ],
    },

    {
        id: 'ISS-006',
        title: 'Large Package',
        subtitle:
            'petclinic.controller',
        description:
            'Package contains too many classes (24). Consider refactoring.',
        severity: 'Low',
        status: 'Open',
        type: 'Maintainability',
        layer: 'Presentation',
        confidence: 72,
        date: 'May 11, 2025',
        icon: 'package',

        summary:
            'The package contains a large number of classes and may benefit from decomposition.',

        detected: 'May 11, 2025 04:15 PM',

        recommendations: [
            'Split the package by responsibility.',
            'Group related functionality into smaller packages.',
        ],
    },
];

export const recommendations = [
    'Apply dependency inversion using an interface.',
    'Introduce a mediator or event-driven approach.',
    'Refactor to break the circular dependency.',
];