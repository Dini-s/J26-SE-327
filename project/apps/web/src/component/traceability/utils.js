/** "spring-petclinic:src/main/java/.../Owner.java" -> "Owner.java" */
export const shortName = (id) => String(id ?? "").split(/[/:]/).pop();

export const natural = (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true });

export const pct = (value) => `${Math.round((value ?? 0) * 100)}%`;

export const cx = (...parts) => parts.filter(Boolean).join(" ");

/** Separate graph namespace from a repository-relative path for display only. */
export function codeLocation(id) {
  const raw = String(id ?? "").replace(/\\/g, "/");
  const colon = raw.indexOf(":");
  const namespaced = colon >= 0 && !/^[A-Za-z]:\//.test(raw);
  const project = namespaced ? raw.slice(0, colon) : "";
  const path = namespaced ? raw.slice(colon + 1) : raw;
  const parts = path.split("/");
  return { project, path, name: parts.pop() || path, folder: parts.join("/") };
}
