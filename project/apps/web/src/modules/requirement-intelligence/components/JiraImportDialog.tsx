import { useState } from 'react'
import { useJiraBoards, useJiraConnect, useJiraImport, useJiraProjects, useSprints } from '../api/hooks'
import { ApiClientError } from '../api/client'
import type { JiraImportResult, JiraSprintState } from '../api/types'
import { useModule } from '../context/ModuleState'
import { copy } from '../copy'
import { goTo } from '../lib/navigate'
import { Dialog } from './Dialog'
import { FIELD } from './PlanDialogs'
import { ownSprints } from '../lib/planning'
import { Spinner } from './ui'

const STATES: JiraSprintState[] = ['active', 'future', 'closed']
const COMMON_TYPES = ['Story', 'Task', 'Bug', 'Epic']

function Result({ r }: { r: JiraImportResult }) {
  const t = copy.jira.result
  const lines = [r.target_sprint ? t.addedTo(r.target_sprint.name) : '', t.issuesNew(r.issues_new), t.issuesUpdated(r.issues_updated), t.issuesUnchanged(r.issues_unchanged)]
  if (r.skipped > 0) lines.push(t.skipped(r.skipped))
  if (r.matched || r.sprints_created + r.sprints_updated > 0) lines.push(t.sprints(r.sprints_created, r.sprints_updated))
  if (r.missing > 0) lines.push(t.missing(r.missing))
  if (r.queued > 0) lines.push(t.queued(r.queued))
  return (
    <div data-testid="jira-result">
      <ul className="list-disc space-y-1 pl-5 text-xs text-heading">
        {lines.filter(Boolean).map((l) => (
          <li key={l}>{l}</li>
        ))}
      </ul>
      {r.truncated && (
        <p className="mt-3 rounded-lg border border-warning-border bg-warning-bg px-3 py-2 text-xs text-warning-text" role="status">
          {copy.jira.truncated}
        </p>
      )}
      {r.analysis_error && (
        <p className="mt-3 rounded-lg border border-warning-border bg-warning-bg px-3 py-2 text-xs text-warning-text" role="alert" data-testid="jira-analysis-error">
          {copy.jira.analysisError}
        </p>
      )}
    </div>
  )
}

/** Choose the Jira project, the board, the kinds of sprint and issue to bring in; then see what the import did. */
export function JiraImportDialog({ pid, onClose }: { pid: number; onClose: () => void }) {
  const { policy, setJobId } = useModule()
  const projects = useJiraProjects(pid)
  const [projectKey, setProjectKey] = useState('')
  const boards = useJiraBoards(pid, projectKey)
  const [board, setBoard] = useState('')
  const [states, setStates] = useState<Set<JiraSprintState>>(new Set<JiraSprintState>(['active', 'future']))
  const [types, setTypes] = useState<Set<string>>(new Set(['Story', 'Task']))
  const [other, setOther] = useState('')
  const sprints = useSprints(pid)
  const [target, setTarget] = useState('') // '' = the current sprint, else a sprint id
  const [error, setError] = useState('')
  const [result, setResult] = useState<JiraImportResult | null>(null)
  const run = useJiraImport(pid)
  const reconnect = useJiraConnect(pid)
  const boardsNeedReconnect = boards.error instanceof ApiClientError && (boards.error.code === 'jira_scope_missing' || boards.error.status === 401 || boards.error.status === 403)

  const flip = <T,>(set: Set<T>, value: T, put: (s: Set<T>) => void) => {
    const next = new Set(set)
    if (!next.delete(value)) next.add(value)
    put(next)
  }
  const sprintList = ownSprints(sprints.data ?? []) // never a sprint an earlier import made: Jira goes into the sprint chosen here
  const chosen = target !== '' ? target : sprintList.some((s) => s.is_current) ? '' : String(sprintList[0]?.id ?? '')
  const submit = () => {
    const issueTypes = Array.from(new Set([...types, ...other.split(',').map((t) => t.trim()).filter(Boolean)]))
    if (!projectKey) return setError(copy.jira.needProject)
    if (states.size === 0) return setError(copy.jira.needStates)
    if (issueTypes.length === 0) return setError(copy.jira.needTypes)
    setError('')
    run.mutate(
      {
        project_key: projectKey,
        ...(board ? { board_id: Number(board) } : {}),
        sprint_states: STATES.filter((s) => states.has(s)),
        issue_types: issueTypes,
        set_current: false,
        target_sprint_id: chosen === '' ? null : Number(chosen),
        policy,
      },
      {
        onSuccess: (r) => {
          setResult(r)
          if (r.job_id) setJobId(r.job_id)
        },
        onError: (e) => setError(copy.jira.importFailed(e.message)),
      },
    )
  }

  return (
    <Dialog
      title={result ? copy.jira.resultTitle : copy.jira.importTitle}
      description={result ? undefined : copy.jira.importIntro}
      onClose={onClose}
      actions={
        result ? (
          <button type="button" className="c1-btn-primary" onClick={onClose} data-testid="jira-done">
            {copy.jira.done}
          </button>
        ) : (
          <>
            <button type="button" className="c1-btn-secondary" onClick={onClose}>
              {copy.common.cancel}
            </button>
            <button type="button" className="c1-btn-primary" disabled={run.isPending} onClick={submit} data-testid="jira-import-submit">
              {run.isPending && <Spinner className="h-3.5 w-3.5" />} {run.isPending ? copy.jira.importing : copy.jira.importButton}
            </button>
          </>
        )
      }
    >
      {result ? (
        <Result r={result} />
      ) : (
        <div className="space-y-3">
          <label className="block text-xs text-secondary-text">
            {copy.jira.project}
            <select
              value={projectKey}
              onChange={(e) => {
                setProjectKey(e.target.value)
                setBoard('')
              }}
              className={FIELD}
              data-testid="jira-project"
              disabled={projects.isLoading}
            >
              <option value="">{projects.isLoading ? copy.common.loading : copy.jira.projectPlaceholder}</option>
              {(projects.data ?? []).map((p) => (
                <option key={p.key} value={p.key}>
                  {p.name} ({p.key})
                </option>
              ))}
            </select>
          </label>
          {projects.isError && (
            <p role="alert" className="text-[11px] text-danger-text">
              {copy.jira.projectsFailed(projects.error.message)}
            </p>
          )}

          <label className="block text-xs text-secondary-text">
            {copy.jira.board}
            <select value={board} onChange={(e) => setBoard(e.target.value)} className={FIELD} data-testid="jira-board" disabled={!projectKey || boards.isLoading}>
              <option value="">{boards.isLoading ? copy.jira.boardsLoading : copy.jira.noBoard}</option>
              {(boards.data ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.type})
                </option>
              ))}
            </select>
          </label>
          {boards.isError && boardsNeedReconnect && (
            <div role="status" className="flex flex-wrap items-center gap-2 text-[11px] text-warning-text" data-testid="jira-boards-reconnect">
              <span>{copy.jira.boardsReconnect}</span>
              <button
                type="button"
                className="c1-btn-secondary"
                disabled={reconnect.isPending}
                onClick={() => reconnect.mutate(undefined, { onSuccess: (r) => goTo(r.authorize_url), onError: (e) => setError(copy.jira.connectFailed(e.message)) })}
                data-testid="jira-boards-reconnect-button"
              >
                {copy.jira.reconnect}
              </button>
              <span className="text-secondary-text">{copy.jira.boardsReconnectHint}</span>
            </div>
          )}
          {boards.isError && !boardsNeedReconnect && (
            <p role="status" className="text-[11px] text-warning-text" data-testid="jira-boards-failed">
              {copy.jira.boardsFailed}
            </p>
          )}

          <label className="block text-xs text-secondary-text">
            {copy.jira.addToSprint}
            <select value={chosen} onChange={(e) => setTarget(e.target.value)} className={FIELD} data-testid="jira-target">
              {sprintList.map((s) => (
                <option key={s.id} value={s.is_current ? '' : s.id}>
                  {s.name}
                  {s.is_current ? ` (${copy.jira.currentSuffix})` : ''}
                </option>
              ))}
            </select>
            <span className="mt-1 block text-[11px] text-muted" data-testid="jira-target-hint">
              {copy.jira.sprintHint}
            </span>
          </label>

          <fieldset>
            <legend className="text-xs text-secondary-text">{copy.jira.sprintStates}</legend>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
              {STATES.map((s) => (
                <label key={s} className="flex items-center gap-1.5 text-xs text-heading">
                  <input type="checkbox" checked={states.has(s)} onChange={() => flip(states, s, setStates)} /> {copy.jira.states[s]}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="text-xs text-secondary-text">{copy.jira.issueTypes}</legend>
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
              {COMMON_TYPES.map((t) => (
                <label key={t} className="flex items-center gap-1.5 text-xs text-heading">
                  <input type="checkbox" checked={types.has(t)} onChange={() => flip(types, t, setTypes)} /> {t}
                </label>
              ))}
            </div>
            <label className="mt-2 block text-xs text-secondary-text">
              {copy.jira.otherTypes}
              <input value={other} onChange={(e) => setOther(e.target.value)} className={FIELD} maxLength={200} />
            </label>
          </fieldset>

          {error && (
            <p role="alert" className="text-[11px] text-danger-text" data-testid="jira-error">
              {error}
            </p>
          )}
        </div>
      )}
    </Dialog>
  )
}
