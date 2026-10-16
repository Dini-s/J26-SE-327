import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { vi } from 'vitest'
import App from '../App'
import { ToastProvider } from '../context/Toasts'
import * as fx from './fixtures'

export const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

export interface Call {
  url: URL
  method: string
  body?: string
  signal?: AbortSignal | null
}
export type Handler = (call: Call) => Response | Promise<Response> | undefined

/** Replace fetch with a router. `handler` runs first; unmatched calls fall back to the default fixtures. */
export function mockApi(handler?: Handler) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const call: Call = { url: new URL(String(input)), method: init?.method ?? 'GET', body: typeof init?.body === 'string' ? init.body : undefined, signal: init?.signal }
      calls.push(call)
      const custom = handler?.(call)
      if (custom) return custom
      const p = call.url.pathname
      if (p === '/api/health') return json(fx.health)
      if (p === '/api/engine' && call.method === 'GET') return json(fx.engine)
      if (p === '/api/projects') return json([fx.project])
      if (p === '/api/projects/1/sources') return json([fx.source])
      if (p === '/api/projects/1/summary') return json(fx.summary)
      if (p === '/api/projects/1/requirements') return json({ total: fx.rows.length, limit: 50, offset: 0, items: fx.rows })
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

export const renderApp = () => renderWithProviders(<App />)
