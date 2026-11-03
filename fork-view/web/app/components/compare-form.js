"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

const LIVE = process.env.NEXT_PUBLIC_LIVE_API === "1";
const ACTIVE = ["pending", "approved", "running"];
const MESSAGES = {
  pending: "Waiting for approval. You can leave this page and come back; we'll keep your place.",
  approved: "In line. You can leave this page and come back; we'll keep your place.",
  running: "Comparing the repos. Larger ones can take a few minutes. You can leave this page and come back.",
};
const POLL_MS = 2000;

const send = (method, body) => fetch(method === "POST" ? "/api/pairs" : "/api/pairs/current", {
  method,
  headers: body ? { "Content-Type": "application/json" } : undefined,
  body: body ? JSON.stringify(body) : undefined,
  cache: "no-store",
});

export default function CompareForm() {
  const router = useRouter();
  const [main, setMain] = useState("");
  const [fork, setFork] = useState("");
  const [job, setJob] = useState(null);
  const [checking, setChecking] = useState(LIVE);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(false);
  const watched = useRef(false); // true once this page has seen the job in progress
  const active = job && ACTIVE.includes(job.state);

  const show = useCallback((next) => {
    setJob(next);
    if (next) { setMain(`https://github.com/${next.main}`); setFork(`https://github.com/${next.fork}`); }
    if (next?.state === "failed") setError(next.error || "This comparison didn't finish.");
  }, []);

  // Coming back: the cookie tells the server which request is ours.
  useEffect(() => {
    if (!LIVE) return;
    let stop = false;
    send("GET").then((r) => r.json()).then((body) => {
      if (stop) return;
      if (body.job && ACTIVE.includes(body.job.state)) watched.current = true;
      show(body.job);
    }).catch(() => { if (!stop) setError("Couldn't reach the server. Refresh to try again."); }).finally(() => { if (!stop) setChecking(false); });
    return () => { stop = true; };
  }, [show]);

  useEffect(() => {
    if (!active) return;
    let stop = false;
    let timer;
    const poll = async () => {
      try {
        const r = await send("GET");
        if (!r.ok) throw new Error();
        const { job: next } = await r.json();
        if (stop) return;
        setOffline(false);
        if (!next) { setJob(null); return; }
        if (next.state === "done" && watched.current) { router.push(`/pairs/${next.id}`); setJob(next); return; }
        show(next);
      } catch {
        if (!stop) setOffline(true); // a blip shouldn't lose their place, so keep trying
      }
      if (!stop) timer = setTimeout(poll, POLL_MS);
    };
    timer = setTimeout(poll, POLL_MS);
    return () => { stop = true; clearTimeout(timer); };
  }, [active, job?.id, router, show]);

  async function submit(e) {
    e.preventDefault();
    if (sending || active) return;
    setSending(true);
    setError(null);
    try {
      const r = await send("POST", { main, fork });
      const body = await r.json().catch(() => ({}));
      if (r.status === 409 && body.job) { watched.current = true; show(body.job); setError(body.detail); return; }
      if (!r.ok) { setError(typeof body.detail === "string" ? body.detail : "Check both links and try again."); return; }
      watched.current = true;
      show(body.job);
    } catch {
      setError("Couldn't reach the server. Try again in a moment.");
    } finally {
      setSending(false);
    }
  }

  async function forget() {
    setError(null);
    try {
      const r = await send("DELETE");
      if (!r.ok) throw new Error();
      watched.current = false;
      setJob(null);
    } catch {
      setError("Couldn't cancel just now. Try again in a moment.");
    }
  }

  const locked = !LIVE || checking || sending || active;
  return (
    <form className="compare-form" onSubmit={submit}>
      <h1>Compare your own repos</h1>
      {job?.state === "done" && !watched.current && (
        <div className="compare-banner">
          <p>Your comparison of <strong>{job.fork}</strong> is ready.</p>
          <Link className="btn small primary" href={`/pairs/${job.id}`}>View it</Link>
        </div>
      )}
      <div className="compare-fields">
        <label>Main repo<input value={main} onChange={(e) => setMain(e.target.value)} placeholder="https://github.com/owner/repo" required disabled={locked} autoComplete="off" spellCheck="false" inputMode="url" /></label>
        <label>Fork<input value={fork} onChange={(e) => setFork(e.target.value)} placeholder="https://github.com/client/repo" required disabled={locked} autoComplete="off" spellCheck="false" inputMode="url" /></label>
        <button className="btn primary" type="submit" disabled={locked}>{active || sending ? "Comparing…" : "Compare"}</button>
      </div>
      {!LIVE && <p className="compare-status">Comparing your own repos isn&apos;t available on this site yet.</p>}
      {LIVE && !active && !error && <p className="compare-status">{checking ? "Checking for your last request…" : <>Public GitHub repos only, one comparison at a time. Add <code>/tree/branch-name</code> to a link to pick a branch.</>}</p>}
      <div aria-live="polite">
        {active && (
          <div className="compare-actions">
            <p className="compare-status"><span className="spinner" aria-hidden="true" />{offline ? "Lost touch with the server. Still trying…" : MESSAGES[job.state]}</p>
            <button type="button" className="btn small" onClick={forget}>{job.state === "running" ? "Stop tracking" : "Cancel"}</button>
          </div>
        )}
        {error && <p className="compare-status error" role="alert">{error}</p>}
      </div>
    </form>
  );
}
