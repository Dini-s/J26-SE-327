const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/repositories").replace(/\/$/, "");

async function request(path = "", options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(typeof detail === "string" ? detail : `API request failed (${response.status})`);
  }
  return payload;
}

export async function getRepositories() {
  const data = await request();
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.repositories)) return data.repositories;
  if (Array.isArray(data?.items)) return data.items;
  throw new Error("Unexpected repositories response. Check GET /api/repositories.");
}

export function analyzeRepository(repositoryId) {
  return request(`/${encodeURIComponent(repositoryId)}/analyze`, { method: "POST" });
}

export function registerRepository(repository) {
  return request("", { method: "POST", body: JSON.stringify(repository) });
}

export function cloneRepository(repositoryId) {
  return request(`/${encodeURIComponent(repositoryId)}/clone`, { method: "POST" });
}
