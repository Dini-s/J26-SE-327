import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { cx } from "./utils";

const plain = (text) => String(text || "").replace(/\$/g, "").replace(/\\text\{([^}]*)\}/g, "$1").replace(/\s+/g, " ").trim();

/** Pick which unlinked requirements to link. Empty selection means "all of them". */
export default function RequirementPicker({ ids, texts = {}, chosen, onChange, disabled = false, max = 20 }) {
  const [query, setQuery] = useState("");
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? ids.filter((id) => `${id} ${texts[id] || ""}`.toLowerCase().includes(q)) : ids;
  }, [ids, texts, query]);
  const full = chosen.length >= max;
  const toggle = (id, on) => onChange(on ? [...chosen, id] : chosen.filter((rid) => rid !== id));
  const selectable = visible.filter((id) => !chosen.includes(id)).slice(0, Math.max(0, max - chosen.length));

  return (
    <div className="c4-picker mt-4" role="group" aria-label="Requirements to link">
      <div className="c4-picker-head">
        <div className="min-w-0">
          <p className="c4-picker-title">Choose requirements</p>
          <p className="c4-picker-sub">{chosen.length ? `${chosen.length} selected` : `None selected: all ${ids.length} will be linked`}{full ? ` (the limit is ${max} at a time)` : ""}</p>
        </div>
        <div className="c4-picker-actions">
          <button type="button" disabled={disabled || !selectable.length} onClick={() => onChange([...chosen, ...selectable])}>{ids.length > max ? `Select first ${max}` : "Select all"}</button>
          <button type="button" disabled={disabled || !chosen.length} onClick={() => onChange([])}>Clear</button>
        </div>
      </div>
      {ids.length > 6 && (
        <label className="c4-picker-search">
          <Search size={14} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by ID or text" aria-label="Search requirements" />
        </label>
      )}
      <ul className="c4-picker-list">
        {visible.map((id) => {
          const on = chosen.includes(id);
          const blocked = disabled || (!on && full);
          return (
            <li key={id}>
              <label className={cx("c4-picker-row", on && "is-on", blocked && "is-blocked")}>
                <input type="checkbox" aria-label={id} checked={on} disabled={blocked} onChange={(event) => toggle(id, event.target.checked)} />
                <span className="c4-picker-id">{id}</span>
                <span className="c4-picker-text">{plain(texts[id]) || "No text stored"}</span>
              </label>
            </li>
          );
        })}
        {!visible.length && <li className="c4-picker-empty">No requirement matches “{query}”.</li>}
      </ul>
    </div>
  );
}
