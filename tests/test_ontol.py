import json, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import ontol


class Demo(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = ontol.connect(Path(self.dir.name) / "t.db")
        ontol.ingest(self.db, ROOT / "demo/sessions")
        ontol.load_tickets(self.db, ROOT / "demo/tickets.json")

    def tearDown(self):
        self.db.close()
        self.dir.cleanup()

    def test_ticket_comes_from_branch(self):
        self.assertEqual(ontol.ticket_from_branch("sam/HAR-101-northwind-export"), "HAR-101")
        self.assertEqual(ontol.ticket_from_branch("feature/kan-7-x"), "KAN-7")
        self.assertIsNone(ontol.ticket_from_branch("main"))
        self.assertIsNone(ontol.ticket_from_branch(None))

    def test_search_finds_rejected_approach(self):
        hits = ontol.search(self.db, "cron idempotency")
        self.assertTrue(hits)
        self.assertEqual(hits[0][1], "HAR-101")

    def test_search_filters_by_client(self):
        self.assertFalse(ontol.search(self.db, "cron", client="Globex"))
        self.assertTrue(ontol.search(self.db, "cron", client="northwind"))

    def test_related_finds_earlier_client_work(self):
        self.assertEqual(ontol.related(self.db, "HAR-117")[0][0], "HAR-101")

    def test_ingest_twice_adds_nothing(self):
        self.assertEqual(ontol.ingest(self.db, ROOT / "demo/sessions")[1], 0)

    def test_unlinked_session_stays_unlinked(self):
        n = self.db.execute("select count(*) from msg where branch='main' and ticket is null").fetchone()[0]
        self.assertEqual(n, 2)

    def test_secrets_are_redacted(self):
        secret = "ghp_" + "a" * 30
        with tempfile.TemporaryDirectory() as d:
            rec = {"type": "user", "uuid": "x", "sessionId": "s", "timestamp": "t", "cwd": "/r", "gitBranch": "main",
                   "message": {"content": f"token {secret}"}}
            (Path(d) / "a.jsonl").write_text(json.dumps(rec) + "\n")
            ontol.ingest(self.db, d)
        self.assertEqual(self.db.execute("select count(*) from msg where text like ?", (f"%{secret}%",)).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
