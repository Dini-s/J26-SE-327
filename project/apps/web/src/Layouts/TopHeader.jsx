import { useEffect, useRef, useState } from "react";
import { useNotifications, useProject, useRefresh } from "../api/c4";
import {
  Menu,
  RefreshCw,
  Bell,
  Check,
  X,
} from "lucide-react";

let audioContext;

function playNotificationChime() {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) return;
  audioContext ??= new AudioContextClass();
  const context = audioContext;
  const play = () => {
    [880, 1175].forEach((frequency, index) => {
      const start = context.currentTime + index * 0.14;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.1, start + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.25);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(start);
      oscillator.stop(start + 0.25);
    });
  };
  if (context.state === "suspended") context.resume().then(play, () => {});
  else play();
}

const eventLabel = (notification) => (notification.event === "trace_decayed" ? "Trace link broken" : "Code change received");
const eventDetail = (notification) => notification.requirementId || notification.project || notification.message || "A Redis event was received.";

const TopHeader = ({
  title = "Research Overview",
  onMenuClick,
  sidebarCollapsed = false,
}) => {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const notificationRef = useRef(null);
  const { bump } = useRefresh();
  const { project } = useProject();
  const { notifications, connected, clear } = useNotifications(project, {
    onLive: (notification) => {
      playNotificationChime();
      setToast(notification);
    },
  });
  const [seen, setSeen] = useState(0);
  const unread = Math.max(0, notifications.length - seen);

  useEffect(() => {
    if (!notificationsOpen) return;
    const closeOnOutside = (event) => {
      if (!notificationRef.current?.contains(event.target)) setNotificationsOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setNotificationsOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [notificationsOpen]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const openNotifications = () => {
    setToast(null);
    setNotificationsOpen(true);
    setSeen(notifications.length);
  };

  const toggleNotifications = () => {
    if (notificationsOpen) setNotificationsOpen(false);
    else openNotifications();
  };

  const clearNotifications = () => {
    clear();
    setSeen(0);
    setToast(null);
  };

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
        <div className="relative" ref={notificationRef}>
          <button
            type="button"
            aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
            aria-expanded={notificationsOpen}
            onClick={toggleNotifications}
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
            {unread > 0 && (
              <span
                className="
                  absolute
                  right-1
                  top-1
                  flex h-4 min-w-4 px-1
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
                {unread > 99 ? "99+" : unread}
              </span>
            )}
          </button>

          {toast && !notificationsOpen && (
            <div
              role="status"
              className="
                absolute right-0 top-12 z-50
                flex w-[min(20rem,calc(100vw-2rem))] items-start gap-3
                rounded-xl border border-red-200 bg-white p-3
                shadow-xl
              "
            >
              <button type="button" onClick={openNotifications} className="flex min-w-0 flex-1 items-start gap-3 text-left">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-600">
                  <Bell size={15} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-semibold text-slate-900">{eventLabel(toast)}</span>
                  <span className="mt-0.5 block break-words text-[11px] leading-5 text-slate-500">{eventDetail(toast)}</span>
                </span>
              </button>
              <button type="button" onClick={() => setToast(null)} className="rounded p-0.5 text-slate-400 hover:bg-slate-100" aria-label="Dismiss notification">
                <X size={13} />
              </button>
            </div>
          )}

          {notificationsOpen && (
            <div role="dialog" aria-label="Notifications" className="absolute right-0 top-12 z-50 flex max-h-[min(28rem,70vh)] w-[min(22rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Notifications</p>
                  <p className={`mt-0.5 text-[11px] ${connected ? "text-emerald-600" : "text-amber-600"}`}>{connected ? "Live notifications" : "Waiting for notification service…"}</p>
                </div>
                <button type="button" onClick={() => setNotificationsOpen(false)} className="rounded p-1 text-slate-400 hover:bg-slate-100" aria-label="Close notifications"><X size={15} /></button>
              </div>
              <div className="min-h-0 flex-1 overflow-auto">
                {!notifications.length ? <p className="px-4 py-10 text-center text-xs text-slate-400">No broken-link notifications yet.</p> : notifications.map((notification) => (
                  <div key={notification.id} className="flex gap-3 border-b border-slate-100 px-4 py-3.5 last:border-0">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-600"><Check size={14} /></span>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-800">{eventLabel(notification)}</p>
                      <p className="mt-0.5 break-words text-[11px] leading-5 text-slate-500">{eventDetail(notification)}</p>
                      <time className="mt-1 block text-[10px] text-slate-400">{notification.timestamp || "Just now"}{notification.delivered === false ? " · Redis delivery unavailable" : ""}</time>
                    </div>
                  </div>
                ))}
              </div>
              {notifications.length > 0 && (
                <div className="border-t border-slate-100 px-4 py-2.5 text-right">
                  <button type="button" onClick={clearNotifications} className="rounded-md px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Clear all</button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="hidden h-8 w-px bg-slate-200 sm:block" />
      </div>
    </header>
  );
};

export default TopHeader;
