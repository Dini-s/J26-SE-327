import { useState } from "react";
import { useRefresh } from "../api/c4";
import {
  Menu,
  RefreshCw,
  Bell,
  
} from "lucide-react";

const TopHeader = ({
  title = "Research Overview",
  onMenuClick,
  sidebarCollapsed = false,
}) => {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const { bump } = useRefresh();

  const handleRefresh = () => {
    setRefreshing(true);
    bump();

    setTimeout(() => {
      setRefreshing(false);
    }, 1000);
  };

  return (
    <header
      className="
        sticky top-0 z-40
        flex h-[72px]
        items-center justify-between
        border-b border-slate-200
        bg-white/95
        px-4
        backdrop-blur-md
        sm:px-6
        lg:px-8
      "
    >
      <div className="flex min-w-0 items-center gap-3">
        {/* Mobile / Sidebar Toggle */}
        <button
          type="button"
          onClick={onMenuClick}
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="
            flex h-9 w-9
            shrink-0
            items-center justify-center
            rounded-lg
            text-slate-500
            transition-all duration-200
            hover:bg-slate-100
            hover:text-blue-600
            focus:outline-none
            focus:ring-2
            focus:ring-blue-500/30
          "
        >
          <Menu size={20} />
        </button>

        {/* Page Title */}
        <div className="min-w-0">
          <h1
            className="
              truncate
              text-base
              font-semibold
              text-slate-900
              sm:text-lg
            "
          >
            ASPIRE
          </h1>

          <p className="hidden text-xs text-slate-400 sm:block italic">
            AI Software platform for Intelligence, Reasoning & Evolution
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        {/* Date & Time */}
        <div className="hidden lg:block">
          <div className="text-right">
            <p className="text-xs font-medium text-slate-700">May 28, 2026</p>

            <p className="text-[10px] text-slate-400">10:24 AM</p>
          </div>
        </div>

        {/* Vertical Divider */}
        <div className="hidden h-8 w-px bg-slate-200 lg:block" />

        {/* Refresh Button */}
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          aria-label="Refresh dashboard"
          className="
            flex h-9 w-9
            items-center justify-center
            rounded-lg
            border border-slate-200
            bg-white
            text-slate-500
            transition-all duration-200
            hover:border-blue-200
            hover:bg-blue-50
            hover:text-blue-600
            disabled:cursor-not-allowed
            disabled:opacity-70
          "
        >
          <RefreshCw size={17} className={refreshing ? "animate-spin" : ""} />
        </button>

        {/* Notifications */}
        <button
          type="button"
          aria-label="Notifications"
          className="
            relative
            flex h-9 w-9
            items-center justify-center
            rounded-lg
            text-slate-500
            transition-all duration-200
            hover:bg-slate-100
            hover:text-blue-600
          "
        >
          <Bell size={19} />

          {/* Notification Badge */}
          <span
            className="
              absolute
              right-1
              top-1
              flex h-4 w-4
              items-center justify-center
              rounded-full
              bg-red-500
              text-[9px]
              font-bold
              text-white
              ring-2
              ring-white
            "
          >
            3
          </span>
        </button>

        {/* Divider */}
        <div className="hidden h-8 w-px bg-slate-200 sm:block" />
      </div>
    </header>
  );
};

export default TopHeader;
