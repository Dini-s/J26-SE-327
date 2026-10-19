import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { RequirementRoutes } from '../RequirementIntelligencePage'
import { ModuleStateProvider } from '../context/ModuleState'
import { ToastProvider } from '../context/Toasts'
import * as fx from './fixtures'

export const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

export interface Call {
  url: URL
  method: string
  body?: string
  form?: FormData
  signal?: AbortSignal | null
}
export type Handler = (call: Call) => Response | Promise<Response> | undefined

/** Replace fetch with a router. `handler` runs first; unmatched calls fall back to the default fixtures. */
export function mockApi(handler?: Handler) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = { url: new URL(String(input)), method: init?.method ?? 'GET', body: typeof init?.body === 'string' ? init.body : undefined, form: init?.body instanceof FormData ? init.body : undefined, signal: init?.signal }
      calls.push(call)
      const custom = handler?.(call)
      if (custom) return custom
      const p = call.url.pathname
      if (p === '/api/health') return json(fx.health)
      if (p === '/api/engine' && call.method === 'GET') return json(fx.engine)
      if (p === '/api/projects') return json([fx.project])
      if (p === '/api/projects/1/sources') return json([fx.source])
      if (p === '/api/projects/1/summary') return json(fx.summary)
      if (p === '/api/projects/1/sprints') return json(fx.sprints)
      if (p === '/api/projects/1/phases') return json(fx.phases)
      if (p === '/api/projects/1/sync') return json(fx.sync)
      if (p === '/api/projects/1/integrations/jira') return call.method === 'GET' ? json(fx.jiraNotConnected) : new Response(null, { status: 204 })
      if (p === '/api/projects/1/overview') return json(fx.overview)
      if (p === '/api/projects/1/requirements') return json({ total: fx.rows.length, limit: 500, offset: 0, items: fx.rows })
      if (p.startsWith('/api/requirements/') && !p.endsWith('/decision') && !p.endsWith('/generate')) return json(fx.detail)
      return json({ error: { code: 'not_found', message: `no mock for ${call.method} ${p}` } }, 404)
    }),
  )
  return { calls }
}

export function renderWithProviders(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, gcTime: 0 } } })
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>{ui}</ToastProvider>
    </QueryClientProvider>,
  )
}

/** The module's routes mounted like the shell does (requirement/*), starting at `path`. */
export function renderApp(path = '/requirement') {
  return renderWithProviders(
    <ModuleStateProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/requirement/*" element={<RequirementRoutes />} />
        </Routes>
      </MemoryRouter>
    </ModuleStateProvider>,
  )
}

/** Open the Processing details popover of the header. */
export async function openDetails() {
  const { screen } = await import('@testing-library/react')
  const userEvent = (await import('@testing-library/user-event')).default
  await userEvent.click(await screen.findByTestId('engine-pill'))
  return screen.findByTestId('processing-details')
}
