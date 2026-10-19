/** Settings that are not read from the API. */
export const API_BASE: string = (import.meta.env.VITE_C1_API_BASE as string | undefined)?.replace(/\/$/, '') || 'http://127.0.0.1:8000'

export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024
export const ALLOWED_EXTENSIONS = ['.txt', '.md', '.pdf', '.docx'] as const

/** Mutable so tests can shorten it. The first analysis can take 1-2 minutes (model load), so the default is generous. */
export const limits = { analyzeTimeoutMs: 300_000 }

export const HEALTH_POLL_MS = 15_000
export const JOB_POLL_MS = 2_000
export const DRAFT_POLL_MS = 1_500
/** The sync state of the knowledge graph changes by itself (waiting, syncing, retrying), so the overview looks again now and then. */
export const SYNC_POLL_MS = 5_000
export const PAGE_SIZE = 50
export const SEARCH_DEBOUNCE_MS = 300
