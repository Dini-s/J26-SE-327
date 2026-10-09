import type {
  CandidateMatch,
  OverviewStats,
  Requirement,
  RequirementDetails,
  ValidationEvidence,
} from "../types/quality";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/quality";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text();

    throw new Error(message || `Request failed (${response.status})`);
  }

  return (await response.json()) as T;
}

export async function getOverview(): Promise<OverviewStats> {
  return parseResponse<OverviewStats>(await fetch(`${API_BASE}/overview`));
}

export async function getRequirements(): Promise<Requirement[]> {
  return parseResponse<Requirement[]>(await fetch(`${API_BASE}/requirements`));
}

export async function getRequirement(id: string): Promise<RequirementDetails> {
  return parseResponse<RequirementDetails>(
    await fetch(`${API_BASE}/requirements/` + `${encodeURIComponent(id)}`),
  );
}

export async function getEvidence(): Promise<ValidationEvidence[]> {
  return parseResponse<ValidationEvidence[]>(
    await fetch(`${API_BASE}/evidence`),
  );
}

export async function processRequirements(): Promise<void> {
  const response = await fetch(`${API_BASE}/process-requirements`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }
}

export async function normalizeEvidence(): Promise<void> {
  const response = await fetch(`${API_BASE}/evidence/normalize`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }
}

export async function retrieveEvidence(
  rvuId: string,

  method: "keyword" | "tfidf" | "semantic",

  topK = 5,
): Promise<CandidateMatch[]> {
  return parseResponse<CandidateMatch[]>(
    await fetch(
      `${API_BASE}/rvus/` +
        `${encodeURIComponent(rvuId)}` +
        `/retrieve` +
        `?method=${encodeURIComponent(method)}` +
        `&top_k=${topK}`,
      {
        method: "POST",
      },
    ),
  );
}
