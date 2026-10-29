import React from "react";

const styles = {
  success: {
    wrapper: "bg-emerald-50 text-emerald-600",
    dot: "bg-emerald-500",
  },

  warning: {
    wrapper: "bg-orange-50 text-orange-600",
    dot: "bg-orange-500",
  },

  danger: {
    wrapper: "bg-red-50 text-red-600",
    dot: "bg-red-500",
  },

  info: {
    wrapper: "bg-blue-50 text-blue-600",
    dot: "bg-blue-500",
  },
};

const StatusBadge = ({ children, type = "success" }) => {
  const style = styles[type] || styles.success;

  return (
    <span
      className={`
        inline-flex items-center gap-1.5
        rounded-full
        px-2.5 py-1
        text-[10px]
        font-medium
        ${style.wrapper}
      `}
    >
      <span
        className={`
          h-1.5 w-1.5
          rounded-full
          ${style.dot}
        `}
      />

      {children}
    </span>
  );
};

export default StatusBadge;
