import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Project } from '../api/types'
import * as fx from './fixtures'
import { json, mockApi, renderApp, type Call } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

const second: Project = { ...fx.project, id: 2, project_key: 'payments', name: 'Payments Hub', requirements: 7 }
const archivedOne: Project = { ...fx.project, id: 3, project_key: 'legacy', name: 'Legacy Ledger', archived: true }

/** A stateful project API: create, rename, archive and restore change the list. */
function projectApi(extra?: (c: Call) => Response | Promise<Response> | undefined) {
  let list: Project[] = [fx.project, second, archivedOne]
  const api = mockApi((c) => {
    const p = c.url.pathname
    if (p === '/api/projects' && c.method === 'GET') return json(list.filter((x) => c.url.searchParams.get('include_archived') === 'true' || !x.archived))
    if (p === '/api/projects' && c.method === 'POST') {
      const name = JSON.parse(c.body!).name as string
      if (list.some((x) => !x.archived && x.name.toLowerCase() === name.toLowerCase())) return json({ error: { code: 'project_name_taken', message: `A project named '${name}' already exists. Choose another name.` } }, 409)
      const created: Project = { ...fx.project, id: 4, project_key: 'brand-new', name, requirements: 0 }
      list = [...list, created]
      return json(created, 201)
    }
    const m = /^\/api\/projects\/(\d+)(\/archive|\/unarchive)?$/.exec(p)
    if (m && (c.method === 'PATCH' || c.method === 'POST')) {
      const id = Number(m[1])
      list = list.map((x) => (x.id !== id ? x : m[2] === '/archive' ? { ...x, archived: true } : m[2] === '/unarchive' ? { ...x, archived: false } : { ...x, name: JSON.parse(c.body!).name }))
      return json(list.find((x) => x.id === id))
    }
    const mo = /^\/api\/projects\/(\d+)\/overview$/.exec(p)
    if (mo) return json({ ...fx.overview, project: { ...fx.overview.project, id: Number(mo[1]) } })
    if (/^\/api\/projects\/\d+\/(sources|summary|requirements)$/.test(p) && !p.startsWith('/api/projects/1/')) {
      if (p.endsWith('/sources')) return json([])
      if (p.endsWith('/summary')) return json(fx.summary)
      return json({ total: 0, limit: 500, offset: 0, items: [] })
    }
    return extra?.(c)
  })
  return api
}

const openMenu = async () => {
  await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('Core Banking Platform'))
  await userEvent.click(screen.getByTestId('project-trigger'))
  return screen.findByTestId('project-menu')
}

describe('project switcher', () => {
  it('shows the current project and lists the active ones in a searchable dropdown', async () => {
    projectApi()
    renderApp()
    const menu = await openMenu()
    expect(screen.getByTestId('project-trigger')).toHaveAttribute('aria-expanded', 'true')
    const options = within(menu).getAllByRole('option')
    expect(options.map((o) => o.textContent?.trim())).toEqual(['Core Banking Platform', 'Payments Hub'])
    expect(options[0]).toHaveAttribute('aria-selected', 'true')
    await userEvent.type(within(menu).getByRole('combobox'), 'pay')
    expect(within(menu).getAllByRole('option').map((o) => o.textContent?.trim())).toEqual(['Payments Hub'])
    await userEvent.clear(within(menu).getByRole('combobox'))
    await userEvent.type(within(menu).getByRole('combobox'), 'zzz')
    expect(within(menu).getByText('No project')).toBeInTheDocument()
  })

  it('switching loads the other project and remembers the choice', async () => {
    const { calls } = projectApi()
    renderApp()
    const menu = await openMenu()
    await userEvent.click(within(menu).getByRole('option', { name: /Payments Hub/ }))
    expect(screen.queryByTestId('project-menu')).toBeNull()
    await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('Payments Hub'))
    await waitFor(() => expect(calls.some((c) => c.url.pathname === '/api/projects/2/overview')).toBe(true))
    expect(window.localStorage.getItem('requirement-intelligence.projectId')).toBe('2')
  })

  it('starts with the remembered project, and ignores a remembered one that no longer exists', async () => {
    window.localStorage.setItem('requirement-intelligence.projectId', '2')
    projectApi()
    const first = renderApp()
    await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('Payments Hub'))
    first.unmount()
    window.localStorage.setItem('requirement-intelligence.projectId', '99')
    renderApp()
    await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('Core Banking Platform'))
  })

  it('works when the browser blocks storage', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    projectApi()
    renderApp()
    const menu = await openMenu()
    await userEvent.click(within(menu).getByRole('option', { name: /Payments Hub/ }))
    await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('Payments Hub'))
    vi.restoreAllMocks()
  })

  it('works from the keyboard: arrows and Enter pick a project, Escape closes the menu and returns the focus', async () => {
    projectApi()
    renderApp()
    const menu = await openMenu()
    const search = within(menu).getByRole('combobox')
    expect(search).toHaveFocus()
    await userEvent.keyboard('{ArrowDown}{Enter}')
    await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('Payments Hub'))
    await userEvent.click(screen.getByTestId('project-trigger'))
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByTestId('project-menu')).toBeNull()
    expect(screen.getByTestId('project-trigger')).toHaveFocus()
  })
})

describe('new, rename and archive', () => {
  it('New project: checks the length first, sends the name, selects the new project', async () => {
    const { calls } = projectApi()
    renderApp()
    const menu = await openMenu()
    await userEvent.click(within(menu).getByRole('button', { name: 'New project' }))
    const dialog = screen.getByRole('dialog', { name: 'New project' })
    const input = within(dialog).getByLabelText('Project name')
    expect(input).toHaveFocus()
    await userEvent.type(input, 'x')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create project' }))
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Use 2 to 80 characters')
    expect(calls.some((c) => c.method === 'POST' && c.url.pathname === '/api/projects')).toBe(false)
    await userEvent.type(input, 'yz')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create project' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(JSON.parse(calls.find((c) => c.method === 'POST' && c.url.pathname === '/api/projects')!.body!)).toEqual({ name: 'xyz' })
    await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('xyz'))
    expect(await screen.findByText('Project “xyz” created.')).toBeInTheDocument()
  })

  it('a name that is already used stays in the dialog with the service message', async () => {
    projectApi()
    renderApp()
    const menu = await openMenu()
    await userEvent.click(within(menu).getByRole('button', { name: 'New project' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('Project name'), 'payments hub')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create project' }))
    expect(await within(dialog).findByText(/already exists/)).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('Cancel and Escape close the dialog without sending anything', async () => {
    const { calls } = projectApi()
    renderApp()
    const menu = await openMenu()
    await userEvent.click(within(menu).getByRole('button', { name: 'New project' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    await userEvent.click(screen.getByTestId('project-trigger'))
    await userEvent.click(within(await screen.findByTestId('project-menu')).getByRole('button', { name: 'New project' }))
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(calls.some((c) => c.method === 'POST' && c.url.pathname === '/api/projects')).toBe(false)
  })

  it('Rename: the dialog starts with the current name and sends PATCH', async () => {
    const { calls } = projectApi()
    renderApp()
    const menu = await openMenu()
    await userEvent.click(within(menu).getByRole('button', { name: 'Rename' }))
    const dialog = screen.getByRole('dialog', { name: 'Rename project' })
    const input = within(dialog).getByLabelText('Project name')
    expect(input).toHaveValue('Core Banking Platform')
    await userEvent.clear(input)
    await userEvent.type(input, 'Core Banking 2')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('Core Banking 2'))
    const patch = calls.find((c) => c.method === 'PATCH')!
    expect(patch.url.pathname).toBe('/api/projects/1')
    expect(JSON.parse(patch.body!)).toEqual({ name: 'Core Banking 2' })
  })

  it('Archive asks first, then archives and moves to another project; Restore brings it back', async () => {
    const { calls } = projectApi()
    renderApp()
    const menu = await openMenu()
    await userEvent.click(within(menu).getByRole('button', { name: 'Archive' }))
    const dialog = screen.getByRole('dialog', { name: 'Archive “Core Banking Platform”?' })
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus()
    expect(calls.some((c) => c.url.pathname.endsWith('/archive'))).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Archive' }))
    await waitFor(() => expect(screen.getByTestId('project-trigger')).toHaveTextContent('Payments Hub'))
    expect(calls.some((c) => c.method === 'POST' && c.url.pathname === '/api/projects/1/archive')).toBe(true)

    await userEvent.click(screen.getByTestId('project-trigger'))
    const menu2 = await screen.findByTestId('project-menu')
    await userEvent.click(within(menu2).getByRole('checkbox', { name: 'Show archived projects' }))
    await waitFor(() => expect(calls.some((c) => c.url.searchParams.get('include_archived') === 'true')).toBe(true))
    const archived = await within(menu2).findByRole('option', { name: /Legacy Ledger/ })
    await userEvent.click(within(archived).getByRole('button', { name: /Restore/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url.pathname === '/api/projects/3/unarchive')).toBe(true))
  })
})
