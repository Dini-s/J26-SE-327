import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { WifiOff } from 'lucide-react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { ApiClientError } from './api/client'
import { useEngine, useHealth, usePauseGeneration, useSummary } from './api/hooks'
import { CloudUnreachableBanner } from './components/EngineSwitch'
import { OPEN_ENGINE_EVENT } from './components/ProcessingDetails'
import { useJiraReturn } from './components/JiraControls'
import { ProcessingDetails } from './components/ProcessingDetails'
import { ProjectSwitcher } from './components/ProjectSwitcher'
import { API_BASE } from './config'
import { ModuleStateProvider, useModule } from './context/ModuleState'
import { ToastProvider, useToasts } from './context/Toasts'
import { copy } from './copy'
import { OverviewPage } from './pages/OverviewPage'
import { ReviewQueuePage } from './pages/ReviewQueuePage'
import { SourcesFindingsPage } from './pages/SourcesFindingsPage'
import { TaskDraftsPage } from './pages/TaskDraftsPage'
import './c1.css'

const isNetwork = (e: unknown) => e instanceof ApiClientError && e.status === 0

function pageFor(pathname: string) {
  const last = pathname.replace(/\/+$/, '').split('/').pop()
  return last === 'sources' ? copy.pages.sources : last === 'review' ? copy.pages.review : last === 'drafts' ? copy.pages.drafts : copy.pages.overview
}

/** Header of all four pages (title, project dropdown, AI engine pill) and the banners that matter on every page. */
export function ModuleLayout() {
  const { project, projectsError, projectsLoading } = useModule()
  const { pathname } = useLocation()
  const toasts = useToasts()
  const health = useHealth()
  const engine = useEngine()
  const summary = useSummary(project?.id)
  const pauseGeneration = usePauseGeneration(project?.id)
  const drafts = summary.data?.task_drafts
  const cloudPaused = !!drafts?.paused && drafts.paused_reason === 'cloud_unreachable'
  const offline = isNetwork(projectsError) || isNetwork(health.error)
  const page = pageFor(pathname)
  useJiraReturn()

  const onRetryCloud = () => pauseGeneration.mutate(false, { onError: (e) => toasts.push(copy.drafts.resumeFailed(e.message), 'error') })
  const onOpenEngine = () => window.dispatchEvent(new Event(OPEN_ENGINE_EVENT))

  return (
    <div className="c1-root mx-auto w-full max-w-[1500px]">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3" data-testid="module-header">
        <div className="min-w-0">
          <p className="c1-label !text-primary">{copy.module.name}</p>
          <h1 className="mt-0.5 text-xl font-bold text-heading">{page.title}</h1>
          <p className="mt-0.5 max-w-[640px] text-xs text-secondary-text">{page.subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ProjectSwitcher />
          <ProcessingDetails engine={engine.data} health={health.data} offline={offline || health.isError} cloudPaused={cloudPaused} />
        </div>
      </header>

      {offline && (
        <div role="alert" className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-danger-border bg-danger-bg px-4 py-3 text-xs text-danger-text" data-testid="offline-banner">
          <WifiOff size={16} aria-hidden="true" />
          <span className="flex-1">{copy.module.offline(API_BASE)}</span>
        </div>
      )}
      {cloudPaused && <CloudUnreachableBanner busy={pauseGeneration.isPending} onRetry={onRetryCloud} onOpen={onOpenEngine} />}

      <div className="mt-4">
        {!project && !projectsLoading && !offline ? (
          <div className="c1-card px-5 py-10 text-center text-xs text-secondary-text" data-testid="no-project">
            {copy.project.empty}
          </div>
        ) : (
          <Outlet />
        )}
      </div>
    </div>
  )
}

/** The four pages of the module under /requirement (the shell mounts this at requirement/*). */
export function RequirementRoutes() {
  return (
    <Routes>
      <Route element={<ModuleLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="sources" element={<SourcesFindingsPage />} />
        <Route path="review" element={<ReviewQueuePage />} />
        <Route path="drafts" element={<TaskDraftsPage />} />
        <Route path="*" element={<Navigate to="/requirement" replace />} />
      </Route>
    </Routes>
  )
}

// One query client for the module, so what was loaded is still there when the user comes back from another page of the shell.
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } })

/** Requirement Intelligence (route /requirement/*). Owns its own data, toast and project providers. */
export default function RequirementIntelligencePage() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ModuleStateProvider>
          <RequirementRoutes />
        </ModuleStateProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}
