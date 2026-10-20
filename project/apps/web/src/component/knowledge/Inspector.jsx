import { linkLabel } from "../traceability/linkStatus";
import { useApi } from "../../api/c4";
import StatusBadge from "../common/StatusBadge";
import { shortName } from "../traceability/utils";
import { KS } from "./layout";

const dirOf = (id) => String(id).replace(/\\/g, "/").split("/").slice(0, -1).join("/");
const clock = (iso) => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "");
const conf = (x) => (x != null ? Number(x).toFixed(2) : "-");

const Tag = ({ children, tone = "slate" }) => {
  const style = { slate: "bg-slate-100 text-slate-600", indigo: "bg-indigo-50 text-indigo-600", amber: "bg-amber-50 text-amber-700" }[tone];
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${style}`}>{children}</span>;
};

function LinkRow({ edge, other }) {
  return (
    <div className="border-t border-slate-100 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="break-all font-mono text-[12px] text-slate-800">{other}</span>
        <StatusBadge type={edge.category === "verified" ? "success" : "warning"}>{linkLabel(edge.category)}</StatusBadge>
      </div>
      <p className="mt-0.5 text-[12px] text-slate-500">
        confidence {conf(edge.confidence)}
        {edge.reasoning ? ` - ${edge.reasoning}` : ""}
      </p>
    </div>
  );
}

function Props({ node }) {
  const rows = Object.entries(node.props || {}).filter(([, v]) => v !== null && v !== "" && v !== undefined);
  if (!rows.length) return null;
  return (
    <table className="mt-3 w-full text-[12px]">
      <tbody>
        {rows.slice(0, 18).map(([k, v]) => (
          <tr key={k} className="border-t border-slate-100 align-top">
            <td className="py-1 pr-3 text-slate-500">{k}</td>
            <td className="break-all py-1 text-slate-800">{String(v)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Relations({ node, nodes, edges }) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const rels = edges.filter((e) => e.category === "rel" && (e.from === node.id || e.to === node.id));
  if (!rels.length) return null;
  return (
    <div className="mt-3">
      <p className="text-[12px] font-semibold text-slate-700">Relationships</p>
      {rels.slice(0, 25).map((e, i) => {
        const outgoing = e.from === node.id;
        const other = byId.get(outgoing ? e.to : e.from);
        return (
          <p key={i} className="border-t border-slate-100 py-1 text-[12px] text-slate-600">
            <span className="font-mono text-slate-400">{outgoing ? e.rel : `${e.rel} (from)`}</span> {other ? shortName(other.label) : "?"}
          </p>
        );
      })}
    </div>
  );
}

function FullCode({ node }) {
  const codeId = String(node.id).replace(/^c:/, "");
  const { data, loading, error } = useApi(`/api/code-text?code=${encodeURIComponent(codeId)}&full=1`);
  return (
    <div className="mt-3">
      <p className="mb-1 text-[12px] font-semibold text-slate-700">Full source code</p>
      {loading && <p className="text-[12px] text-slate-500">Loading source code...</p>}
      {error && <p role="alert" className="text-[12px] text-red-600">{error}</p>}
      {data && <pre className="max-h-[480px] overflow-auto whitespace-pre rounded-lg bg-slate-50 p-3 font-mono text-[11px] leading-relaxed text-slate-700"><code>{data.text || "No source code stored for this file."}</code></pre>}
    </div>
  );
}

export default function Inspector({ selected, nodes, edges }) {
  if (!selected) {
    return (
      <div className="space-y-2 text-[13px] text-slate-500">
        <p className="text-sm font-semibold text-slate-800">Inspector</p>
        <p>Select a node to inspect its properties and connections, or an edge to read the LLM's reason for a link.</p>
        <p className="text-[12px] text-slate-400">Move nodes individually to organize the graph. Scroll to zoom, or use Fit to see every node.</p>
      </div>
    );
  }

  const byId = new Map(nodes.map((n) => [n.id, n]));

  if (selected.type === "edge") {
    const e = edges[selected.index];
    if (!e) return null;
    const name = (id) => byId.get(id)?.label || id;
    if (e.category === "rel") {
      return (
        <div className="space-y-2 text-[13px]">
          <Tag>{e.rel}</Tag>
          <p className="text-sm font-semibold text-slate-900">{shortName(name(e.from))} to {shortName(name(e.to))}</p>
          {e.confidence != null && <p className="text-[12px] text-slate-500">similarity {conf(e.confidence)}</p>}
        </div>
      );
    }
    return (
      <div className="space-y-2 text-[13px]">
        <Tag tone="indigo">VERIFIED_TRACE</Tag>
        <p className="break-all font-mono text-sm font-semibold text-slate-900">{String(e.from).slice(2)} to {shortName(String(e.to).slice(2))}</p>
        <p className="flex items-center gap-2">
          <StatusBadge type={e.category === "verified" ? "success" : "warning"}>{linkLabel(e.category)}</StatusBadge>
          <span className="text-slate-500">confidence {conf(e.confidence)}</span>
        </p>
        {e.checked && <p className="text-[12px] text-slate-400">last checked {clock(e.checked)}</p>}
        <p className="leading-relaxed text-slate-600">{e.reasoning || "No reason stored."}</p>
      </div>
    );
  }

  const n = byId.get(selected.id);
  if (!n) return null;
  const linkEdges = edges.filter((e) => (["verified", "decayed", "pending_review", "deferred", "rejected"].includes(e.category)) && (e.from === n.id || e.to === n.id));

  if (n.kind === "requirement") {
    return (
      <div className="text-[13px]">
        <Tag tone="indigo">Requirement</Tag>
        <p className="mt-2 font-mono text-sm font-semibold text-slate-900">{n.label}</p>
        <p className="mt-1 leading-relaxed text-slate-700">{n.text}</p>
        <Props node={n} />
        <p className="mb-1 mt-3 text-[12px] font-semibold text-slate-700">Trace links ({linkEdges.length})</p>
        {n.orphan && linkEdges.length === 0 && <p className="rounded-lg border border-red-100 bg-red-50 p-2 text-red-700">No verified link for this requirement.</p>}
        {linkEdges.map((e, i) => (
          <LinkRow key={i} edge={e} other={shortName(String(e.to).slice(2))} />
        ))}
        <Relations node={n} nodes={nodes} edges={edges} />
      </div>
    );
  }

  if (n.kind === "decayflag") {
    return (
      <div className="text-[13px]">
        <Tag tone="amber">Decay record</Tag>
        <p className="mt-2 break-all font-mono text-sm font-semibold text-slate-900">{shortName(n.codeEntityId || "")}</p>
        <p className="mt-1 text-[12px] text-slate-500">flagged {clock(n.flaggedAt)}, confidence before {conf(n.previousConfidence)}</p>
        <p className="mt-2 leading-relaxed text-slate-700">{n.text}</p>
      </div>
    );
  }

  if (KS[n.kind]) {
    return (
      <div className="text-[13px]">
        <Tag>{KS[n.kind].title}</Tag>
        <p className="mt-2 text-sm font-semibold text-slate-900">{n.label}</p>
        {n.text && n.text !== n.label && <p className="mt-1 leading-relaxed text-slate-700">{n.text}</p>}
        <Props node={n} />
        <Relations node={n} nodes={nodes} edges={edges} />
      </div>
    );
  }

  return (
    <div className="text-[13px]">
      <Tag>Code file</Tag>
      <p className="mt-2 break-all font-mono text-sm font-semibold text-slate-900">{shortName(n.label)}</p>
      <p className="break-all text-[12px] text-slate-400">{dirOf(n.label)}</p>
      <Props node={n} />
      <p className="mb-1 mt-3 text-[12px] font-semibold text-slate-700">Linked requirements ({linkEdges.length})</p>
      {linkEdges.map((e, i) => (
        <LinkRow key={i} edge={e} other={String(e.from).slice(2)} />
      ))}
      <FullCode key={n.id} node={n} />
      <Relations node={n} nodes={nodes} edges={edges} />
    </div>
  );
}
