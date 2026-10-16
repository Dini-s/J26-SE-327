import { useMemo } from "react";
import { natural, shortName } from "./utils";

/** Which links and nodes the current filters leave visible. Shared by the graph, the matrix and the side panel. */
export function useVisible(links, orphans, filters) {
  return useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    const visible = links.filter(
      (l) => (l.status === "decayed" ? filters.decayed : filters.verified) && (l.confidence ?? 0) >= filters.minConfidence,
    );
    const reqIds = new Set(visible.map((l) => l.requirement));
    if (filters.orphans) orphans.forEach((o) => reqIds.add(o.requirement));
    const orphanIds = new Set(orphans.map((o) => o.requirement));
    const degree = new Map();
    visible.forEach((l) => degree.set(l.code, (degree.get(l.code) || 0) + 1));
    const reqs = [...reqIds].sort(natural);
    const codes = [...degree.keys()].sort((a, b) => degree.get(b) - degree.get(a) || natural(shortName(a), shortName(b)));
    const matches = (id) => !q || String(id).toLowerCase().includes(q) || shortName(id).toLowerCase().includes(q);
    return { visible, reqs, codes, orphanIds, degree, matches, searching: Boolean(q) };
  }, [links, orphans, filters]);
}
