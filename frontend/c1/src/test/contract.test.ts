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
const spec = JSON.parse(readFileSync(resolve(process.cwd(), '../../docs/c1_openapi.json'), 'utf-8')) as OpenApi // run from frontend/c1

afterEach(() => vi.unstubAllGlobals())

describe('the typed client and fixtures match docs/c1_openapi.json', () => {
  it('has the eighteen documented paths', () => {
    expect(Object.keys(spec.paths).sort()).toEqual(
      [
        '/api/health', '/api/projects', '/api/projects/{pid}/sources', '/api/projects/{pid}/sources/{source_id}', '/api/projects/{pid}/analyze', '/api/jobs/{job_id}', '/api/projects/{pid}/summary',
        '/api/projects/{pid}/requirements', '/api/requirements/{rid}', '/api/requirements/{rid}/generate', '/api/requirements/{rid}/decision', '/api/projects/{pid}/export',
        '/api/projects/{pid}/generate', '/api/projects/{pid}/generation/pause', '/api/projects/{pid}/generation/resume',
        '/api/engine', '/api/engine/test', '/api/projects/{pid}/publish/neo4j',
      ].sort(),
    )
  })

  it('every client call goes to a documented path with a documented method', async () => {
    const { calls } = mockApi()
    const templates = Object.entries(spec.paths).flatMap(([p, methods]) => Object.keys(methods).map((m) => ({ re: new RegExp('^' + p.replace(/\{[^}]+\}/g, '[^/]+') + '$'), method: m.toUpperCase() })))
    await Promise.allSettled([
      api.health(), api.projects(), api.sources(1), api.upload(1, []), api.analyze(1), api.job('abc'), api.summary(1),
      api.requirements(1, { risk: 'all', type: 'all', q: '' }, 50, 0), api.requirement('p1-REQ-001'), api.generate('p1-REQ-001'),
      api.decide('p1-REQ-001', { decision: 'accepted' }), api.deleteSource(1, 2), api.clearSources(1),
      api.generateRemaining(1), api.pause(1), api.resume(1), api.engine(), api.updateEngine({ target: 'device' }), api.testEngine('cloud'),
    ])
    expect(calls).toHaveLength(19)
    for (const c of calls) expect(templates.some((t) => t.method === c.method && t.re.test(c.url.pathname)), `${c.method} ${c.url.pathname}`).toBe(true)
    expect(api.exportUrl(1, 'csv')).toContain('/api/projects/1/export?format=csv')
  })

  it('response fixtures have exactly the fields of the API schemas', () => {
    const keys = (name: string) => Object.keys(spec.components.schemas[name]!.properties ?? {}).sort()
    const check: [string, object][] = [
      ['Health', fx.health], ['ProjectOut', fx.project], ['SourceOut', fx.source], ['Summary', fx.summary], ['Job', fx.job],
      ['RequirementRow', fx.rows[0]!], ['RequirementDetail', fx.detail], ['GenerationOut', fx.generationDone], ['TaskDrafts', fx.summary.task_drafts],
      ['EngineOut', fx.engine], ['DeviceEngine', fx.engine.device], ['CloudEngine', fx.engine.cloud],
    ]
    for (const [name, obj] of check) expect(Object.keys(obj).sort(), name).toEqual(keys(name))
  })

  it('builds the list query like the API expects', () => {
    expect(listParams({ risk: 'all', type: 'all', q: '' }, 50, 0)).toBe('limit=50&offset=0')
    expect(listParams({ risk: 'HIGH', type: 'conflict', q: ' login ' }, 50, 100)).toBe('limit=50&offset=100&risk=HIGH&type=conflict&q=login')
  })

  it('the query parameters it sends are documented', () => {
    const op = spec.paths['/api/projects/{pid}/requirements']!.get as { parameters: { name: string }[] }
    expect(op.parameters.map((p) => p.name).sort()).toEqual(['limit', 'offset', 'pid', 'q', 'risk', 'type'])
  })
})
