import { Code2, FileSearch, GitBranch, Layers, Network, PenLine, type LucideIcon } from 'lucide-react'
import type { Health, Project } from '../api/types'
import { CURRENT_USER } from '../config'

interface Module {
  label: string
  icon: LucideIcon
  active?: boolean
}

const MODULES: Module[] = [
  { label: 'Framework overview', icon: Layers },
  { label: 'Requirement intelligence', icon: FileSearch, active: true },
  { label: 'Repository intelligence', icon: Code2 },
  { label: 'Quality & testing', icon: PenLine },
  { label: 'Traceability intelligence', icon: GitBranch },
  { label: 'USKG knowledge graph', icon: Network },
]

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join('')
}

function Row({ label, value, good }: { label: string; value: string; good?: boolean | null }) {
  return (
    <div className="flex items-center justify-between gap-2 text-[11.5px]">
      <span className="text-nav-muted">{label}</span>
      <span className={`flex items-center gap-1.5 truncate font-medium ${good === false ? 'text-red-300' : 'text-white'}`}>
        {good !== undefined && good !== null && <span className={`h-1.5 w-1.5 rounded-full ${good ? 'bg-emerald-400' : 'bg-red-400'}`} aria-hidden="true" />}
        <span className="truncate">{value}</span>
      </span>
    </div>
  )
}

export function Sidebar({ project, health, healthError }: { project?: Project; health?: Health; healthError: boolean }) {
  return (
    <aside className="flex h-screen w-[72px] shrink-0 flex-col justify-between overflow-y-auto bg-nav-bg px-3 py-5 text-nav-text lg:w-[280px] lg:px-5" aria-label="Framework navigation">
      <div>
        <div className="flex items-center gap-3 px-1">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-600 to-violet-600 text-[15px] font-bold text-white shadow-lg" aria-hidden="true">
            {'{ }'}
          </div>
          <div className="hidden min-w-0 lg:block">
            <div className="text-[17px] font-bold leading-tight text-white">USI Framework</div>
            <div className="text-[12px] text-nav-muted">Unified software intelligence</div>
          </div>
        </div>

        <div className="mt-6 hidden rounded-card border border-nav-line bg-nav-card p-3.5 lg:block" aria-label="Current project">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-600/70 text-[12px] font-bold text-white">{project ? initials(project.name) : '…'}</div>
            <div className="min-w-0">
              <div className="label-caps !text-nav-muted">Current project</div>
              <div className="truncate text-[14px] font-semibold text-white">{project?.name ?? 'Loading…'}</div>
            </div>
          </div>
        </div>

        <div className="label-caps mt-7 hidden px-2 !text-nav-muted lg:block">Intelligence modules</div>
        <nav className="mt-3 flex flex-col gap-1" aria-label="Intelligence modules">
          {MODULES.map(({ label, icon: Icon, active }) =>
            active ? (
              <a
                key={label}
                href="#top"
                aria-current="page"
                title={label}
                className="relative flex items-center gap-3 rounded-ctl bg-nav-active px-3 py-3 text-[14px] font-medium text-white"
              >
                <span className="absolute -left-5 top-0 hidden h-full w-[3px] rounded-r bg-nav-accent lg:block" aria-hidden="true" />
                <Icon size={19} className="shrink-0" />
                <span className="hidden flex-1 truncate lg:block">{label}</span>
                <span className="hidden h-1.5 w-1.5 rounded-full bg-sky-300 lg:block" aria-hidden="true" />
              </a>
            ) : (
              <button
                key={label}
                type="button"
                disabled
                aria-disabled="true"
                title={`${label}: Coming soon`}
                className="group relative flex cursor-not-allowed items-center gap-3 rounded-ctl px-3 py-3 text-left text-[14px] text-nav-text/70"
              >
                <Icon size={19} className="shrink-0" />
                <span className="hidden flex-1 truncate lg:block">{label}</span>
                <span role="tooltip" className="pointer-events-none absolute left-full top-1/2 z-40 ml-2 hidden -translate-y-1/2 whitespace-nowrap rounded-md bg-ink px-2 py-1 text-[11px] text-white group-hover:block group-focus-visible:block">
                  Coming soon
                </span>
              </button>
            ),
          )}
        </nav>
      </div>

      <div className="mt-6">
        <section className="hidden rounded-card border border-nav-line bg-nav-card p-3.5 lg:block" aria-label="Engine status">
          <div className="label-caps mb-2 !text-nav-muted">Engine status</div>
          {healthError ? (
            <div className="text-[12px] text-red-300">API not reachable</div>
          ) : !health ? (
            <div className="text-[12px] text-nav-muted">Checking…</div>
          ) : (
            <div className="flex flex-col gap-1.5">
              <Row label="Part A models" value={health.part_a_loaded ? 'Loaded' : 'Not loaded'} good={health.part_a_loaded} />
              <Row label="Generation" value={`${health.generation_backend} · ${health.model || 'no model'}`} />
              <Row label="Reachable" value={health.generation_reachable ? 'Yes' : 'No'} good={health.generation_reachable} />
            </div>
          )}
        </section>
        <div className="mt-4 flex items-center gap-3 border-t border-nav-line px-1 pt-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-nav-active text-[12px] font-bold text-white" aria-hidden="true">
            {initials(CURRENT_USER.name)}
          </div>
          <div className="hidden min-w-0 lg:block">
            <div className="truncate text-[13px] font-semibold text-white">{CURRENT_USER.name}</div>
            <div className="truncate text-[11.5px] text-nav-muted">{CURRENT_USER.role}</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
