import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { GlobalActivity } from "../component/traceability/Activity";
import { announceActivity } from "../component/traceability/activityBus";

describe("GlobalActivity dock", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ state: "idle" }) })));
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows nothing while idle and appears at once when a job is announced, on any page", async () => {
    render(<MemoryRouter initialEntries={["/knowledge-graph"]}><GlobalActivity /></MemoryRouter>);
    expect(screen.queryByText(/Starting to link requirements/)).toBeNull();

    await act(async () => announceActivity({ kind: "link", project: "demo" }));
    expect(screen.getAllByText("Starting to link requirements").length).toBeGreaterThan(0);

    await act(async () => announceActivity(null));
    expect(screen.queryByText(/Starting to link requirements/)).toBeNull();
  });
});
