import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Sidebar from '../../../Layouts/Sidebar'
import AppRoutes from '../../../routes/AppRoutes'
import { navigation } from '../../../data/navigation'
import { mockApi } from './utils'

afterEach(() => {
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

const CHILDREN = [
  ['Overview', '/requirement'],
  ['Sources & Findings', '/requirement/sources'],
  ['Review Queue', '/requirement/review'],
  ['Publish', '/requirement/drafts'],
] as const

describe('sidebar registration', () => {
  it('declares the children like Repository Intelligence does: expandable, with a children array', () => {
    const item = navigation.find((n) => n.label === 'Requirement Intelligence')!
    const repo = navigation.find((n) => n.label === 'Repository Intelligence')!
    expect(item.expandable).toBe(true)
    expect(repo.expandable).toBe(true)
    expect(item.path).toBe('/requirement')
    expect(item.children!.map((c) => [c.label, c.path])).toEqual(CHILDREN.map((c) => [...c]))
  })

  it.each(CHILDREN)('shows the child "%s" as a link to %s and marks only the page that is open', (label, path) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <Sidebar collapsed={false} onToggle={() => undefined} />
      </MemoryRouter>,
    )
    // other components have an "Overview" too: look at this module's links by their address
    const mine = (name: string, href: string) => screen.getAllByRole('link', { name }).find((l) => l.getAttribute('href') === href)!
    const link = mine(label, path)
    expect(link).toBeTruthy()
    expect(link.className).toContain('bg-blue-600')
    for (const [other, otherPath] of CHILDREN.filter(([l]) => l !== label)) expect(mine(other, otherPath).className).not.toContain('bg-blue-600')
  })

  it('expands from the arrow button of the item and collapses again', async () => {
    render(
      <MemoryRouter initialEntries={['/overview']}>
        <Sidebar collapsed={false} onToggle={() => undefined} />
      </MemoryRouter>,
    )
    const toggle = screen.getByRole('button', { name: 'Expand Requirement Intelligence' })
    const wrapper = toggle.closest('.relative')!.parentElement!
    const rows = () => wrapper.querySelector('.grid') as HTMLElement
    expect(rows().className).toContain('grid-rows-[0fr]') // closed while another page is open
    await userEvent.click(toggle)
    expect(rows().className).toContain('grid-rows-[1fr]')
    expect(within(rows()).getAllByRole('link').map((l) => l.textContent)).toEqual(CHILDREN.map(([l]) => l))
    await userEvent.click(toggle)
    expect(rows().className).toContain('grid-rows-[0fr]')
  })
})

describe('routes in the shell', () => {
  const open = (path: string) => {
    window.history.pushState({}, '', path)
    return render(<AppRoutes />)
  }

  it.each([
    ['/requirement', 'Overview'],
    ['/requirement/sources', 'Sources & Findings'],
    ['/requirement/review', 'Review Queue'],
    ['/requirement/drafts', 'Publish'],
  ])('%s opens the page "%s" with its own active state in the sidebar', async (path, title) => {
    mockApi()
    open(path)
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument()
    const active = screen.getAllByRole('link', { name: title }).find((l) => l.getAttribute('href') === path)!
    expect(active.className).toContain('bg-blue-600')
  })

  it('moves between the four pages from the sidebar and still reaches the shell overview', async () => {
    mockApi()
    open('/requirement')
    await screen.findByRole('heading', { level: 1, name: 'Overview' })
    for (const [label] of CHILDREN.slice(1)) {
      await userEvent.click(screen.getByRole('link', { name: label }))
      expect(await screen.findByRole('heading', { level: 1, name: label })).toBeInTheDocument()
    }
    await userEvent.click(screen.getByRole('link', { name: 'Research Overview' }))
    await waitFor(() => expect(window.location.pathname).toBe('/overview'))
  })

  it('an unknown address below /requirement goes back to the overview', async () => {
    mockApi()
    open('/requirement/nowhere')
    expect(await screen.findByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument()
  })
})
