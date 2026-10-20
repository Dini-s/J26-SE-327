import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

/** GET a JSON document from the C4 Python API (proxied by Vite under /api). */
export async function getJson(path, signal) {
  const res = await fetch(path, { headers: { Accept: "application/json" }, signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* the body was not JSON */
    }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/** POST JSON to the C4 API. The API only accepts requests that carry this header and come from the page itself. */
export async function postJson(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Requested-With": "c4-web" },
    body: JSON.stringify(body || {}),
  });
  let data = {};
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

/** Bumped by the refresh button in the top bar; every useApi on the page reloads when it changes. */
export const RefreshContext = createContext({ tick: 0, bump: () => {} });
/** The repository selected in the sidebar: {projects, project, setProject, error, loading}. */
export const ProjectContext = createContext({ projects: [], project: null, setProject: () => {}, error: null, loading: false });

/** Load `path` and keep {data, error, loading}; call reload() to fetch again. A falsy path loads nothing. */
export function useApi(path, { pollMs = 0 } = {}) {
  const [localTick, setTick] = useState(0);
  const { tick: globalTick } = useContext(RefreshContext);
  const tick = `${localTick}.${globalTick}`;
  const [result, setResult] = useState({ key: null, data: null, error: null });
  const key = path ? `${path}#${tick}` : null;

  useEffect(() => {
    if (!path) return undefined;
    const controller = new AbortController();
    getJson(path, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setResult({ key, data, error: null }); })
      .catch((error) => {
        if (!controller.signal.aborted && error.name !== "AbortError") setResult({ key, data: null, error: error.message });
      });
    return () => controller.abort();
  }, [path, key]);

  useEffect(() => {
    if (!path || !pollMs) return undefined;
    const timer = setInterval(() => setTick((value) => value + 1), pollMs);
    return () => clearInterval(timer);
  }, [path, pollMs]);

  const finished = key !== null && result.key === key;
  // keep showing the previous answer of the same path while a refresh is running
  const sameRequest = path && result.key !== null && result.key.startsWith(`${path}#`);
  const reload = useCallback(() => setTick((value) => value + 1), []);
  return {
    data: sameRequest ? result.data : null,
    error: finished ? result.error : null,
    loading: Boolean(path) && !finished,
    reload,
  };
}

/** The project (repository / dataset) chosen in the sidebar. */
export const useProject = () => useContext(ProjectContext);
export const useRefresh = () => useContext(RefreshContext);

const CLEARED_KEY = "c4-notifications-cleared-at";

function readClearedAt() {
  try {
    return Number(localStorage.getItem(CLEARED_KEY)) || 0;
  } catch {
    return 0;
  }
}

function isCleared(item, clearedAt) {
  const time = Date.parse(item.timestamp);
  return Boolean(clearedAt) && Number.isFinite(time) && time <= clearedAt;
}

export function useNotifications(project, { onLive } = {}) {
  const [notifications, setNotifications] = useState([]);
  const [connected, setConnected] = useState(false);
  const clearedAt = useRef(readClearedAt());
  const onLiveRef = useRef(onLive);
  useEffect(() => {
    onLiveRef.current = onLive;
  });
  useEffect(() => {
    let active = true;
    const merge = (items) => {
      if (!active || !Array.isArray(items)) return;
      setNotifications((current) => {
        const historyItems = items
          .filter((item) => !isCleared(item, clearedAt.current))
          .map((item, index) => ({ ...item, id: `history-${item.timestamp}-${index}` }));
        const merged = [...current, ...historyItems].filter((item, index, all) =>
          all.findIndex((candidate) => candidate.event === item.event && candidate.timestamp === item.timestamp && candidate.requirementId === item.requirementId) === index
        );
        return merged.sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || ""))).slice(0, 40);
      });
    };
    const loadRecent = () => getJson("/api/notifications/recent?limit=40")
      .then((items) => {
        if (active) {
          setConnected(true);
          merge(items);
        }
      })
      .catch(() => {
        const query = project ? `?project=${encodeURIComponent(project)}` : "";
        return getJson(`/api/change-runs${query}`)
          .then((data) => {
            const items = (data.runs || []).flatMap((run) =>
              (run.rechecks || [])
                .filter((check) => check.broken)
                .map((check) => ({
                  event: "trace_decayed",
                  requirementId: check.requirement,
                  codeEntityId: check.target,
                  previousConfidence: check.before,
                  newConfidence: check.after,
                  timestamp: run.finished || run.started,
                  project: run.project,
                  delivered: run.messages?.some((message) => message.delivered) ?? false,
                }))
            );
            if (active) {
              setConnected(true);
              merge(items);
            }
          })
          .catch(() => {
            if (active) setConnected(false);
          });
      });
    loadRecent();
    const poll = window.setInterval(loadRecent, 5000);
    const stream = new EventSource("/api/notifications");
    const liveKeys = new Set();
    const receive = (event) => {
      let value;
      try {
        value = JSON.parse(event.data);
      } catch {
        return;
      }
      if (isCleared(value, clearedAt.current)) return;
      const key = `${value.event}|${value.timestamp}|${value.requirementId}`;
      if (liveKeys.has(key)) return;
      liveKeys.add(key);
      const next = { ...value, id: `${Date.now()}-${Math.random()}` };
      setNotifications((current) => [next, ...current].slice(0, 40));
      onLiveRef.current?.(next);
    };
    const channels = ["trace_decayed", "code_changed"];
    channels.forEach((channel) => stream.addEventListener(channel, receive));
    stream.onopen = () => setConnected(true);
    stream.onerror = () => {
      setConnected(false);
      loadRecent();
    };
    return () => {
      active = false;
      window.clearInterval(poll);
      channels.forEach((channel) => stream.removeEventListener(channel, receive));
      stream.close();
    };
  }, [project]);
  const clear = useCallback(() => {
    const now = Date.now();
    clearedAt.current = now;
    try {
      localStorage.setItem(CLEARED_KEY, String(now));
    } catch {
      /* storage unavailable: the clear still holds for this page session */
    }
    setNotifications([]);
  }, []);
  return { notifications, connected, clear };
}
