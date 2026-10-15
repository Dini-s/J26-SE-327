
import {
  ChevronLeft,
  ChevronRight,
  Database,
} from "lucide-react";


import SidebarItem from "./SidebarItem";
import SidebarSection from "./SidebarSection";
import { navigation } from "../data/navigation";

const Sidebar = ({
  collapsed,
  onToggle,
}) => {
  return (
    <aside
      className={`
        fixed left-0 top-0 z-50
        flex h-screen
        flex-col
        border-r border-white/10
        bg-[#06152D]
        text-white
        shadow-2xl shadow-black/20

        transition-all
        duration-300
        ease-in-out

        ${collapsed ? "w-[72px]" : "w-[260px]"}
      `}
    >

     
      <div
        className={`
          flex h-[76px]
          shrink-0
          items-center
          border-b border-white/10
          ${collapsed ? "justify-center" : "px-5"}
        `}
      >

        {/* Logo Icon */}
        <div
          className="
            flex h-10 w-10
            shrink-0
            items-center justify-center
            rounded-xl
            border border-blue-400/30
            bg-blue-500/10
          "
        >
          <span className="text-xl">
            ◈
          </span>
        </div>

        {/* Brand */}
        {!collapsed && (
          <div className="ml-3 min-w-0">
            <h1 className="text-lg font-bold tracking-wide">
              ASPIRE
            </h1>

            <p className="truncate text-[8px] text-slate-400">
              Unified Software Intelligence
            </p>
          </div>
        )}

      </div>

    
      <div className="flex-1 overflow-y-auto px-2 py-3 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10">

        {navigation.map((item, index) => {

          if (item.type === "section") {
            return (
              <SidebarSection
                key={`${item.label}-${index}`}
                label={item.label}
                collapsed={collapsed}
              />
            );
          }

          return (
            <div
              key={`${item.label}-${index}`}
              className="mb-0.5"
            >
              <SidebarItem
                item={item}
                collapsed={collapsed}
              />
            </div>
          );
        })}

      </div>

   
      {!collapsed && (
        <div className="shrink-0 border-t border-white/10 p-3">

          <div className="rounded-xl border border-blue-400/20 bg-blue-500/5 p-3">

            <p className="mb-2 text-[9px] font-medium uppercase tracking-wide text-slate-500">
              Active Repository
            </p>

            <div className="flex items-center justify-between">

              <div className="flex min-w-0 items-center gap-2">

                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-blue-500/10">
                  <Database
                    size={14}
                    className="text-blue-400"
                  />
                </div>

                <span className="truncate text-xs font-medium text-slate-200">
                  Spring PetClinic
                </span>

              </div>

              <ChevronLeft
                size={13}
                className="shrink-0 text-slate-400"
              />

            </div>

            <div className="my-3 h-px bg-white/10" />

            <p className="text-[9px] text-slate-500">
              Last Analysis
            </p>

            <div className="mt-1 flex items-center justify-between">

              <span className="text-[10px] text-slate-300">
                May 12, 2026 • 09:45 AM
              </span>

              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50" />

            </div>

          </div>

        </div>
      )}

    
      <button
        type="button"
        onClick={onToggle}
        aria-label={
          collapsed
            ? "Expand sidebar"
            : "Collapse sidebar"
        }
        className={`
          absolute
          -right-3
          bottom-6
          flex h-7 w-7
          items-center justify-center
          rounded-full
          border border-white/10
          bg-[#102542]
          text-slate-300
          shadow-lg
          transition-all
          hover:bg-blue-600
          hover:text-white
        `}
      >
        {collapsed ? (
          <ChevronRight size={14} />
        ) : (
          <ChevronLeft size={14} />
        )}
      </button>

    </aside>
  );
};

export default Sidebar;