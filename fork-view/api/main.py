"""Compare a client fork with main at product level.

What's added, changed or shared, the groups, and the links between features are computed by parsing each repo's routes. Plain-English labels and ticket context come
from data/labels.json and data/forks.json; in a real product they'd come from an LLM pass, Jira and recorded sessions.
"""
import ast, difflib, json, re, sys
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "worker"))
import worker

DATA = Path(__file__).resolve().parent.parent / "data"
MAIN = "harbor-main"
LABELS = json.loads((DATA / "labels.json").read_text())
FORKS = json.loads((DATA / "forks.json").read_text())
app = FastAPI(title="ProductOlogy")


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name) and parts:
        return ".".join([node.id, *reversed(parts)])


def routes(repo):
    """Map 'METHOD /path' to its file, handler source and the calls the handler makes."""
    found = {}
    for file in sorted((DATA / repo / "routes").glob("*.py")):
        text = file.read_text()
        for node in ast.parse(text).body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for deco in node.decorator_list:
                if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute) and deco.args:
                    key = f"{deco.func.attr.upper()} {deco.args[0].value}"
                    calls = {d for stmt in node.body for n in ast.walk(stmt) if isinstance(n, ast.Call) and (d := dotted(n.func))}
                    found[key] = (f"routes/{file.name}", "\n".join(text.splitlines()[deco.lineno - 1:node.end_lineno]), calls)
    return found


def group_of(key):
    """The product group is the route's first path segment, so it comes from the code, not a label."""
    return key.split(" ", 1)[1].strip("/").split("/")[0]


def link(key, ours, base):
    """Find which main capability a client capability builds on, from the code they share."""
    def score(other):
        shared = ours[key][2] & base[other][2]
        objects = {c.rsplit(".", 1)[0] for c in ours[key][2]} & {c.rsplit(".", 1)[0] for c in base[other][2]}
        return len(shared), len(objects), shared, objects

    def path_overlap(other):
        return len(set(key.split(" ")[1].split("/")) & set(other.split(" ")[1].split("/")) - {"", "{id}"})
    best = max(sorted(base), key=lambda k: (*score(k)[:2], path_overlap(k)), default=None)
    if best:
        exact, objs, shared, objects = score(best)
        if exact:
            return best, f"Both call {sorted(shared)[0]}"
        if objs:
            return best, f"Both use {sorted(objects)[0]}"
    return None, None


def compare(fork):
    """Return {key: status} for everything in main or the fork."""
    base, ours = routes(MAIN), routes(FORKS[fork]["dir"])
    status = {}
    for key in base.keys() | ours.keys():
        if key not in base:
            status[key] = "added"
        elif key not in ours:
            status[key] = "removed"
        else:
            status[key] = "same" if base[key][1] == ours[key][1] else "changed"
    return status


def siblings(fork, key):
    """Other clients with their own version of the same capability."""
    family = LABELS.get(key, {}).get("family")
    if not family:
        return []
    out = []
    for other, info in FORKS.items():
        if other == fork:
            continue
        for k in routes(info["dir"]):
            if LABELS.get(k, {}).get("family") == family and compare(other)[k] == "added":
                out.append({"fork": other, "client": info["name"], "key": k, "name": LABELS[k]["name"], "ticket": info["work"].get(k, {}).get("ticket")})
    return out


def all_files(repo):
    root = DATA / repo
    return {str(p.relative_to(root)): p.read_text() for p in root.rglob("*") if p.is_file()}


def changed_files(fork):
    """Every file that differs from main, with its status, line counts and diff. This is a real comparison."""
    base, ours = all_files(MAIN), all_files(FORKS[fork]["dir"])
    out = {}
    for path in sorted(base.keys() | ours.keys()):
        old, new = base.get(path), ours.get(path)
        if old == new:
            continue
        diff = list(difflib.unified_diff((old or "").splitlines(), (new or "").splitlines(), lineterm="", n=3))[2:]
        out[path] = {"path": path, "status": "added" if old is None else "removed" if new is None else "modified",
                     "additions": sum(l.startswith("+") for l in diff), "deletions": sum(l.startswith("-") for l in diff), "diff": diff}
    return out


def files_of(fork, key):
    """The extension's route file (from the code) plus the files mapped to its ticket (hand-written in this demo)."""
    route = routes(FORKS[fork]["dir"]).get(key)
    paths = FORKS[fork]["work"].get(key, {}).get("files", [])
    changed = changed_files(fork)
    return [changed[p] for p in dict.fromkeys([route[0], *paths] if route else paths) if p in changed]


def unattributed(fork):
    """Files that differ from main but aren't tied to any extension. Nothing should fall through silently."""
    claimed = {f["path"] for key in FORKS[fork]["work"] for f in files_of(fork, key)}
    return sorted(set(changed_files(fork)) - claimed)


def describe(fork, key, status):
    label = LABELS.get(key, {})
    return {"key": key, "name": label.get("name", key), "status": status, "group": group_of(key), "summary": label.get("summary"),
            "changed": FORKS[fork]["work"].get(key, {}).get("changed"), "also": [s["client"] for s in siblings(fork, key)],
            **{k: FORKS[fork]["work"].get(key, {}).get(k) for k in ("reason", "owner", "ticket")}}


def connect(fork, status):
    """Give each client capability the node it grows from: the main one it changes, or the one it shares code with."""
    base, ours = routes(MAIN), routes(FORKS[fork]["dir"])
    edges = {}
    for key, s in status.items():
        if s == "changed":
            edges[key] = {"from": key, "via": "Same route, different code", "kind": "changed"}
        elif s == "added":
            source, via = link(key, ours, base)
            if source:
                edges[key] = {"from": source, "via": via, "kind": "added"}
    for key in sorted(k for k, s in status.items() if s == "added" and k not in edges):
        peers = [k for k in sorted(edges) if status[k] == "added" and group_of(k) == group_of(key)]
        edges[key] = {"from": peers[0], "via": f"Same /{group_of(key)} routes", "kind": "chained"} if peers else None
    return edges


@app.get("/api/forks")
def forks():
    return [{"id": k, "name": v["name"]} for k, v in FORKS.items()]


def need(fork):
    if fork not in FORKS:
        raise HTTPException(404, "unknown fork")


@app.get("/api/compare/{fork}")
def compare_view(fork: str):
    need(fork)
    status = compare(fork)
    edges = connect(fork, status)
    groups = {}
    for key, s in sorted(status.items(), key=lambda kv: LABELS.get(kv[0], {}).get("name", kv[0])):
        if s != "added":
            groups.setdefault(group_of(key), []).append(describe(fork, key, s))
    main = [{"id": g, "items": groups[g]} for g in sorted(groups)]
    client = []
    for k, s in status.items():
        if s in ("added", "changed"):
            fs = files_of(fork, k)
            client.append({**describe(fork, k, s), "edge": edges.get(k),
                           "files": {"count": len(fs), "additions": sum(f["additions"] for f in fs), "deletions": sum(f["deletions"] for f in fs)}})
    client.sort(key=lambda c: (LABELS.get(c["key"], {}).get("name", "")))
    counts = {s: sum(v == s for v in status.values()) for s in ("added", "changed", "same", "removed")}
    return {"id": fork, "name": FORKS[fork]["name"], "counts": counts, "main": main, "client": client, "unattributed": unattributed(fork)}


@app.get("/api/capability/{fork}")
def capability(fork: str, key: str):
    need(fork)
    status = compare(fork).get(key)
    if status is None:
        raise HTTPException(404, "unknown capability")
    also = siblings(fork, key)
    if status == "added" and also:
        advice = {"kind": "merge", "text": f"Built twice. {also[0]['client']} has its own version, so this is a candidate for main."}
    elif status == "changed":
        advice = {"kind": "review", "text": "This changes something every client shares, so check it before merging it back."}
    elif status == "added":
        advice = {"kind": "keep", "text": "Only this client has it so far. Keep it in the fork until a second client asks."}
    else:
        advice = None
    return {**describe(fork, key, status), "work": FORKS[fork]["work"].get(key), "siblings": also, "edge": connect(fork, compare(fork)).get(key), "files": files_of(fork, key), "advice": advice}


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def local_only(request: Request):
    """Comparison requests run without approval, so only this machine's own pages may send them."""
    origin = request.headers.get("origin")
    if origin and urlparse(origin).hostname not in LOCAL_HOSTS:
        raise HTTPException(403, "Requests are only accepted from this machine.")
    if (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]") not in LOCAL_HOSTS:
        raise HTTPException(403, "Requests are only accepted from this machine.")


class PairRequest(BaseModel):
    main: str
    fork: str


COOKIE = "productology_request"
COOKIE_DAYS = 30
MAX_QUEUED = 20
ID = re.compile(r"[a-z0-9-]{1,120}")
RESULT_FILE = re.compile(r"[a-z0-9-]{1,120}\.json")


def public_job(job):
    """What the browser may see. Internal error detail stays on the machine."""
    return {k: job.get(k) for k in ("id", "main", "fork", "state", "error")}


def own_job(request: Request):
    """The request this browser made, if its cookie still points at a real job."""
    job_id = request.cookies.get(COOKIE, "")
    path = worker.JOBS / f"{job_id}.json"
    if not ID.fullmatch(job_id) or not path.exists():
        return None
    try:
        return worker.load(path)
    except (ValueError, OSError):
        return None


@app.post("/api/pairs")
def request_pair(body: PairRequest, request: Request):
    local_only(request)
    mine = own_job(request)
    if mine and mine["state"] in worker.ACTIVE:
        return JSONResponse({"detail": "You already have a comparison in progress.", "job": public_job(mine)}, status_code=409)
    try:
        main_repo, branch = worker.parse_link(body.main)
        fork_repo, fork_branch = worker.parse_link(body.fork)
        worker.validate(main_repo, fork_repo, branch, fork_branch)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if sum(j["state"] in worker.ACTIVE for j in worker.all_jobs()) >= MAX_QUEUED:
        raise HTTPException(503, "We're handling a lot of comparisons right now. Try again soon.")
    job = worker.add(main_repo, fork_repo, branch, fork_branch, approve=True)
    response = JSONResponse({"job": public_job(job)})
    response.set_cookie(COOKIE, job["id"], max_age=COOKIE_DAYS * 86400, httponly=True, samesite="lax", path="/",
                        secure=request.headers.get("x-forwarded-proto") == "https")
    return response


@app.get("/api/pairs/current")
def current_pair(request: Request):
    mine = own_job(request)
    return {"job": public_job(mine) if mine else None}


@app.delete("/api/pairs/current")
def forget_pair(request: Request):
    """Cancel a request that hasn't started and stop tracking it. A running comparison finishes on its own."""
    local_only(request)
    mine = own_job(request)
    if mine and mine["state"] in ("pending", "approved"):
        mine.update(state="cancelled")
        worker.save(mine)
    response = JSONResponse({"job": None})
    response.delete_cookie(COOKIE, path="/")
    return response


@app.get("/api/results/{job_id}/{name}")
@app.get("/api/results/{name}")
def result_file(name: str, job_id: str | None = None):
    """Serve results straight from disk, because a production site can't see files added after it starts."""
    if not RESULT_FILE.fullmatch(name) or (job_id is not None and not ID.fullmatch(job_id)):
        raise HTTPException(404, "not found")
    path = worker.RESULTS / job_id / name if job_id else worker.RESULTS / name
    if not path.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="application/json")
