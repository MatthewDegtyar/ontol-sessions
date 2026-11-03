import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)


import pytest


def test_status_is_computed_from_code():
    s = main.compare("northwind")
    assert s["POST /exports/sftp/schedule"] == "added"
    assert s["GET /audit"] == "changed"
    assert s["GET /shipments"] == "same"


def test_counts():
    assert c.get("/api/compare/northwind").json()["counts"] == {"added": 2, "changed": 1, "same": 7, "removed": 0}
    assert c.get("/api/compare/globex").json()["counts"] == {"added": 3, "changed": 1, "same": 7, "removed": 0}


def test_built_twice_is_flagged():
    d = c.get("/api/capability/northwind", params={"key": "POST /exports/sftp/schedule"}).json()
    assert d["advice"]["kind"] == "merge" and d["siblings"][0]["client"] == "Globex"


def test_extension_lists_its_files_with_real_diffs():
    d = c.get("/api/capability/globex", params={"key": "POST /invoices/{id}/send"}).json()
    by = {f["path"]: f for f in d["files"]}
    assert set(by) == {"routes/invoices.py", "web/invoices/SendDialog.tsx", "migrations/022_invoice_po_number.sql"}
    assert by["routes/invoices.py"]["status"] == "modified" and any("require_po" in l for l in by["routes/invoices.py"]["diff"])
    assert by["migrations/022_invoice_po_number.sql"]["status"] == "added"
    assert by["web/invoices/SendDialog.tsx"]["additions"] > 0 and by["web/invoices/SendDialog.tsx"]["deletions"] > 0


def test_every_changed_file_belongs_to_an_extension():
    for fork in ("northwind", "globex"):
        assert main.unattributed(fork) == []


def test_unknown_404():
    assert c.get("/api/compare/nope").status_code == 404


def test_groups_come_from_paths():
    assert [g["id"] for g in c.get("/api/compare/globex").json()["main"]] == ["audit", "exports", "invoices", "shipments", "users"]


def edge(fork, key):
    return next(x for x in c.get(f"/api/compare/{fork}").json()["client"] if x["key"] == key)["edge"]


def test_edges_come_from_shared_code():
    assert edge("northwind", "POST /exports/sftp/schedule") == {"from": "GET /exports/csv", "via": "Both call db.shipments.on", "kind": "added"}
    assert edge("globex", "GET /portal/shipments")["via"] == "Both use db.shipments"
    assert edge("northwind", "GET /audit")["kind"] == "changed"


def test_feature_with_no_shared_code_chains_to_its_group():
    e = edge("globex", "POST /portal/shipments/{id}/issue")
    assert e["kind"] == "chained" and e["from"] == "GET /portal/shipments"


def test_ties_prefer_the_same_part_of_the_product():
    assert edge("northwind", "POST /shipments/{id}/customs-hold")["from"] == "GET /shipments"
    assert edge("globex", "GET /portal/shipments")["from"] == "GET /shipments"


def test_website_snapshot_is_current():
    import json
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
    import export
    for name, data in export.snapshot().items():
        assert json.loads((export.OUT / name).read_text()) == json.loads(json.dumps(data)), f"run api/export.py: {name} is stale"


def pair_client(tmp_path, monkeypatch):
    monkeypatch.setattr(main.worker, "JOBS", tmp_path)
    return TestClient(main.app, base_url="http://localhost:3610")


def ask(p, main_repo="https://github.com/a/b", fork="https://github.com/c/b/tree/dev"):
    return p.post("/api/pairs", json={"main": main_repo, "fork": fork})


def set_state(tmp_path, job_id, state, **extra):
    job = main.worker.load(tmp_path / f"{job_id}.json")
    job.update(state=state, **extra)
    main.worker.save(job)


def test_requesting_a_pair_queues_it_and_sets_a_cookie(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    r = ask(p)
    assert r.status_code == 200 and r.json()["job"]["state"] == "approved"
    job = main.worker.load(tmp_path / f"{r.json()['job']['id']}.json")
    assert (job["main"], job["fork"], job["fork_branch"]) == ("a/b", "c/b", "dev")
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "max-age" in cookie


def test_coming_back_finds_the_request(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    assert p.get("/api/pairs/current").json()["job"] is None
    job_id = ask(p).json()["job"]["id"]
    assert p.get("/api/pairs/current").json()["job"]["id"] == job_id
    set_state(tmp_path, job_id, "done")
    assert p.get("/api/pairs/current").json()["job"]["state"] == "done"


def test_only_one_request_at_a_time(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    first = ask(p).json()["job"]["id"]
    for state in ("approved", "running", "pending"):
        set_state(tmp_path, first, state)
        r = ask(p, "e/f", "g/f")
        assert r.status_code == 409 and r.json()["job"]["id"] == first
    assert len(list(tmp_path.glob("*.json"))) == 1


@pytest.mark.parametrize("state", ["done", "failed", "cancelled", "rejected"])
def test_a_finished_request_frees_you_up(tmp_path, monkeypatch, state):
    p = pair_client(tmp_path, monkeypatch)
    set_state(tmp_path, ask(p).json()["job"]["id"], state)
    assert ask(p, "e/f", "g/f").status_code == 200


def test_invalid_request_doesnt_replace_your_tracked_one(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    job_id = ask(p).json()["job"]["id"]
    set_state(tmp_path, job_id, "done")
    assert ask(p, "https://gitlab.com/x/y", "c/d").status_code == 422
    assert p.get("/api/pairs/current").json()["job"]["id"] == job_id


def test_cancel_before_it_starts(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    job_id = ask(p).json()["job"]["id"]
    assert p.delete("/api/pairs/current").status_code == 200
    assert main.worker.load(tmp_path / f"{job_id}.json")["state"] == "cancelled"
    assert p.get("/api/pairs/current").json()["job"] is None
    assert ask(p, "e/f", "g/f").status_code == 200


def test_forgetting_a_running_job_leaves_it_running(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    job_id = ask(p).json()["job"]["id"]
    set_state(tmp_path, job_id, "running")
    p.delete("/api/pairs/current")
    assert main.worker.load(tmp_path / f"{job_id}.json")["state"] == "running"


@pytest.mark.parametrize("bad", ["../../secret", "a/b", "nope", "x" * 300, ""])
def test_bad_or_stale_cookie_is_ignored(tmp_path, monkeypatch, bad):
    p = pair_client(tmp_path, monkeypatch)
    p.cookies.set(main.COOKIE, bad)
    assert p.get("/api/pairs/current").json()["job"] is None
    assert ask(p).status_code == 200


def test_damaged_job_file_doesnt_break_the_page(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    job_id = ask(p).json()["job"]["id"]
    (tmp_path / f"{job_id}.json").write_text("{not json")
    assert p.get("/api/pairs/current").json()["job"] is None


def test_internal_error_detail_isnt_exposed(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    set_state(tmp_path, ask(p).json()["job"]["id"], "failed", error="friendly", detail="/private/path secret")
    assert "secret" not in p.get("/api/pairs/current").text


def test_queue_has_a_ceiling(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "MAX_QUEUED", 1)
    main.worker.add("x/y", "z/y", approve=True)
    assert ask(p).status_code == 503


def test_results_are_served_and_paths_are_contained(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    monkeypatch.setattr(main.worker, "RESULTS", tmp_path)
    (tmp_path / "abc").mkdir(); (tmp_path / "abc/summary.json").write_text('{"ok": 1}'); (tmp_path / "index.json").write_text("[]")
    assert p.get("/api/results/abc/summary.json").json() == {"ok": 1}
    assert p.get("/api/results/index.json").json() == []
    for path in ("/api/results/abc/nope.json", "/api/results/abc/..%2f..%2fsecret.json", "/api/results/ABC/summary.json", "/api/results/abc/summary.txt"):
        assert p.get(path).status_code == 404


def test_bad_link_is_a_clear_error(tmp_path, monkeypatch):
    r = pair_client(tmp_path, monkeypatch).post("/api/pairs", json={"main": "https://gitlab.com/a/b", "fork": "c/d"})
    assert r.status_code == 422 and "GitHub" in r.json()["detail"]


def test_other_sites_cant_start_jobs(tmp_path, monkeypatch):
    p = pair_client(tmp_path, monkeypatch)
    assert p.post("/api/pairs", json={"main": "a/b", "fork": "c/d"}, headers={"origin": "https://evil.test"}).status_code == 403
    assert p.post("/api/pairs", json={"main": "a/b", "fork": "c/d"}, headers={"host": "evil.test"}).status_code == 403
    assert list(tmp_path.iterdir()) == []
