"use client";
import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Files } from "./product";
import { Logo } from "./site";

const get = (url) => fetch(url).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
// A running production site can't see files added after it starts, so live mode reads results from the API.
const results = process.env.NEXT_PUBLIC_LIVE_API === "1" ? "/api/results" : "/pairs";
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const FIRST_SHOWN = 12;
const Delta = ({ add, del }) => <span className="delta"><span className="pos">+{add}</span> <span className="neg">−{del}</span></span>;

function ModulePanel({ pair, moduleId, onClose }) {
  const [m, setM] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => { setM(null); setFailed(false); get(`${results}/${pair.id}/${moduleId}.json`).then(setM).catch(() => setFailed(true)); }, [pair.id, moduleId]);
  if (failed) return <aside className="detail"><button className="close" onClick={onClose} aria-label="Close details">×</button><p>We couldn&apos;t load this area. Refresh to try again.</p></aside>;
  if (!m) return <aside className="detail"><p className="muted">Loading…</p></aside>;
  return (
    <aside className="detail">
      <button className="close" onClick={onClose} aria-label="Close details">×</button>
      <p className={`status ${m.is_new ? "added" : "changed"}`}>{m.is_new ? "New area: main has nothing here" : "Extends an existing area of main"}</p>
      <h2>{m.name}</h2>
      {m.surfaces.length > 0 && (
        <>
          <h3>What it adds</h3>
          <div className="chips">{m.surfaces.map((s) => <span className="chip" key={s.kind + s.name}><b>{s.kind}</b> {s.name}</span>)}</div>
        </>
      )}
      {m.commits.length > 0 && (
        <>
          <h3>Why: {plural(m.commits.length, "commit")} on the fork</h3>
          <ul className="commits">
            {m.commits.slice(0, 8).map((c) => (
              <li key={c.sha}>
                <a href={`https://github.com/${pair.fork}/commit/${c.sha}`} rel="noreferrer" target="_blank">{c.subject}</a>
                <small>{c.sha} · {c.author} · {c.date}{c.refs.length > 0 ? ` · ${c.refs.join(", ")}` : ""}</small>
              </li>
            ))}
          </ul>
        </>
      )}
      <Files files={m.files} />
      {m.cut_short && <p className="muted">This result hit the file limit, so some files aren&apos;t shown.</p>}
    </aside>
  );
}

export function PairView({ id }) {
  const [pair, setPair] = useState(null);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState(null);
  const [all, setAll] = useState(false);
  const board = useRef(null);
  const [lines, setLines] = useState([]);
  const [size, setSize] = useState({ w: 0, h: 0 });

  useEffect(() => { get(`${results}/${id}/summary.json`).then(setPair).catch(() => setError(true)); }, [id]);
  const modules = pair ? (all ? pair.modules : pair.modules.slice(0, FIRST_SHOWN)) : [];

  const measure = useCallback(() => {
    const el = board.current;
    if (!el) return;
    const box = el.getBoundingClientRect();
    setSize({ w: box.width, h: box.height });
    setLines([...el.querySelectorAll("[data-from]")].flatMap((from) => {
      const to = el.querySelector(`[data-to="${from.dataset.from}"]`);
      if (!to) return [];
      const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
      const x1 = a.right - box.left, y1 = a.top - box.top + a.height / 2, x2 = b.left - box.left, y2 = b.top - box.top + b.height / 2, mid = (x1 + x2) / 2;
      return [{ id: from.dataset.from, d: `M${x1} ${y1} C${mid} ${y1} ${mid} ${y2} ${x2} ${y2}` }];
    }));
  }, []);
  useLayoutEffect(() => {
    measure();
    if (!board.current) return;
    const ro = new ResizeObserver(measure);
    ro.observe(board.current);
    return () => ro.disconnect();
  }, [measure, modules.length]);

  if (error) return <div className="app-main"><Logo /><p>We couldn&apos;t find this comparison.</p></div>;
  if (!pair) return <div className="app-main"><p className="muted">Loading…</p></div>;
  const ignored = Object.entries(pair.ignored);
  const fresh = pair.modules.filter((m) => m.is_new).length;

  return (
    <div className={open ? "layout with-detail" : "layout"}>
      <div className="app-main">
        <div className="pair-top"><Logo /><Link href="/pairs" className="btn small">All comparisons</Link></div>
        <h1>What {pair.fork.split("/")[0]} changed in {pair.main.split("/")[1]}</h1>
        <p className="pair-repos">
          <a href={`https://github.com/${pair.fork}/tree/${pair.fork_branch}`} rel="noreferrer" target="_blank">{pair.fork}</a> compared with{" "}
          <a href={`https://github.com/${pair.main}/tree/${pair.branch}`} rel="noreferrer" target="_blank">{pair.main}</a> at the point they split
        </p>
        <p className="stats">
          <span className="stat add"><b>{pair.modules.length}</b> product {pair.modules.length === 1 ? "area" : "areas"} touched</span>
          <span className="stat add"><b>{fresh}</b> new</span>
          <span className="stat"><b>{pair.product.files}</b> files <Delta add={pair.product.additions} del={pair.product.deletions} /></span>
          <span className="stat"><b>{pair.ahead}</b> commits ahead</span>
          <span className="stat"><b>{pair.behind}</b> behind</span>
        </p>
        {pair.modules.length === 0 && <p>This fork has no product code changes.</p>}
        <div className="pair-board" ref={board}>
          <svg className="wires" width={size.w} height={size.h} aria-hidden="true">
            {lines.map((l) => <g key={l.id} className="wire-simple ext"><path d={l.d} /></g>)}
          </svg>
          {modules.map((m) => (
            <div className="pair-row" key={m.id}>
              <div className="pair-left">
                {m.is_new ? <p className="pair-new">Not in main</p> : <div className="pair-area" data-from={m.id}>{m.name}</div>}
              </div>
              <button className={`pair-card ${m.is_new ? "new" : ""} ${open === m.id ? "active" : ""}`} data-to={m.id} aria-pressed={open === m.id} onClick={() => setOpen(m.id)}>
                <span className="pair-card-top"><strong>{m.is_new ? `New: ${m.name}` : m.name}</strong><span>{plural(m.file_count, "file")} <Delta add={m.additions} del={m.deletions} /></span></span>
                {m.commits[0] && <span className="pair-commit">{m.commits[0].subject}</span>}
                {m.surfaces.length > 0 && <span className="chips">{m.surfaces.slice(0, 3).map((s) => <span className="chip" key={s.kind + s.name}><b>{s.kind}</b> {s.name}</span>)}{m.surfaces.length > 3 && <span className="chip">+{m.surfaces.length - 3} more</span>}</span>}
              </button>
            </div>
          ))}
        </div>
        {!all && pair.modules.length > FIRST_SHOWN && <button className="btn more" onClick={() => setAll(true)}>Show all {pair.modules.length} areas</button>}
        {ignored.length > 0 && <p className="ignored">Set aside as not product code: {ignored.map(([k, v]) => `${plural(v.files, "file")} of ${k}`).join(", ")}.</p>}
      </div>
      {open && <ModulePanel pair={pair} moduleId={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

export function PairList() {
  const [pairs, setPairs] = useState(null);
  useEffect(() => { get(`${results}/index.json`).then(setPairs).catch(() => setPairs([])); }, []);
  return (
    <div className="app-main">
      <Logo />
      <h1>Compared repos</h1>
      {pairs && pairs.length === 0 && <p className="muted">No comparisons yet.</p>}
      <ul className="pair-list">
        {(pairs || []).map((p) => (
          <li key={p.id}>
            <Link href={`/pairs/${p.id}`}>
              <span>{p.fork} <span className="muted">vs {p.main}</span></span>
              <span>{plural(p.product.files, "file")} <Delta add={p.product.additions} del={p.product.deletions} /></span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
