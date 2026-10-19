import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { useProjects } from '../api/hooks'
import type { Policy, Project } from '../api/types'

const PROJECT_KEY = 'requirement-intelligence.projectId'
const POLICY_KEY = 'requirement-intelligence.draftPolicy'

/** Storage can be blocked (private window, site data cleared): every read and write is guarded and the page works without it. */
function readStored(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}
function writeStored(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* not remembered, still applied for this visit */
  }
}

function loadPolicy(): Policy {
  const v = readStored(POLICY_KEY)
  return v === 'all' || v === 'manual' || v === 'smart' ? v : 'smart'
}

interface ModuleState {
  /** Projects that are not archived. */
  projects: Project[]
  projectsLoading: boolean
  projectsError: unknown
  project: Project | undefined
  selectProject: (id: number) => void
  /** The analysis job started on this visit (the Sources and Task Drafts pages both follow it). */
  jobId: string | null
  setJobId: (id: string | null) => void
  /** Sources were added after the last analysis. */
  stale: boolean
  setStale: (v: boolean) => void
  policy: Policy
  setPolicy: (p: Policy) => void
}

const Ctx = createContext<ModuleState | null>(null)

export function useModule(): ModuleState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useModule needs the ModuleStateProvider')
  return v
}

/** Project choice (remembered), the running analysis and the draft policy: state that all four pages share. */
export function ModuleStateProvider({ children }: { children: ReactNode }) {
  const query = useProjects()
  const [chosen, setChosen] = useState<number | null>(() => {
    const n = Number(readStored(PROJECT_KEY))
    return Number.isInteger(n) && n > 0 ? n : null
  })
  const [jobId, setJobId] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const [policy, setPolicyState] = useState<Policy>(loadPolicy)

  const projects = query.data ?? []
  const project = projects.find((p) => p.id === chosen) ?? projects[0]

  const selectProject = useCallback((id: number) => {
    setChosen(id)
    writeStored(PROJECT_KEY, String(id))
    setJobId(null)
    setStale(false)
  }, [])
  const setPolicy = useCallback((p: Policy) => {
    setPolicyState(p)
    writeStored(POLICY_KEY, p)
  }, [])

  const value = useMemo<ModuleState>(
    () => ({ projects, projectsLoading: query.isLoading, projectsError: query.error, project, selectProject, jobId, setJobId, stale, setStale, policy, setPolicy }),
    // `projects` is a new array each render when there is no data yet; the query result is what changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [query.data, query.isLoading, query.error, project, selectProject, jobId, stale, policy, setPolicy],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
