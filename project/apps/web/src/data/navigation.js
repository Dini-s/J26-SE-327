import {
  Home,
  Network,
  BarChart3,
  FileText,
  Activity,
  Settings,
  Info,
  FolderGit2,
  ShieldAlert,
  Boxes,
  GitBranch,
  Bug,
  TestTube2,
  ChartNoAxesCombined,
} from "lucide-react";

export const navigation = [
  {
    type: "item",
    label: "Research Overview",
    path: "/overview",
    icon: Home,
  },

  {
    type: "section",
    label: "INTELLIGENCE COMPONENTS",
  },

  // =========================================================
  // COMPONENT 1
  // =========================================================
  {
    type: "item",
    label: "Requirement Intelligence",
    number: "1",
    numberColor: "green",
    path: "/requirement",
    icon: FileText,
    expandable: true,

    children: [
      {
        label: "Overview",
        path: "/requirement",
      },

      {
        label: "Sources & Findings",
        path: "/requirement/sources",
      },

      {
        label: "Review Queue",
        path: "/requirement/review",
      },

      {
        label: "Task Drafts",
        path: "/requirement/drafts",
      },
    ],
  },

  // =========================================================
  // COMPONENT 2
  // =========================================================
  {
    type: "item",
    label: "Repository Intelligence",
    number: "2",
    numberColor: "blue",
    path: "/repository",
    icon: FolderGit2,
    expandable: true,

    children: [
      {
        label: "Overview",
        path: "/repository",
      },

      {
        label: "Repositories",
        path: "/repository/repositories",
        icon: FolderGit2,
      },

      {
        label: "Evalution & Metrics",
        path: "/repository/evalution",
        icon: ChartNoAxesCombined,
      },

      {
        label: "Risk & Architecture",
        expandable: true,
        icon: ShieldAlert,

        children: [
          {
            label: "Risk Models",
            path: "/repository/risk-models",
            icon: ShieldAlert,
          },

          {
            label: "Architecture Visualization",
            path: "/repository/architecture",
            icon: Boxes,
          },

          {
            label: "Architecture Issues",
            path: "/repository/issues",
            icon: Bug,
          },

          {
            label: "Dependencies",
            path: "/repository/dependencies",
            icon: GitBranch,
          },
        ],
      },
    ],
  },

  // =========================================================
  // COMPONENT 3
  // QUALITY & TESTING INTELLIGENCE
  // =========================================================
  {
    type: "item",
    label: "Quality & Testing Intelligence",
    number: "3",
    numberColor: "purple",
    path: "/quality",
    icon: TestTube2,
    expandable: true,

    children: [
      {
        label: "Overview",
        path: "/quality",
      },

      {
        label: "Requirements",
        path: "/quality/requirements",
      },

      {
        label: "Requirement Details",
        path: "/quality/requirement-details/REQ-014",

        // Makes Requirement Details remain selected
        // for REQ-014, REQ-021 and future requirements.
        activePrefix: "/quality/requirement-details/",
      },
    ],
  },

  // =========================================================
  // COMPONENT 4
  // =========================================================
  {
    type: "item",
    label: "Traceability Intelligence",
    number: "4",
    numberColor: "orange",
    path: "/traceability",
    icon: GitBranch,
  },

  // =========================================================
  // SHARED LAYER
  // =========================================================
  {
    type: "section",
    label: "SHARED LAYER",
  },

  {
    type: "item",
    label: "Unified Software Knowledge Graph",
    path: "/knowledge-graph",
    icon: Network,
  },

  {
    type: "item",
    label: "Cross-Component Insights",
    path: "/insights",
    icon: BarChart3,
  },

  // =========================================================
  // SHARED REPORTS
  // =========================================================
  {
    type: "item",
    label: "Reports & Analytics",
    path: "/reports",
    icon: FileText,
    expandable: true,

    children: [
      {
        label: "QA Reports and Analytics",
        path: "/reports/quality",
      },
    ],
  },

  {
    type: "item",
    label: "Activity Monitor",
    path: "/activity",
    icon: Activity,
  },

  // =========================================================
  // SYSTEM
  // =========================================================
  {
    type: "section",
    label: "SYSTEM",
  },

  {
    type: "item",
    label: "Settings",
    path: "/settings",
    icon: Settings,
  },

  {
    type: "item",
    label: "About ASPIRE",
    path: "/about",
    icon: Info,
  },
];
