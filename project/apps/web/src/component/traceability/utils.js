/** "spring-petclinic:src/main/java/.../Owner.java" -> "Owner.java" */
export const shortName = (id) => String(id ?? "").split(/[/:]/).pop();

export const natural = (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true });

export const pct = (value) => `${Math.round((value ?? 0) * 100)}%`;

export const cx = (...parts) => parts.filter(Boolean).join(" ");
