import React from "react";
import {
  AlertTriangle,
  Boxes,
  Folder,
  Link2,
  Package,
  Layers,
} from "lucide-react";

const icons = {
  link: Link2,
  layers: Layers,
  warning: AlertTriangle,
  folder: Folder,
  package: Package,
};

const styles = {
  High: "bg-red-50 text-red-500",
  Medium: "bg-orange-50 text-orange-500",
  Low: "bg-blue-50 text-blue-500",
};

const IssueIcon = ({ type, severity }) => {
  const Icon = icons[type] || Boxes;

  return (
    <div
      className={`
        flex h-10 w-10 shrink-0
        items-center justify-center
        rounded-lg
        ${styles[severity]}
      `}
    >
      <Icon size={19} />
    </div>
  );
};

export default IssueIcon;
