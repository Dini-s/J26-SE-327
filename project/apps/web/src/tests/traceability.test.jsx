import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ProjectContext } from "../api/c4";
import TraceabilityLink, { RunResult } from "../pages/TraceabilityLink";
import TraceabilityLabeling from "../pages/TraceabilityLabeling";
import RequirementText from "../component/traceability/RequirementText";
import { codeLocation } from "../component/traceability/utils";

const project = 'aspire/long-project-name';
const first = { requirement: 'REQ-1', requirementText: 'Calculate $\\text{weight} / \\text{height}^2$.', code: `${project}:src/BMICalculator.java`, confidence: 0.6, status: 'pending_review', textHash: 'version-hash', label: null, reason: 'Implements the formula.' };
const second = { ...first, requirement: 'REQ-2', code: `${project}:Person.java` };
const stats = { labelled: 0, sample: 2, correct: 0, wrong: 0, unsure: 0, precision: null, ci95: null, byConfidence: [] };
const fixtureRun = { id: 'run-1', state: 'finished', started: '2026-10-20T00:00:00Z', finished: '2026-10-20T00:05:28Z', linked: 2, done: 3, total: 3, requirements: ['REQ-1'], candidates: [
  { target: first.code, requirement: 'REQ-1', decision: 'linked', confidence: 0.6, reason: 'Formula implementation', seconds: 14 },
  { target: second.code, requirement: 'REQ-1', decision: 'not linked', confidence: 0.1, reason: 'Only data fields', seconds: 279 },
  { target: `${project}:BMIMainApp.java`, requirement: 'REQ-1', decision: 'linked', confidence: 0.9, reason: 'Calls calculator', seconds: 32 },
] };
let posts, items, unlinked, runs, write, fullCode;
const deferred = () => { let resolve; const promise = new Promise((r) => { resolve = r; }); return { resolve, promise }; };
const response = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const openReview = async (name) => { const button = await screen.findByRole('button', { name }); await waitFor(() => expect(button.disabled).toBe(false)); fireEvent.click(button); };
function tree(Component, selected = project) {
  return <ProjectContext.Provider value={{ project: selected, projects: [{ project: selected, links: 2 }] }}><MemoryRouter><Component /></MemoryRouter></ProjectContext.Provider>;
}
beforeEach(() => {
  posts = []; items = [{ ...first }, { ...second }]; runs = []; unlinked = { requirements: 1, unlinked: 0, codeFiles: 3 }; fullCode = 'class Calculator {}\n' + ' '.repeat(7000) + '// END OF FULL SOURCE';
  write = async () => response({ ok: true });
  vi.stubGlobal('fetch', vi.fn(async (url, init = {}) => {
    if (init.method === 'POST') { posts.push({ url, body: JSON.parse(init.body) }); return write(url, init); }
    const path = String(url);
    if (path.startsWith('/api/labeling')) return response({ items, stats, total: items.length });
    if (path.startsWith('/api/code-text')) return response({ text: fullCode });
    if (path.startsWith('/api/unlinked')) return response(unlinked);
    if (path.startsWith('/api/link-runs')) return response({ runs, texts: { 'REQ-1': first.requirementText } });
    if (path.startsWith('/api/activity')) return response({ state: 'idle' });
    throw new Error(`Unexpected request ${url}`);
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('consistent display', () => {
  it('separates project namespaces and nested filenames', () => {
    expect(codeLocation(first.code)).toEqual({ project, path: 'src/BMICalculator.java', folder: 'src', name: 'BMICalculator.java' });
    expect(codeLocation('C:\\src\\Main.java').name).toBe('Main.java');
    expect(codeLocation(second.code).name).toBe('Person.java');
  });
  it('renders formulas without modifying text or executing markup', async () => {
    const text = 'BMI $\\text{weight} / \\text{height}^2$ <script>alert(1)</script>';
    const { container } = render(<RequirementText text={text} />);
    await waitFor(() => expect(container.querySelector('.katex')).not.toBeNull());
    expect(container.querySelector('script')).toBeNull();
    expect(text).toContain('\\text{weight}');
  });
  it('keeps malformed math readable instead of crashing', () => {
    render(<RequirementText text={'Keep $\\badcommand$ readable'} />);
    expect(screen.getByText(/badcommand/)).toBeTruthy();
  });
});

describe('link creation and run results', () => {
  it('defaults to existing requirements and replaces completed controls with a saved-links action', async () => {
    render(tree(TraceabilityLink));
    await screen.findByText('1 requirement already linked.');
    expect(screen.queryByText('Candidates per requirement')).toBeNull();
    expect(screen.getByRole('link', { name: /View saved links/ })).toBeTruthy();
    expect(screen.queryByRole('textbox', { name: 'Requirement' })).toBeNull();
    fireEvent.click(screen.getByRole('tab', { name: 'New requirement' }));
    expect(screen.getByRole('textbox', { name: 'Requirement' })).toBeTruthy();
  });
  it('scans only the chosen requirements', async () => {
    unlinked = { requirements: 2, unlinked: 2, ids: ['REQ-1', 'REQ-2'], codeFiles: 3 };
    render(tree(TraceabilityLink));
    fireEvent.click(await screen.findByRole('checkbox', { name: 'REQ-2' }));
    fireEvent.click(screen.getByRole('button', { name: 'Link 1 selected' }));
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0].body.requirement_ids).toEqual(['REQ-2']);
  });
  it('handles empty requirements and offers a new requirement tab', async () => {
    unlinked = { requirements: 0, unlinked: 0, codeFiles: 3 };
    render(tree(TraceabilityLink));
    await screen.findByText(/No requirements yet/);
    expect(screen.queryByRole('button', { name: 'Create trace links' })).toBeNull();
  });
  it('resets form state when the selected project changes', async () => {
    const view = render(tree(TraceabilityLink));
    fireEvent.click(screen.getByRole('tab', { name: 'New requirement' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Requirement' }), { target: { value: 'A requirement for the first project' } });
    view.rerender(tree(TraceabilityLink, 'other'));
    expect(screen.getByRole('tab', { name: 'Existing requirements' }).getAttribute('aria-selected')).toBe('true');
    fireEvent.click(screen.getByRole('tab', { name: 'New requirement' }));
    expect(screen.getByRole('textbox', { name: 'Requirement' }).value).toBe('');
  });
  it('shows one result summary and filename decisions, with paths inside details', async () => {
    const { container } = render(<MemoryRouter><RunResult run={fixtureRun} texts={{ 'REQ-1': first.requirementText }} /></MemoryRouter>);
    expect(screen.getByText('2 approved · 0 need review · 3 files checked · 5m 28s')).toBeTruthy();
    expect(screen.getByText('BMICalculator.java')).toBeTruthy();
    expect(screen.getAllByText('Approved')).toHaveLength(2);
    expect(screen.getByText('Not selected')).toBeTruthy();
    expect(screen.queryByText('Step 1 (done)')).toBeNull();
    const path = screen.getByText('src/BMICalculator.java');
    expect(path.closest('details').open).toBe(false);
    await waitFor(() => expect(container.querySelector('.katex')).not.toBeNull());
  });
  it.each(['running', 'stopped'])('represents a %s run without calling unchecked candidates rejected', (state) => {
    const run = { ...fixtureRun, state, finished: null, done: 0, linked: 0, candidates: [{ ...fixtureRun.candidates[0], decision: 'waiting', confidence: null }] };
    render(<MemoryRouter><RunResult run={run} texts={{}} /></MemoryRouter>);
    expect(screen.getByText(state === 'running' ? 'Checking' : 'Not checked')).toBeTruthy();
    expect(screen.queryByText('Not selected')).toBeNull();
  });
});

describe('optional human review', () => {
  it('loads full code and requires an explicit action before showing review choices', async () => {
    render(tree(TraceabilityLabeling));
    await screen.findByText(/END OF FULL SOURCE/);
    expect(fetch.mock.calls.some(([url]) => String(url).includes('&full=1'))).toBe(true);
    expect(screen.queryByRole('button', { name: /^Matches/ })).toBeNull();
    fireEvent.keyDown(window, { key: '1' });
    expect(posts).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Review this link' }));
    expect(screen.getByRole('button', { name: /^Matches/ })).toBeTruthy();
    expect(screen.getByText('Review statistics').closest('details').open).toBe(false);
  });
  it('ignores rapid duplicate decisions, saves without advancing, and sends a versioned graph review', async () => {
    const pending = deferred(); write = () => pending.promise;
    render(tree(TraceabilityLabeling));
    await openReview('Review this link');
    const match = screen.getByRole('button', { name: /^Matches/ });
    fireEvent.click(match); fireEvent.click(match);
    fireEvent.keyDown(window, { key: '2' });
    expect(posts).toHaveLength(1);
    expect(screen.getByRole('button', { name: /^Does not match/ }).disabled).toBe(true);
    pending.resolve(response({ ok: true }));
    await screen.findByText('Approved. USKG and traceability graph updated.');
    expect(posts[0]).toEqual({ url: '/api/label', body: { project, requirement: 'REQ-1', code: first.code, label: 'correct', text_hash: 'version-hash' } });
    expect(screen.getByText('Requirement · REQ-1')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Edit review' })).toBeTruthy();
    expect(screen.getByText('AI confidence 0.60')).toBeTruthy();
  });
  it('retains a prior review on failure and permits a retry', async () => {
    items[0].label = 'correct'; write = async () => response({ detail: 'Disk unavailable' }, 500);
    render(tree(TraceabilityLabeling));
    await openReview('Edit review');
    fireEvent.click(screen.getByRole('button', { name: /^Does not match/ }));
    await screen.findByRole('alert');
    expect(screen.getByRole('button', { name: /^Matches/ }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: /^Does not match/ }).getAttribute('aria-pressed')).toBe('false');
    write = async () => response({ ok: true });
    fireEvent.click(screen.getByRole('button', { name: /^Does not match/ }));
    await screen.findByText(/Rejected. USKG updated/);
    expect(posts).toHaveLength(2);
    expect(posts[1].body.label).toBe('wrong');
  });
  it('ignores the completion of a previous project save', async () => {
    const pending = deferred(); write = () => pending.promise;
    const view = render(tree(TraceabilityLabeling));
    await openReview('Review this link');
    fireEvent.click(screen.getByRole('button', { name: /^Matches/ }));
    items = [{ ...second, requirement: 'OTHER-REQ', code: 'other:Main.java' }];
    view.rerender(tree(TraceabilityLabeling, 'other'));
    await screen.findByText('Requirement · OTHER-REQ');
    pending.resolve(response({ ok: true }));
    await waitFor(() => expect(screen.queryByText('Approved. USKG and traceability graph updated.')).toBeNull());
    expect(screen.queryByRole('button', { name: 'Edit review' })).toBeNull();
  });
  it('makes navigation explicit and resets review controls on selection', async () => {
    render(tree(TraceabilityLabeling));
    await openReview('Review this link');
    fireEvent.click(screen.getByRole('button', { name: 'Next link' }));
    await screen.findByText('Requirement · REQ-2');
    expect(screen.queryByRole('button', { name: /^Matches/ })).toBeNull();
    expect(screen.getByRole('button', { name: 'Review this link' })).toBeTruthy();
  });
  it('handles an empty saved-link sample', async () => {
    items = [];
    render(tree(TraceabilityLabeling));
    await screen.findByText('No candidates to review');
    expect(screen.queryByRole('button', { name: 'Review this link' })).toBeNull();
  });
});

it('shows a source error and retries without blocking inspection', async () => {
  const original = fetch.getMockImplementation();
  let attempts = 0;
  fetch.mockImplementation(async (url, init) => {
    if (String(url).startsWith('/api/code-text') && attempts++ === 0) return response({ detail: 'Source unavailable' }, 503);
    return original(url, init);
  });
  render(tree(TraceabilityLabeling));
  await screen.findByText(/Unable to load source/);
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  await screen.findByText(/END OF FULL SOURCE/);
});

it('identifies a capped review sample using the eligible link count', async () => {
  const original = fetch.getMockImplementation();
  fetch.mockImplementation((url, init) => String(url).startsWith('/api/labeling') ? Promise.resolve(response({ items, stats, total: 80 })) : original(url, init));
  render(tree(TraceabilityLabeling));
  await screen.findByText('Review sample · 2');
});

it('shows candidate controls only when existing requirements can be linked', async () => {
  unlinked = { requirements: 4, unlinked: 2, codeFiles: 3 };
  render(tree(TraceabilityLink));
  await screen.findByText('2 of 4 requirements need links.');
  expect(screen.getByRole('button', { name: 'Create trace links' }).disabled).toBe(false);
});

it('ignores stale JSON completion after a request changes', async () => {
  const { useApi } = await import('../api/c4');
  const old = deferred();
  fetch.mockImplementation(async (url) => String(url) === '/old' ? { ok: true, json: () => old.promise } : response({ value: 'new-project' }));
  function Probe({ path }) {
    const { data } = useApi(path);
    return <p>{data?.value || 'loading'}</p>;
  }
  const view = render(<Probe path="/old" />);
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  view.rerender(<Probe path="/new" />);
  await screen.findByText('new-project');
  old.resolve({ value: 'old-project' });
  await waitFor(() => expect(screen.getByText('new-project')).toBeTruthy());
  expect(screen.queryByText('old-project')).toBeNull();
});

it('keeps the reviewed candidate selected when the pending sample advances', async () => {
  write = async () => { items = [{ ...second }]; return response({ ok: true, status: 'verified' }); };
  render(tree(TraceabilityLabeling));
  await openReview('Review this link');
  fireEvent.click(screen.getByRole('button', { name: /^Matches/ }));
  await screen.findByText('Approved. USKG and traceability graph updated.');
  expect(screen.getByText('Requirement · REQ-1')).toBeTruthy();
});
