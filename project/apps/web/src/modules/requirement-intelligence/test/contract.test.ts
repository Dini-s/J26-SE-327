import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, listParams } from '../api/client'
import * as fx from './fixtures'
import { mockApi } from './utils'

interface OpenApi {
  paths: Record<string, Record<string, unknown>>
  components: { schemas: Record<string, { properties?: Record<string, unknown> }> }
}
const spec = JSON.parse(readFileSync(resolve(process.cwd(), '../../../docs/c1_openapi.json'), 'utf-8')) as OpenApi // run from project/apps/web

afterEach(() => vi.unstubAllGlobals())

describe('the typed client and fixtures match docs/c1_openapi.json', () => {
  it('has the documented paths', () => {
    expect(Object.keys(spec.paths).sort()).toEqual(
      [
        '/api/health', '/api/projects', '/api/projects/{pid}/sources', '/api/projects/{pid}/sources/{source_id}', '/api/projects/{pid}/analyze', '/api/jobs/{job_id}', '/api/projects/{pid}/summary',
        '/api/projects/{pid}/requirements', '/api/requirements/{rid}', '/api/requirements/{rid}/generate', '/api/requirements/{rid}/decision', '/api/projects/{pid}/export',
        '/api/projects/{pid}/generate', '/api/projects/{pid}/generation/pause', '/api/projects/{pid}/generation/resume',
        '/api/engine', '/api/engine/test', '/api/projects/{pid}/publish/neo4j',
        '/api/projects/{pid}', '/api/projects/{pid}/archive', '/api/projects/{pid}/unarchive', '/api/projects/{pid}/overview',
        '/api/projects/{pid}/sync', '/api/projects/{pid}/phases', '/api/projects/{pid}/phases/{phase_id}', '/api/projects/{pid}/sprints', '/api/projects/{pid}/sprints/{sprint_id}',
        '/api/projects/{pid}/current-sprint', '/api/projects/{pid}/sources/{source_id}/sprint', '/api/projects/{pid}/sources/{source_id}/assign-ranges',
        '/api/projects/{pid}/sources/{source_id}/reanalyze', '/api/projects/{pid}/requirements/assign', '/api/projects/{pid}/drafts/retry-failed',
        '/api/projects/{pid}/integrations/jira', '/api/projects/{pid}/integrations/jira/connect', '/api/projects/{pid}/integrations/jira/projects', '/api/projects/{pid}/integrations/jira/boards',
        '/api/projects/{pid}/integrations/jira/sprints', '/api/projects/{pid}/integrations/jira/import', '/api/integrations/jira/callback',
      ].sort(),
    )
  })

  it('every client call goes to a documented path with a documented method', async () => {
    const { calls } = mockApi()
    const templates = Object.entries(spec.paths).flatMap(([p, methods]) => Object.keys(methods).map((m) => ({ re: new RegExp('^' + p.replace(/\{[^}]+\}/g, '[^/]+') + '$'), method: m.toUpperCase() })))
    await Promise.allSettled([
      api.health(), api.projects(), api.projects(true), api.createProject('Second'), api.renameProject(1, 'Renamed'), api.archiveProject(1), api.unarchiveProject(1), api.overview(1), api.publish(1),
      api.sources(1), api.upload(1, [], 'brd'), api.analyze(1), api.job('abc'), api.summary(1),
      api.requirements(1, { risk: 'all', type: 'all', q: '' }, 50, 0), api.requirement('p1-REQ-001'), api.generate('p1-REQ-001'),
      api.decide('p1-REQ-001', { decision: 'accepted' }), api.removeDecision('p1-REQ-001'), api.deleteSource(1, 2), api.clearSources(1),
      api.generateRemaining(1), api.pause(1), api.resume(1), api.engine(), api.updateEngine({ target: 'device' }), api.testEngine('cloud'),
      api.sync(1), api.phases(1), api.createPhase(1, 'Build'), api.updatePhase(1, 2, { name: 'Run' }), api.deletePhase(1, 2),
      api.sprints(1), api.createSprint(1, { name: 'Sprint 2' }), api.updateSprint(1, 2, { confirmed: true }), api.deleteSprint(1, 2, 3), api.deleteSprint(1, 2),
      api.setCurrentSprint(1, 2), api.setSourceSprint(1, 2, 3), api.assignRanges(1, 2, [{ from_page: 1, to_page: 2, sprint_id: 3 }]),
      api.assignRequirements(1, ['REQ-001'], 3), api.assignRequirements(1, ['REQ-001'], null), api.reanalyze(1, 2),
      api.retryFailed(1),
      api.jiraStatus(1), api.jiraConnect(1), api.jiraDisconnect(1), api.jiraProjects(1), api.jiraBoards(1, 'ABC'), api.jiraSprints(1, 7), api.jiraSprints(1, 7, ['closed']),
      api.jiraImport(1, { project_key: 'ABC', board_id: 7, set_current: true }),
    ])
    expect(calls).toHaveLength(52)
    for (const c of calls) expect(templates.some((t) => t.method === c.method && t.re.test(c.url.pathname)), `${c.method} ${c.url.pathname}`).toBe(true)
    expect(api.exportUrl(1, 'csv')).toContain('/api/projects/1/export?format=csv')
  })

  it('publishes without a body, saves a decision with PUT and sends the document type', async () => {
    const { calls } = mockApi()
    await Promise.allSettled([api.publish(1), api.decide('p1-REQ-001', { decision: 'accepted' }), api.upload(1, [new File(['x'], 'a.txt')], 'brd')])
    const publish = calls.find((c) => c.url.pathname.endsWith('/publish/neo4j'))!
    expect(publish.method).toBe('POST')
    expect(publish.body).toBeUndefined()
    expect(calls.find((c) => c.url.pathname.endsWith('/decision'))!.method).toBe('PUT')
  })

  it('response fixtures have exactly the fields of the API schemas', () => {
    const keys = (name: string) => Object.keys(spec.components.schemas[name]!.properties ?? {}).sort()
    const check: [string, object][] = [
      ['Health', fx.health], ['ProjectOut', fx.project], ['DecisionCounts', fx.project.decisions], ['SourceOut', fx.source], ['Summary', fx.summary], ['Job', fx.job],
      ['RequirementRow', fx.rows[0]!], ['RequirementDetail', fx.detail], ['GenerationOut', fx.generationDone], ['TaskDrafts', fx.summary.task_drafts],
      ['EngineOut', fx.engine], ['DeviceEngine', fx.engine.device], ['CloudEngine', fx.engine.cloud],
      ['SourceDrafts', fx.source.drafts], ['SourceSprintCount', fx.source.sprints[0]!], ['PhaseOut', fx.phases[0]!], ['SprintOut', fx.sprints[0]!], ['SyncStatus', fx.sync],
      ['CurrentSprint', fx.overview.current_sprint!], ['CurrentPhase', fx.overview.current_phase!], ['SprintDecisions', fx.overview.by_sprint[0]!], ['PhaseDecisions', fx.overview.by_phase[0]!],
      ['FindingsByType', fx.overview.findings_by_type], ['AnalysisOverview', fx.overview.analysis],
      ['Overview', fx.overview], ['OverviewProject', fx.overview.project], ['OverviewCounts', fx.overview.counts], ['AmbiguityOverview', fx.overview.counts.ambiguities],
      ['DraftOverview', fx.overview.counts.drafts], ['DecisionOverview', fx.overview.decisions], ['SourcesOverview', fx.overview.sources], ['GenerationOverview', fx.overview.generation],
      ['GraphOverview', { ...fx.graph, host: undefined }],
      ['JiraStatus', fx.jiraConnected], ['JiraSite', fx.jiraConnected.site!], ['JiraProject', fx.jiraProjects[0]!], ['JiraBoard', fx.jiraBoards[0]!], ['JiraSprintOut', fx.jiraSprints[0]!],
      ['JiraImportOut', fx.jiraImported], ['JiraConnectOut', { authorize_url: 'https://auth.atlassian.com/authorize?x=1' }], ['JiraRef', { key: 'ABC-1', type: 'Story', status: 'To Do', url: '' }],
    ]
    for (const [name, obj] of check) {
      const have = Object.keys(obj).filter((k) => (obj as Record<string, unknown>)[k] !== undefined).sort()
      expect(have, name).toEqual(name === 'GraphOverview' ? keys(name).filter((k) => k !== 'host') : keys(name))
    }
  })

  it('builds the list query like the API expects', () => {
    expect(listParams({ risk: 'all', type: 'all', q: '' }, 50, 0)).toBe('limit=50&offset=0')
    expect(listParams({ risk: 'HIGH', type: 'conflict', q: ' login ' }, 50, 100)).toBe('limit=50&offset=100&risk=HIGH&type=conflict&q=login')
    expect(listParams({ risk: 'all', type: 'all', q: '', sprint: 3 }, 50, 0)).toBe('limit=50&offset=0&sprint_id=3')
  })

  it('the query parameters it sends are documented', () => {
    const op = spec.paths['/api/projects/{pid}/requirements']!.get as { parameters: { name: string }[] }
    expect(op.parameters.map((p) => p.name).sort()).toEqual(['limit', 'offset', 'pid', 'q', 'risk', 'sprint_id', 'type'])
  })
})
