const LIVE = process.env.NEXT_PUBLIC_LIVE_API === "1";
const get = (url) => fetch(url).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
const saved = {};
const snapshot = (fork) => (saved[fork] ??= get(`/demo-data/${fork}.json`));

export const getForks = () => get(LIVE ? "/api/forks" : "/demo-data/index.json");
export const getView = (fork) => (LIVE ? get(`/api/compare/${fork}`) : snapshot(fork).then((s) => s.view));
export const getDetail = (fork, key) => (LIVE ? get(`/api/capability/${fork}?key=${encodeURIComponent(key)}`) : snapshot(fork).then((s) => s.capabilities[key]));
