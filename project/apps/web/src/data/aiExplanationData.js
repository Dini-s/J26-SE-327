export const aiExplanationData = {
    module: {
        name: "PaymentService",
        package: "com.petclinic.payment.service",
        driftProbability: "0.89",
        riskLevel: "High",
        architectureHealth: "42",
        confidence: 92,
        analysisId: "AN-20250512-0945",
        model: "HRIM v1.3.2",
    },

    factors: [
        {
            title: "High Code Churn",
            description:
                "This module has been modified 45 times in the last 6 months, which is significantly higher than other modules.",
            contribution: "+0.28",
            percentage: "31%",
            color: "red",
            icon: "churn",
        },
        {
            title: "High Coupling",
            description:
                "It depends on 8 modules and is depended on by 5 modules, creating a high impact zone.",
            contribution: "+0.24",
            percentage: "27%",
            color: "green",
            icon: "coupling",
        },
        {
            title: "Complexity Increase",
            description:
                "Cyclomatic complexity has increased by 42% compared to the previous analysis.",
            contribution: "+0.18",
            percentage: "20%",
            color: "purple",
            icon: "complexity",
        },
        {
            title: "Instability",
            description:
                "Instability value is 0.82, indicating the module is more dependent on other unstable modules.",
            contribution: "+0.12",
            percentage: "13%",
            color: "orange",
            icon: "instability",
        },
        {
            title: "Architecture Issues",
            description:
                "2 architecture violations detected: Layer Violation and Circular Dependency.",
            contribution: "+0.07",
            percentage: "9%",
            color: "pink",
            icon: "issues",
        },
    ],

    recommendations: [
        {
            number: 1,
            title: "Reduce Coupling",
            description:
                "Extract payment gateway integrations into a separate module (PaymentGatewayAdapter) to reduce dependencies.",
            priority: "High",
            tags: ["Refactoring", "Architecture"],
        },
        {
            number: 2,
            title: "Simplify Complex Methods",
            description:
                "Break down methods in PaymentServiceImpl.java (lines 120–210) that have high cyclomatic complexity.",
            priority: "High",
            tags: ["Code Quality", "Maintainability"],
        },
        {
            number: 3,
            title: "Resolve Architecture Violations",
            description:
                "Move direct repository calls from service layer to repository layer to fix Layer Violation.",
            priority: "High",
            tags: ["Architecture", "Compliance"],
        },
        {
            number: 4,
            title: "Add Unit Tests",
            description:
                "Increase unit test coverage from 58% to at least 80% for critical business logic.",
            priority: "Medium",
            tags: ["Testing", "Quality"],
        },
        {
            number: 5,
            title: "Monitor Changes",
            description:
                "This module has high churn. Consider stricter code review and change monitoring.",
            priority: "Low",
            tags: ["Process", "Governance"],
        },
    ],

    impact: [
        {
            label: "Affects",
            value: "5 modules",
            description: "High propagation impact",
            icon: "modules",
        },
        {
            label: "Introduced in",
            value: "Commit a1b2c3d",
            description: "3 months ago",
            icon: "commit",
        },
        {
            label: "Last Modified",
            value: "May 10, 2025",
            description: "2 days ago",
            icon: "edit",
        },
        {
            label: "Risk Trend",
            value: "Increasing",
            description: "",
            icon: "trend",
        },
    ],

    relatedIssues: [
        {
            title: "Layer Violation",
            description: "Service layer accessing repository directly",
            severity: "High",
        },
        {
            title: "Circular Dependency",
            description: "PaymentService ↔ OrderService",
            severity: "High",
        },
    ],

    relatedModules: [
        {
            name: "OrderService",
            risk: "0.81",
            severity: "High",
        },
        {
            name: "NotificationService",
            risk: "0.74",
            severity: "High",
        },
        {
            name: "EmailService",
            risk: "0.69",
            severity: "Medium",
        },
    ],

    history: [
        {
            date: "May 12, 2025 09:45 AM",
            model: "HRIM v1.3.2",
            severity: "High",
        },
        {
            date: "May 05, 2025 09:30 AM",
            model: "HRIM v1.3.1",
            severity: "High",
        },
        {
            date: "Apr 28, 2025 09:15 AM",
            model: "HRIM v1.3.0",
            severity: "Medium",
        },
        {
            date: "Apr 21, 2025 09:00 AM",
            model: "HRIM v1.2.8",
            severity: "Medium",
        },
    ],
};