import { createContext, useCallback, useContext, useEffect, useState } from "react";

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
      .then((data) => setResult({ key, data, error: null }))
      .catch((error) => {
        if (error.name !== "AbortError") setResult({ key, data: null, error: error.message });
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
