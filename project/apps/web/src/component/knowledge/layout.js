// Node placement for the knowledge graph, ported from the previous C4 web app.
// Structure views (C1 requirement details, C2 code structure) are drawn as tidy rows and columns;
// the trace-link view is a force layout per connected component, packed into the viewport.

export const KS = {
  repository: { fill: "#4fa3f0", stroke: "#2f7cc4", r: 46, inner: "REPO", title: "Repository", cap: 1 },
  package: { fill: "#5cc8a0", stroke: "#2f9c78", r: 40, inner: "PKG", title: "Package", cap: 1 },
  evolution: { fill: "#f2c14e", stroke: "#c29a2e", r: 30, inner: "EVO", title: "Evolution features" },
  finding: { fill: "#f08187", stroke: "#c95665", r: 32, inner: "!", title: "Finding", cap: 1 },
  analysis: { fill: "#f4a3a8", stroke: "#c95665", r: 30, inner: "FIND", title: "Analysis finding" },
  document: { fill: "#5cc8a0", stroke: "#2f9c78", r: 34, inner: "DOC", title: "Document", cap: 1 },
  story: { fill: "#f5a15a", stroke: "#c47a35", r: 34, inner: "STORY", title: "User story" },
  criterion: { fill: "#f2d36b", stroke: "#c2a63b", r: 30, inner: "AC", title: "Acceptance criterion" },
  task: { fill: "#a58be8", stroke: "#7b62c4", r: 30, inner: "TASK", title: "Technical task" },
  risk: { fill: "#7fd0c8", stroke: "#4aa39a", r: 30, inner: "RISK", title: "Risk" },
};

export const PALETTE = {
  ok: "#8b939e", bad: "#c95665", warn: "#d8a456", faint: "#9ca3af", blue: "#e0d58d", blueDark: "#baad61",
  green: "#b9d2a9", greenDark: "#8faa7f", surface: "#f6f6f7", text: "#31323a", muted: "#646671", canvas: "#ffffff",
};

const byLabel = (a, b) => String(a.label).localeCompare(String(b.label), undefined, { numeric: true });

export function radiusOf(node) {
  if (KS[node.kind]) return KS[node.kind].r;
  if (node.kind === "decayflag") return 25;
  return node.kind === "requirement" ? 40 : 38;
}

function layoutStructured(nodes, edges) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const rels = edges.filter((e) => e.category === "rel");
  const kids = (id, rel) => rels.filter((e) => e.from === id && e.rel === rel).map((e) => byId.get(e.to)).filter(Boolean);
  const placed = new Set();
  const put = (n, x, y) => {
    n.x = x;
    n.y = y;
    placed.add(n.id);
  };
  let right = 0;

  // C1: one row per requirement, its story, criteria, task, findings and risk to the right; the document on the left
  const reqs = nodes.filter((n) => n.kind === "requirement").sort(byLabel);
  const ROW = 100;
  if (reqs.some((r) => rels.some((e) => e.from === r.id))) {
    const PER = 13;
    let w = 0;
    reqs.forEach((r, i) => {
      const block = Math.floor(i / PER);
      const x0 = block * 1150;
      const y = (i % PER) * ROW;
      put(r, x0, y);
      let x = x0 + 130;
      for (const rel of ["HAS_STORY", "HAS_CRITERION", "HAS_TASK", "HAS_FINDING", "HAS_RISK"]) {
        for (const child of kids(r.id, rel)) {
          put(child, x, y);
          x += 80;
        }
        x += 25;
      }
      w = Math.max(w, x);
    });
    nodes.filter((n) => n.kind === "document").forEach((d, i) => put(d, -210, ((Math.min(reqs.length, PER) - 1) * ROW) / 2 + i * 110));
    right = w + 320;
  } else {
    reqs.forEach((r, i) => {
      put(r, (i % 7) * 120, Math.floor(i / 7) * 110);
      right = Math.max(right, 7 * 120 + 200);
    });
  }

  // C2: repository on top, packages in rows, each package's files below it (evolution features beside the files)
  const CELL = 190;
  const RH = 88;
  const MAXROWS = 6;
  const MAXW = 2000;
  const TOP = 190;
  const items = nodes.filter((n) => n.kind === "package").sort(byLabel).map((p) => {
    const files = kids(p.id, "CONTAINS").filter((n) => n.kind === "code").sort(byLabel);
    const cols = Math.max(1, Math.ceil(files.length / MAXROWS));
    return { p, files, cols, w: cols * CELL + 30, h: 120 + Math.min(files.length, MAXROWS) * RH };
  });
  const c2 = [];
  let x = 0;
  let y = TOP;
  let rowH = 0;
  let total = 0;
  for (const it of items) {
    if (x && x + it.w > MAXW) {
      total = Math.max(total, x);
      x = 0;
      y += rowH + 40;
      rowH = 0;
    }
    put(it.p, x + (it.w - 30) / 2 - 20, y);
    c2.push(it.p);
    it.files.forEach((f, i) => {
      const fx = x + Math.floor(i / MAXROWS) * CELL;
      const fy = y + 120 + (i % MAXROWS) * RH;
      put(f, fx, fy);
      c2.push(f);
      const evo = kids(f.id, "HAS_EVOLUTION")[0];
      if (evo) {
        put(evo, fx + 88, fy + 8);
        c2.push(evo);
      }
    });
    x += it.w;
    rowH = Math.max(rowH, it.h);
  }
  total = Math.max(total, x, 400);
  nodes.filter((n) => n.kind === "repository").forEach((n, i) => {
    put(n, total / 2 + i * 120, 0);
    c2.push(n);
  });
  nodes.filter((n) => n.kind === "finding").forEach((n, i) => {
    put(n, total / 2 + 220 + i * 100, 30);
    c2.push(n);
  });
  const dx = reqs.length && right ? right : 0;
  if (dx) c2.forEach((n) => { n.x += dx; });

  // anything else (decay records, code files that no package contains) goes in a row underneath
  const rest = nodes.filter((n) => !placed.has(n.id));
  const maxY = Math.max(0, ...nodes.filter((n) => placed.has(n.id)).map((n) => n.y));
  rest.forEach((n, i) => put(n, (i % 12) * 100, maxY + 170 + Math.floor(i / 12) * 100));
}

function layoutForce(nodes, edges, aspect) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const adjacent = new Map(nodes.map((n) => [n.id, []]));
  for (const e of edges) {
    adjacent.get(e.from)?.push(e.to);
    adjacent.get(e.to)?.push(e.from);
  }
  const visited = new Set();
  const components = [];
  for (const first of nodes) {
    if (visited.has(first.id)) continue;
    const queue = [first];
    const group = [];
    visited.add(first.id);
    for (let i = 0; i < queue.length; i++) {
      const n = queue[i];
      group.push(n);
      for (const id of adjacent.get(n.id)) {
        if (!visited.has(id)) {
          visited.add(id);
          queue.push(byId.get(id));
        }
      }
    }
    const ids = new Set(group.map((n) => n.id));
    const links = edges.filter((e) => ids.has(e.from) && ids.has(e.to)).map((e) => ({ a: byId.get(e.from), b: byId.get(e.to) }));
    group.forEach((n, i) => {
      const angle = (i / group.length) * Math.PI * 2;
      n.x = Math.cos(angle) * 100;
      n.y = Math.sin(angle) * 100;
      n.vx = 0;
      n.vy = 0;
    });
    for (let iteration = 0; iteration < 180; iteration++) {
      const alpha = 1 - iteration / 200;
      for (let i = 0; i < group.length; i++) {
        for (let j = i + 1; j < group.length; j++) {
          const a = group[i];
          const b = group[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy) || 1;
          const force = Math.min(12, 3200 / (dist * dist)) * alpha;
          a.vx += (dx / dist) * force;
          a.vy += (dy / dist) * force;
          b.vx -= (dx / dist) * force;
          b.vy -= (dy / dist) * force;
        }
      }
      for (const { a, b } of links) {
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 1;
        const force = (dist - 170) * 0.045 * alpha;
        a.vx += (dx / dist) * force;
        a.vy += (dy / dist) * force;
        b.vx -= (dx / dist) * force;
        b.vy -= (dy / dist) * force;
      }
      for (const n of group) {
        n.x += Math.max(-12, Math.min(12, n.vx));
        n.y += Math.max(-12, Math.min(12, n.vy));
        n.vx *= 0.5;
        n.vy *= 0.5;
      }
    }
    const minX = Math.min(...group.map((n) => n.x));
    const minY = Math.min(...group.map((n) => n.y));
    const width = Math.max(120, Math.max(...group.map((n) => n.x)) - minX + (group.length === 1 ? 120 : 160));
    const height = Math.max(110, Math.max(...group.map((n) => n.y)) - minY + (group.length === 1 ? 110 : 150));
    components.push({ group, minX, minY, width, height });
  }
  components.sort((a, b) => b.height - a.height);
  const area = components.reduce((sum, c) => sum + c.width * c.height, 0);
  const rowWidth = Math.max(...components.map((c) => c.width), Math.sqrt(area * aspect) * 1.15);
  let x = 0;
  let y = 0;
  let rowHeight = 0;
  for (const c of components) {
    if (x && x + c.width > rowWidth) {
      x = 0;
      y += rowHeight + 15;
      rowHeight = 0;
    }
    for (const n of c.group) {
      n.x = n.x - c.minX + x + 80;
      n.y = n.y - c.minY + y + 65;
    }
    x += c.width + 15;
    rowHeight = Math.max(rowHeight, c.height);
  }
}

/** Sets x and y on every node (mutates). */
export function layoutGraph(nodes, edges, aspect = 1.6) {
  if (nodes.length === 0) return;
  if (edges.some((e) => e.category === "rel")) layoutStructured(nodes, edges);
  else layoutForce(nodes, edges, aspect);
}
