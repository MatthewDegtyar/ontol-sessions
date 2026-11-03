"use client";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { getDetail, getForks, getView } from "./data";

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

const ICONS = {
  shipments: <><path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5z" /><path d="M3 7.5 12 12l9-4.5M12 12v9" /></>,
  invoices: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6" /></>,
  exports: <><path d="M12 15V3M7.5 7.5 12 3l4.5 4.5" /><path d="M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5" /></>,
  audit: <><path d="M12 3 4.5 6v5.5c0 4.5 3 8 7.5 9.5 4.5-1.5 7.5-5 7.5-9.5V6z" /><path d="m9 12 2 2 4-4" /></>,
  users: <><circle cx="9" cy="8" r="3.5" /><path d="M3 20c.5-4 3-6 6-6s5.500 2 6 6" /><path d="M16 4.800a3.500 3.500 0 0 1 0 6.400M18 14.500c1.800.8 2.800 2.800 3 5.500" /></>,
  portal: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 9h18M7 6.500h.01M10 6.500h.01" /></>,
  other: <><circle cx="12" cy="12" r="8" /></>,
};
const TITLES = { shipments: "Shipments", invoices: "Billing", exports: "Data exports", audit: "Compliance", users: "Team", portal: "Customer portal" };

const Icon = ({ id, size = 18 }) => (
  <svg className="icon" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.700" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {ICONS[id] || ICONS.other}
  </svg>
);

/* Put each client node next to what it grows from, so the lines cross as little as possible. */
function orderClient(view) {
  const order = view.main.flatMap((g) => g.items.map((i) => i.key));
  const rank = (c) => (c.edge ? order.indexOf(c.edge.from) : 999);
  const roots = view.client.filter((c) => c.edge?.kind !== "chained").sort((a, b) => rank(a) - rank(b));
  return roots.flatMap((r) => [r, ...view.client.filter((c) => c.edge?.kind === "chained" && c.edge.from === r.key)]);
}

/* Line numbers come from the diff's own hunk headers. */
function numbered(diff) {
  let o = 0, n = 0;
  return diff.map((line) => {
    const hunk = line.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)/);
    if (hunk) { o = +hunk[1]; n = +hunk[2]; return { type: "hunk", text: line }; }
    if (line[0] === "+") return { type: "plus", n: n++, text: line.slice(1) };
    if (line[0] === "-") return { type: "minus", o: o++, text: line.slice(1) };
    return { type: "ctx", o: o++, n: n++, text: line.slice(1) };
  });
}

const Delta = ({ add, del }) => (
  <span className="delta"><span className="pos">+{add}</span> <span className="neg">−{del}</span></span>
);

export function Files({ files }) {
  const add = files.reduce((s, f) => s + f.additions, 0);
  const del = files.reduce((s, f) => s + f.deletions, 0);
  return (
    <section className="module">
      <header className="module-head">
        <h3>{plural(files.length, "file")} in this extension</h3>
        <Delta add={add} del={del} />
      </header>
      {files.map((f, i) => {
        const slash = f.path.lastIndexOf("/") + 1;
        return (
          <details key={f.path} className="file" open={i === 0}>
            <summary>
              <span className={`pill ${f.status}`} title={f.status}>{{ added: "New", removed: "Gone", renamed: "Moved" }[f.status] || "Edit"}</span>
              <span className="path"><span className="dir">{f.path.slice(0, slash)}</span>{f.path.slice(slash)}</span>
              <Delta add={f.additions} del={f.deletions} />
            </summary>
            <div className="diff" tabIndex={0} role="region" aria-label={`Diff of ${f.path}`}>
              <table>
                <tbody>
                  {numbered(f.diff).map((l, j) => l.type === "hunk"
                    ? <tr key={j} className="hunk"><td colSpan={3}>{l.text}</td></tr>
                    : <tr key={j} className={l.type}><td className="ln">{l.o ?? ""}</td><td className="ln">{l.n ?? ""}</td><td className="code">{l.type === "plus" ? "+ " : l.type === "minus" ? "− " : "  "}{l.text}</td></tr>)}
                </tbody>
              </table>
              {f.diff.length === 0 && <p className="diff-note">No text changes to show.</p>}
              {f.truncated && <p className="diff-note">This diff is long, so only the start is shown.</p>}
            </div>
          </details>
        );
      })}
    </section>
  );
}

function Detail({ fork, id, nameOf, onClose }) {
  const [d, setD] = useState(null);
  useEffect(() => { setD(null); getDetail(fork, id).then(setD); }, [fork, id]);
  if (!d) return <aside className="detail"><p className="muted">Loading…</p></aside>;
  return (
    <aside className="detail">
      <button className="close" onClick={onClose} aria-label="Close details">×</button>
      <p className={`status ${d.status}`}>{d.status === "added" ? "Main doesn't have this" : "Different from main"}</p>
      <h2>{d.name}</h2>
      {(d.summary || d.changed) && <p>{d.changed || d.summary}</p>}
      {d.edge && d.edge.kind !== "changed" && (
        <p className="built-on">Built on <strong>{nameOf(d.edge.from)}</strong><span>{d.edge.via}</span></p>
      )}
      {d.advice && <p className={`advice ${d.advice.kind}`}>{d.advice.text}</p>}
      {d.work && (
        <>
          <h3>What the client asked for</h3>
          <p>{d.work.asked}</p>
          <p className="muted">{d.work.ticket} · owned by {d.work.owner}</p>
          <h3>Why it was built this way</h3>
          <p>{d.work.why}</p>
          {d.work.quote && <blockquote>{d.work.quote}<cite>From the coding session</cite></blockquote>}
        </>
      )}
      {d.siblings.map((s) => <p key={s.key} className="muted">{s.client} has its own version: {s.name} ({s.ticket}).</p>)}
      <Files files={d.files} />
    </aside>
  );
}

function Graph({ view, open, setOpen }) {
  const board = useRef(null);
  const [lines, setLines] = useState([]);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [hover, setHover] = useState(null);
  const client = orderClient(view);
  const live = open || hover;
  const activeEdge = (c) => live && (c.key === live || c.edge?.from === live);
  const connected = new Set(client.filter(activeEdge).flatMap((c) => [c.key, c.edge?.from]));
  // A changed node shares its key with the main node it grows from, so nodes are addressed by side.
  const node = (side, key) => board.current?.querySelector(`[data-node="${side}:${CSS.escape(key)}"]`);

  const measure = useCallback(() => {
    const el = board.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    setSize({ w: box.width, h: box.height });
    const pos = (n) => { const r = n.getBoundingClientRect(); return { l: r.left - box.left, r: r.right - box.left, y: r.top - box.top + r.height / 2 }; };
    const out = [];
    for (const c of client) {
      if (!c.edge) continue;
      const to = node("client", c.key);
      const from = node(c.edge.kind === "chained" ? "client" : "main", c.edge.from);
      if (!to || !from) continue;
      const a = pos(from), b = pos(to);
      if (c.edge.kind === "chained") {
        out.push({ c, d: `M${a.l} ${a.y} C${a.l - 34} ${a.y} ${b.l - 34} ${b.y} ${b.l} ${b.y}`, x: b.l });
      } else {
        const mid = (a.r + b.l) / 2;
        out.push({ c, d: `M${a.r} ${a.y} C${mid} ${a.y} ${mid} ${b.y} ${b.l} ${b.y}`, x: a.r, ax: a.r, ay: a.y, bx: b.l, by: b.y });
      }
    }
    setLines(out);
  }, [view]); // eslint-disable-line

  useLayoutEffect(() => {
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(board.current);
    return () => ro.disconnect();
  }, [measure]);

  const nodeClass = (key) => (live && !connected.has(key) && key !== live ? " dim" : "");
  const hoverProps = (key) => ({ onMouseEnter: () => setHover(key), onMouseLeave: () => setHover(null), onFocus: () => setHover(key), onBlur: () => setHover(null) });
  const linked = new Set(client.map((c) => c.edge?.from));

  return (
    <div className="board" ref={board}>
      <svg className="wires" width={size.w} height={size.h} aria-hidden="true">
        {lines.map((l) => {
          const on = activeEdge(l.c);
          return (
            <g key={l.c.key} className={`wire ${l.c.status} ${on ? "on" : live ? "off" : ""}`}>
              <path className="glow" d={l.d} />
              <path className="core" d={l.d} pathLength="1" />
              {l.ax !== undefined && <><circle cx={l.ax} cy={l.ay} r="4" /><circle cx={l.bx} cy={l.by} r="4" /></>}
            </g>
          );
        })}
      </svg>

      <div className="col">
        <p className="col-title">Harbor monolith</p>
        {view.main.map((g) => (
          <section className="group" key={g.id}>
            <h2><span className="badge"><Icon id={g.id} /></span>{TITLES[g.id] || g.id}</h2>
            {g.items.map((c) => {
              const clickable = linked.has(c.key);
              const cls = `node base ${c.status === "changed" ? "touched changedbase" : clickable ? "touched" : ""}${nodeClass(c.key)}`;
              return clickable
                ? <button key={c.key} className={cls} data-node={`main:${c.key}`} aria-pressed={live === c.key} onClick={() => setOpen(c.status === "changed" ? c.key : null)} {...hoverProps(c.key)}>{c.name}</button>
                : <div key={c.key} className={cls} data-node={`main:${c.key}`}>{c.name}</div>;
            })}
          </section>
        ))}
      </div>

      <div className="col client">
        <p className="col-title accent">{view.name} extensions</p>
        {client.map((c) => (
          <button key={c.key} data-node={`client:${c.key}`} aria-pressed={open === c.key} onClick={() => setOpen(c.key)} {...hoverProps(c.key)}
            className={`node ext ${c.status} ${c.edge?.kind === "chained" ? "chained" : ""} ${open === c.key ? "active" : ""}${nodeClass(c.key)}`}>
            <span className="ext-top"><Icon id={c.group} size={16} /><strong>{c.status === "changed" ? c.changed : c.name}</strong></span>
            <span className="via">{c.status === "changed" ? `Changes “${c.name}”` : c.edge?.via || "No shared code found"}</span>
            {c.also.length > 0 && <span className="twice">Also built for {c.also.join(", ")}</span>}
            <span className="filecount">{plural(c.files.count, "file")} <Delta add={c.files.additions} del={c.files.deletions} /></span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ForkExplorer({ compact = false, brand = null }) {
  const [forks, setForks] = useState([]);
  const [fork, setFork] = useState(null);
  const [view, setView] = useState(null);
  const [open, setOpen] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => { getForks().then((f) => { setForks(f); setFork(f[0].id); }).catch(() => setError(true)); }, []);
  useEffect(() => { if (fork) { setOpen(null); getView(fork).then(setView).catch(() => setError(true)); } }, [fork]);

  if (error) return <div className="app-main"><p>Couldn&apos;t load the demo. Refresh to try again.</p></div>;
  if (!view) return <div className={`app-main ${compact ? "compact" : ""}`}><p className="muted loading">Loading…</p></div>;
  const { added, changed, same } = view.counts;
  const nameOf = (key) => view.main.flatMap((g) => g.items).concat(view.client).find((c) => c.key === key)?.name || key;
  // The landing page's preview only highlights; the full panel lives on the demo page.
  const showDetail = open && !compact;

  return (
    <div className={showDetail ? "layout with-detail" : "layout"}>
      <div className={`app-main ${compact ? "compact" : ""}`}>
        <div className="top">
          {brand}
          <div className="switch" role="group" aria-label="Choose a client fork">
            {forks.map((f) => <button key={f.id} className={f.id === fork ? "on" : ""} aria-pressed={f.id === fork} onClick={() => setFork(f.id)}>{f.name}</button>)}
          </div>
        </div>
        {!compact && <h1>How {view.name} extended the monolith</h1>}
        <p className="stats">
          <span className="stat add"><b>{added}</b> new {added === 1 ? "capability" : "capabilities"}</span>
          <span className="stat chg"><b>{changed}</b> changed</span>
          <span className="stat"><b>{same}</b> untouched</span>
        </p>
        <Graph key={view.id} view={view} open={open} setOpen={setOpen} />
        {view.unattributed.length > 0 && <p className="muted">Changed but not tied to any extension: {view.unattributed.join(", ")}</p>}
      </div>
      {showDetail && <Detail fork={fork} id={open} nameOf={nameOf} onClose={() => setOpen(null)} />}
    </div>
  );
}
