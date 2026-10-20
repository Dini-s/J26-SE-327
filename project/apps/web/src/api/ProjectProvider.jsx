import { useCallback, useMemo, useState } from "react";
import { ProjectContext, RefreshContext, useApi } from "./c4";

const KEY = "c4.project";
const read = () => {
  try {
    return new URLSearchParams(window.location.search).get("project") || window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
};

function Inner({ children }) {
  const api = useApi("/api/projects", { pollMs: 30000 });
  const [wanted, setWanted] = useState(read);
  const projects = useMemo(() => (Array.isArray(api.data) ? api.data : []), [api.data]);
  const names = projects.map((p) => p.project);
  const project = names.includes(wanted) ? wanted : names.includes("spring-petclinic") ? "spring-petclinic" : names[0] || null;

  const setProject = useCallback((name) => {
    try {
      if (name) window.localStorage.setItem(KEY, name);
      else window.localStorage.removeItem(KEY);
    } catch {
      /* storage unavailable */
    }
    setWanted(name);
  }, []);

  const value = useMemo(() => ({ projects, project, setProject, error: api.error, loading: api.loading }), [projects, project, setProject, api.error, api.loading]);
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

/** Wraps the dashboard: one selected repository and one refresh signal shared by the sidebar, the top bar and the C4 pages. */
export default function ProjectProvider({ children }) {
  const [tick, setTick] = useState(0);
  const refresh = useMemo(() => ({ tick, bump: () => setTick((v) => v + 1) }), [tick]);
  return (
    <RefreshContext.Provider value={refresh}>
      <Inner>{children}</Inner>
    </RefreshContext.Provider>
  );
}
