#!/usr/bin/env python3
"""Local worker: compares repo-fork pairs and writes results for the site. Only public GitHub repos.

  worker.py add owner/repo owner/fork [--branch B] [--fork-branch B] [--approve]
  worker.py list | approve <id> | reject <id>
  worker.py run [--once] [--interval 30]

Jobs wait for approval. Results go to web/public/pairs/<id>/. Failures are recorded on the job.
"""
import argparse, fcntl, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from compare import compare, git

JOBS = HERE / "jobs"
RESULTS = HERE.parent / "web/public/pairs"
REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}/[A-Za-z0-9._-]{1,100}$")
BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,200}$")
MAX_REPO_MB = 1024
MAX_FILES_KEPT = 1500  # after this a result is cut short and says so
ACTIVE = ("pending", "approved", "running")
STALE_AFTER = timedelta(minutes=45)  # longer than any git timeout adds up to in practice
GENERIC_ERROR = "We couldn't read those repos or branches. Check that both links are right and try again."


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def github(repo):
    """Public metadata, unauthenticated on purpose: if anonymous can't see it, we don't process it."""
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers={"Accept": "application/vnd.github+json", "User-Agent": "productology-worker"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"{repo} isn't a public GitHub repo")
        if e.code in (403, 429):
            raise ValueError("GitHub's limit for anonymous requests was reached. Try again in an hour.")
        raise RuntimeError(f"GitHub returned {e.code} for {repo}")


def validate(main, fork, branch=None, fork_branch=None):
    for r in (main, fork):
        if not REPO.match(r) or ".." in r:
            raise ValueError(f"not an owner/repo name: {r}")
    for b in (branch, fork_branch):
        if b and (not BRANCH.match(b) or ".." in b):
            raise ValueError(f"not a branch name: {b}")
    if main.lower() == fork.lower():
        raise ValueError("main and fork are the same repo")


def parse_link(text):
    """Accept a GitHub link or owner/repo, and return (owner/repo, branch or None)."""
    text = text.strip()
    m = re.fullmatch(r"(?:https?://(?:www\.)?github\.com/)?([^/\s]+/[^/\s?#]+?)(?:\.git)?/?(?:/tree/([^?#\s]+?))?/?(?:[?#]\S*)?", text)
    if not m:
        raise ValueError(f"That doesn't look like a GitHub repo link: {text[:80]}")
    repo, branch = m.group(1), m.group(2)
    if "." in repo.split("/")[0] or not REPO.match(repo):
        raise ValueError(f"That doesn't look like a GitHub repo link: {text[:80]}")
    return repo, branch


def job_id(main, fork):
    return re.sub(r"[^a-z0-9]+", "-", f"{main}-vs-{fork}".lower()).strip("-")[:120]


def load(path):
    return json.loads(path.read_text())


def save(job):
    JOBS.mkdir(exist_ok=True)
    tmp = JOBS / f".{job['id']}.{os.getpid()}.{time.monotonic_ns()}.tmp"
    tmp.write_text(json.dumps(job, indent=1))
    tmp.replace(JOBS / f"{job['id']}.json")


def add(main, fork, branch=None, fork_branch=None, approve=False):
    validate(main, fork, branch, fork_branch)
    existing = JOBS / f"{job_id(main, fork)}.json"
    if existing.exists() and load(existing)["state"] in ("approved", "running") and approve:
        return load(existing)  # already on its way
    job = {"id": job_id(main, fork), "main": main, "fork": fork, "branch": branch, "fork_branch": fork_branch,
           "state": "approved" if approve else "pending", "created": now(), "error": None}
    save(job)
    return job


def fetch(job, repo_dir):
    """Clone without blobs or a working tree; file contents are fetched only when a diff needs them."""
    main_info, fork_info = github(job["main"]), github(job["fork"])
    for info in (main_info, fork_info):
        if info.get("private"):
            raise ValueError(f"{info['full_name']} is private")
        if info.get("size", 0) > MAX_REPO_MB * 1024:
            raise ValueError(f"{info['full_name']} is over the {MAX_REPO_MB} MB limit")
    branch, fork_branch = job.get("branch") or main_info["default_branch"], job.get("fork_branch") or fork_info["default_branch"]
    url = "https://github.com/{}.git"
    git(repo_dir.parent, "clone", "--quiet", "--bare", "--filter=blob:none", "--no-tags", "--single-branch", "--branch", branch, "--", url.format(job["main"]), str(repo_dir), timeout=900)
    git(repo_dir, "remote", "add", "fork", url.format(job["fork"]))
    git(repo_dir, "config", "remote.fork.promisor", "true")
    git(repo_dir, "config", "remote.fork.partialclonefilter", "blob:none")
    git(repo_dir, "fetch", "--quiet", "--filter=blob:none", "--no-tags", "fork", f"+refs/heads/{fork_branch}:refs/fork/head", timeout=900)
    return f"refs/heads/{branch}", "refs/fork/head", branch, fork_branch, main_info, fork_info


def publish(job, result, meta):
    """Write the summary and one file per module, then swap them in so a reader never sees a half-written result."""
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(dir=RESULTS, prefix=".tmp-"))
    kept, modules = 0, []
    for m in result["modules"]:
        room = max(0, MAX_FILES_KEPT - kept)
        files, kept = m["files"][:room], kept + len(m["files"][:room])
        (out / f"{m['id']}.json").write_text(json.dumps({**m, "files": files, "cut_short": len(files) < len(m["files"])}))
        modules.append({k: v for k, v in m.items() if k != "files"} | {"file_count": len(m["files"])})
    summary = {**{k: v for k, v in result.items() if k != "modules"}, "id": job["id"], "main": job["main"], "fork": job["fork"], **meta, "generated": now(), "modules": modules}
    (out / "summary.json").write_text(json.dumps(summary))
    final = RESULTS / job["id"]
    if final.exists():
        shutil.rmtree(final)
    out.chmod(0o755)
    out.rename(final)
    index = sorted((load(p) for p in RESULTS.glob("*/summary.json") if not p.parent.name.startswith(".")), key=lambda s: s["generated"], reverse=True)
    (RESULTS / "index.json").write_text(json.dumps([{k: s[k] for k in ("id", "main", "fork", "ahead", "behind", "product", "generated")} for s in index]))
    return summary


def process(job):
    job.update(state="running", started=now(), error=None)
    save(job)
    with tempfile.TemporaryDirectory(prefix="productology-") as tmp:
        repo = Path(tmp) / "repo.git"
        try:
            base, head, branch, fork_branch, main_info, fork_info = fetch(job, repo)
            result = compare(repo, base, head)
            parent = (fork_info.get("parent") or {}).get("full_name", "")
            meta = {"branch": branch, "fork_branch": fork_branch, "is_github_fork": parent.lower() == job["main"].lower(),
                    "stars": fork_info.get("stargazers_count"), "fork_pushed": (fork_info.get("pushed_at") or "")[:10]}
            summary = publish(job, result, meta)
            job.update(state="done", finished=now(), product=summary["product"], ahead=summary["ahead"], behind=summary["behind"])
        except ValueError as e:  # written for the person who asked
            job.update(state="failed", finished=now(), error=str(e)[:300])
        except subprocess.TimeoutExpired:
            job.update(state="failed", finished=now(), error="These repos took too long to compare, so we stopped.")
        except Exception as e:  # a bad repo shouldn't stop the worker; keep the detail out of what people see
            job.update(state="failed", finished=now(), error=GENERIC_ERROR, detail=str(e)[:500])
    save(job)
    return job


def all_jobs():
    """Every readable job, oldest first. One damaged file shouldn't stop the others."""
    jobs = []
    for path in JOBS.glob("*.json") if JOBS.exists() else []:
        try:
            jobs.append(load(path))
        except (ValueError, OSError):
            print(f"skipping unreadable job {path.name}", file=sys.stderr, flush=True)
    return sorted(jobs, key=lambda j: j["created"])


def recover(jobs=None):
    """Nothing is running when a worker starts, so anything marked running was interrupted: queue it again."""
    for leftover in Path(tempfile.gettempdir()).glob("productology-*"):  # a hard kill leaves its temporary clone behind
        shutil.rmtree(leftover, ignore_errors=True)
    for job in jobs if jobs is not None else all_jobs():
        if job["state"] == "running":
            job.update(state="approved", error=None)
            save(job)


def expire_stuck():
    """Fail jobs that have been running far too long, so nobody is locked out by one that never ends."""
    for job in all_jobs():
        if job["state"] == "running" and datetime.now(timezone.utc) - datetime.fromisoformat(job["started"]) > STALE_AFTER:
            job.update(state="failed", finished=now(), error="This comparison took too long and was stopped. You can try again.")
            save(job)


def take_lock():
    """Allow one worker per machine. The lock ends with the process, even after a crash."""
    JOBS.mkdir(exist_ok=True)
    handle = open(JOBS / ".lock", "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another worker is already running")
    return handle


def run(once, interval):
    lock = take_lock()
    recover()
    while True:
        try:
            expire_stuck()
            for queued in [j for j in all_jobs() if j["state"] == "approved"]:
                job = load(JOBS / f"{queued['id']}.json")  # it may have been cancelled while others ran
                if job["state"] != "approved":
                    continue
                print(f"running {job['id']}", flush=True)
                done = process(job)
                print(f"  {done['state']}: {done.get('product') or done.get('error')}", flush=True)
        except Exception as e:  # keep the worker alive; the next pass tries again
            print(f"worker error: {e}", file=sys.stderr, flush=True)
        if once:
            lock.close()
            return
        time.sleep(interval)


def main():
    p = argparse.ArgumentParser(description="Compare repo-fork pairs for ProductOlogy.")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("add"); c.add_argument("main"); c.add_argument("fork"); c.add_argument("--branch"); c.add_argument("--fork-branch"); c.add_argument("--approve", action="store_true")
    sub.add_parser("list")
    c = sub.add_parser("approve"); c.add_argument("id")
    c = sub.add_parser("reject"); c.add_argument("id")
    c = sub.add_parser("run"); c.add_argument("--once", action="store_true"); c.add_argument("--interval", type=int, default=30)
    a = p.parse_args()
    if a.cmd == "add":
        print(json.dumps(add(a.main, a.fork, a.branch, a.fork_branch, a.approve)))
    elif a.cmd == "list":
        for f in sorted(JOBS.glob("*.json")) if JOBS.exists() else []:
            j = load(f); print(j["state"].ljust(9), j["id"], j.get("error") or "", j.get("detail") or "")
    elif a.cmd in ("approve", "reject"):
        if not re.fullmatch(r"[a-z0-9-]+", a.id) or not (JOBS / f"{a.id}.json").exists():
            sys.exit(f"no job {a.id}")
        j = load(JOBS / f"{a.id}.json"); j["state"] = "approved" if a.cmd == "approve" else "rejected"; save(j); print(j["state"], a.id)
    else:
        run(a.once, a.interval)


if __name__ == "__main__":
    main()
