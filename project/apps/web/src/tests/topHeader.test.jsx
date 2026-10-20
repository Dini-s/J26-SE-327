import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import TopHeader from "../Layouts/TopHeader";

const state = { notifications: [], onLive: null, clear: vi.fn() };

vi.mock("../api/c4", () => ({
  useProject: () => ({ project: "demo" }),
  useRefresh: () => ({ bump: () => {} }),
  useNotifications: (_project, options) => {
    state.onLive = options?.onLive;
    return { notifications: state.notifications, connected: true, clear: state.clear };
  },
}));

const sample = { id: "a", event: "trace_decayed", requirementId: "NEW-014", timestamp: "2026-10-20T13:44:18+00:00" };

describe("TopHeader notifications", () => {
  beforeEach(() => {
    state.notifications = [sample];
    state.clear = vi.fn();
  });
  afterEach(() => cleanup());

  it("closes the panel on an outside click and on Escape", () => {
    render(<TopHeader />);
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    expect(screen.getByRole("dialog", { name: "Notifications" })).toBeTruthy();

    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("dialog", { name: "Notifications" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Notifications" })).toBeNull();
  });

  it("keeps the panel open for clicks inside it", () => {
    render(<TopHeader />);
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    fireEvent.pointerDown(screen.getByText("NEW-014"));
    expect(screen.getByRole("dialog", { name: "Notifications" })).toBeTruthy();
  });

  it("clears all notifications from a visible button", () => {
    render(<TopHeader />);
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(state.clear).toHaveBeenCalledTimes(1);
  });

  it("shows a toast under the bell for a live event and dismisses it", () => {
    vi.useFakeTimers();
    state.notifications = [];
    render(<TopHeader />);
    act(() => state.onLive({ ...sample, id: "live-1" }));
    expect(screen.getByRole("status").textContent).toContain("Trace link broken");

    act(() => vi.advanceTimersByTime(5000));
    expect(screen.queryByRole("status")).toBeNull();
    vi.useRealTimers();
  });
});
