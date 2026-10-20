import { describe, expect, it } from "vitest";
import { layoutGraph, radiusOf } from "../component/knowledge/layout";

describe("knowledge graph force layout", () => {
  it("never leaves two nodes on top of each other, even in a dense cluster", () => {
    const requirements = Array.from({ length: 24 }, (_, i) => ({ id: `R${i}`, kind: "requirement", label: `R${i}` }));
    const files = Array.from({ length: 6 }, (_, i) => ({ id: `F${i}`, kind: "code", label: `F${i}` }));
    const nodes = [...requirements, ...files];
    const edges = requirements.flatMap((r, i) => [0, 1, 2].map((k) => ({ from: r.id, to: files[(i + k) % files.length].id, category: "verified" })));

    layoutGraph(nodes, edges);

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const distance = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y);
        expect(distance).toBeGreaterThanOrEqual(radiusOf(nodes[i]) + radiusOf(nodes[j]));
      }
    }
  });
});
