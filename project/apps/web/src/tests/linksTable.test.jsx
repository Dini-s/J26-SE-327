import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LinksTable from "../component/traceability/LinksTable";

afterEach(cleanup);

const link = (requirement, status, confidence) => ({ requirement, code: `${requirement}.java`, requirementText: `text ${requirement}`, status, confidence });

describe("trace links table order", () => {
  it("groups by status (broken, needs review, approved) and then by confidence, never interleaving them", () => {
    const links = [link("A", "verified", 0.9), link("B", "pending_review", 0.8), link("C", "verified", 0.9), link("D", "pending_review", 0.8), link("E", "decayed", 0)];
    render(<MemoryRouter><LinksTable links={links} /></MemoryRouter>);
    const order = screen.getAllByRole("row").slice(1).map((row) => row.textContent.match(/[A-E]\.java/)?.[0]);
    expect(order).toEqual(["E.java", "B.java", "D.java", "A.java", "C.java"]);
  });

  it("lists only needs-review links under that filter", () => {
    const links = [link("A", "verified", 0.9), link("B", "pending_review", 0.8)];
    render(<MemoryRouter><LinksTable links={links} /></MemoryRouter>);
    expect(screen.getByText(/Needs review \(1\)/)).toBeTruthy();
  });
});
