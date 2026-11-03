import os, subprocess, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "worker"))
import compare as cmp
import worker


def g(d, *a):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "secret@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "secret@example.com"}
    return subprocess.run(["git", *a], cwd=d, env=env, check=True, capture_output=True, text=True).stdout


def write(d, path, text):
    p = d / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "r"; d.mkdir()
    g(d, "init", "-q", "-b", "main")
    write(d, "src/app/billing/page.tsx", "export default 1\n")
    write(d, "src/lib/billing/charge.ts", "a\nb\n")
    g(d, "add", "."); g(d, "commit", "-qm", "base")
    g(d, "checkout", "-qb", "fork")
    write(d, "src/lib/billing/charge.ts", "a\nb\nc\n")
    write(d, "src/app/portal/page.tsx", "export default 2\n")
    write(d, "src/app/api/portal/route.ts", "export function GET() {}\n")
    write(d, "prisma/schema.prisma", "model Portal {\n  id Int\n}\n")
    write(d, "package-lock.json", "{}\n")
    write(d, "src/lib/billing/charge.test.ts", "t\n")
    write(d, "public/locales/de.json", "{}\n")
    g(d, "add", "."); g(d, "commit", "-qm", "ACME-12 add portal (#7)")
    g(d, "checkout", "-q", "main")
    write(d, "src/lib/upstream_only.ts", "upstream\n")
    g(d, "add", "."); g(d, "commit", "-qm", "upstream moves on")
    return d


def test_upstream_only_work_is_not_counted(repo):
    r = cmp.compare(repo, "main", "fork")
    paths = {f["path"] for m in r["modules"] for f in m["files"]}
    assert "src/lib/upstream_only.ts" not in paths
    assert (r["ahead"], r["behind"]) == (1, 1)


def test_noise_is_separated_from_product(repo):
    r = cmp.compare(repo, "main", "fork")
    paths = {f["path"] for m in r["modules"] for f in m["files"]}
    assert "package-lock.json" not in paths and "src/lib/billing/charge.test.ts" not in paths
    assert set(r["ignored"]) == {"generated", "tests", "translations"}


def test_new_vs_existing_modules(repo):
    mods = {m["name"]: m for m in cmp.compare(repo, "main", "fork")["modules"]}
    assert mods["billing"]["is_new"] is False
    assert mods["portal"]["is_new"] is True


def test_surfaces_and_commit_refs(repo):
    mods = {m["name"]: m for m in cmp.compare(repo, "main", "fork")["modules"]}
    kinds = {(s["kind"], s["name"]) for s in mods["portal"]["surfaces"]}
    assert ("Page", "/portal") in kinds and ("API", "/api/portal") in kinds
    assert mods["portal"]["commits"][0]["refs"] == ["#7", "ACME-12"]


def test_author_email_is_not_in_the_result(repo):
    assert "secret@example.com" not in str(cmp.compare(repo, "main", "fork"))


def test_diff_shape_matches_the_ui(repo):
    mods = {m["name"]: m for m in cmp.compare(repo, "main", "fork")["modules"]}
    f = mods["billing"]["files"][0]
    assert f["status"] == "modified" and f["additions"] == 1 and f["diff"][0].startswith("@@")


@pytest.mark.parametrize("main,fork,branch", [("a/b;rm -rf", "c/d", None), ("../x", "c/d", None), ("a/b", "a/b", None), ("a/b", "c/d", "--upload-pack=x"), ("a/b", "c/d", "x..y")])
def test_bad_input_is_rejected(main, fork, branch):
    with pytest.raises(ValueError):
        worker.validate(main, fork, branch)


def test_failed_job_is_recorded_and_worker_continues(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    monkeypatch.setattr(worker, "fetch", lambda *a: (_ for _ in ()).throw(ValueError("x/y isn't a public GitHub repo")))
    job = worker.add("a/b", "c/d", approve=True)
    assert worker.process(job)["state"] == "failed" and "public" in job["error"]


def test_jobs_wait_for_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    monkeypatch.setattr(worker, "process", lambda j: pytest.fail("ran without approval"))
    worker.add("a/b", "c/d")
    worker.run(once=True, interval=0)


@pytest.mark.parametrize("path,name", [
    ("prisma/migrations/20260302200554_add_x/migration.sql", "database"),
    ("db/clickhouse/schema.sql", "database"),
    ("src/app/(main)/links/LinkForm.tsx", "links"),
    ("apps/remix/app/routes/_authenticated+/settings/a.tsx", "authenticated"),
    ("packages/ui/primitives/button.tsx", "primitives"),
    ("src/app/api/websites/[websiteId]/route.ts", "websites"),
])
def test_module_names(path, name):
    assert cmp.module_of(path) == name


@pytest.mark.parametrize("text,want", [
    ("https://github.com/umami-software/umami", ("umami-software/umami", None)),
    ("https://github.com/umami-software/umami/", ("umami-software/umami", None)),
    ("https://github.com/umami-software/umami.git", ("umami-software/umami", None)),
    ("github.com/a/b".replace("github.com/", "https://www.github.com/"), ("a/b", None)),
    ("a/b", ("a/b", None)),
    (" https://github.com/a/b/tree/feature/x ", ("a/b", "feature/x")),
    ("https://github.com/a/b?tab=readme", ("a/b", None)),
])
def test_links_are_understood(text, want):
    assert worker.parse_link(text) == want


@pytest.mark.parametrize("text", ["https://gitlab.com/a/b", "http://evil.test/a/b", "not a link", "", "https://github.com/a", "https://github.com/a/b/pull/1", "git@github.com:a/b.git"])
def test_other_links_are_refused(text):
    with pytest.raises(ValueError):
        worker.parse_link(text)


def test_unrelated_repos_get_a_clear_error(tmp_path):
    d = tmp_path / "r"; d.mkdir()
    g(d, "init", "-q", "-b", "main"); write(d, "a", "1\n"); g(d, "add", "."); g(d, "commit", "-qm", "a")
    g(d, "checkout", "-q", "--orphan", "other"); write(d, "b", "2\n"); g(d, "add", "."); g(d, "commit", "-qm", "b")
    with pytest.raises(ValueError, match="share no history"):
        cmp.compare(d, "main", "other")


def test_interrupted_job_is_queued_again(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    job = worker.add("a/b", "c/d", approve=True); job["state"] = "running"; job["started"] = worker.now(); worker.save(job)
    worker.recover()
    assert worker.load(tmp_path / f"{job['id']}.json")["state"] == "approved"


def test_stuck_job_fails_so_nobody_is_locked_out(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    job = worker.add("a/b", "c/d", approve=True); job.update(state="running", started="2020-01-01T00:00:00+00:00"); worker.save(job)
    worker.expire_stuck()
    done = worker.load(tmp_path / f"{job['id']}.json")
    assert done["state"] == "failed" and done["error"]


def test_recent_running_job_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    job = worker.add("a/b", "c/d", approve=True); job.update(state="running", started=worker.now()); worker.save(job)
    worker.expire_stuck()
    assert worker.load(tmp_path / f"{job['id']}.json")["state"] == "running"


def test_damaged_job_file_doesnt_stop_the_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    (tmp_path / "broken.json").write_text("{nope")
    ran = []
    monkeypatch.setattr(worker, "process", lambda j: ran.append(j["id"]) or {**j, "state": "done"})
    job = worker.add("a/b", "c/d", approve=True)
    worker.run(once=True, interval=0)
    assert ran == [job["id"]]


def test_cancelled_job_isnt_run(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    monkeypatch.setattr(worker, "process", lambda j: pytest.fail("ran a cancelled job"))
    job = worker.add("a/b", "c/d", approve=True); job["state"] = "cancelled"; worker.save(job)
    worker.run(once=True, interval=0)


def test_only_one_worker_at_a_time(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    held = worker.take_lock()
    code = "import fcntl,sys; h=open(sys.argv[1],'w')\ntry:\n  fcntl.flock(h, fcntl.LOCK_EX|fcntl.LOCK_NB); print('got')\nexcept OSError: print('blocked')"
    assert subprocess.run([sys.executable, "-c", code, str(tmp_path / ".lock")], capture_output=True, text=True).stdout.strip() == "blocked"
    held.close()


def test_git_errors_dont_reach_the_person(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    def boom(*a): raise RuntimeError("git clone failed: fatal /private/tmp/secret")
    monkeypatch.setattr(worker, "fetch", boom)
    done = worker.process(worker.add("a/b", "c/d", approve=True))
    assert done["state"] == "failed" and "secret" not in done["error"] and "secret" in done["detail"]


def test_timeout_has_a_clear_message(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    def slow(*a): raise subprocess.TimeoutExpired("git", 1)
    monkeypatch.setattr(worker, "fetch", slow)
    assert "too long" in worker.process(worker.add("a/b", "c/d", approve=True))["error"]


def test_restart_removes_clones_left_by_a_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "JOBS", tmp_path)
    monkeypatch.setattr(worker.tempfile, "gettempdir", lambda: str(tmp_path))
    (tmp_path / "productology-abc" / "repo.git").mkdir(parents=True)
    worker.recover()
    assert not (tmp_path / "productology-abc").exists()
