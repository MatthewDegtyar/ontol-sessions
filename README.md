# ontol-sessions

**What did we build for this client, and why?** Your code shows what shipped and your ticket shows what was asked for.
The reasoning in between lives in AI coding sessions that nobody can find. This links them in one local SQLite db.

```console
$ python3 ontol.py related HAR-117        # new ticket: nightly export for Globex
HAR-101  Northwind  Done  6 matching messages
  Nightly shipment export to SFTP for Northwind

$ python3 ontol.py search "cron restart" --client northwind
[4] HAR-101 (Northwind) assistant: The cron job retries from scratch after a restart, so it can't tell
the upload already happened. I'm dropping the cron approach and moving the export to the job queue…
```

Early demo: no dependencies, local only, Claude Code only. Using an agent? Point it at [AGENTS.md](AGENTS.md).

```bash
export ONTOL_DB=/tmp/ontol-demo.db
python3 ontol.py ingest --source demo/sessions
python3 ontol.py tickets demo/tickets.json
python3 ontol.py related HAR-117
```

The demo data is made up. Your sessions are only read if you run `ingest` without `--source`, and nothing leaves your machine.

## How sessions link to tickets

Claude Code records the git branch on each message. A branch containing a ticket key, like `sam/HAR-101-export`, links
that message to the ticket. Nothing is guessed, and anything else shows up under `unlinked`.

## What we've measured

One small test on our own project: an agent answered 16 questions about past work, with and without the session db.

| Questions | Files and notes only | With session db |
|---|---|---|
| History (8) | 0 correct, 2 partial, 6 couldn't answer | 7 correct, 1 wrong |
| Past pitfalls (4) | 2 correct, 2 partial | 3 correct, 1 partial |
| Current state (4) | 4 correct | 4 correct |

We wrote the questions from the same transcripts, so the history result favours the db by design. It's one person's project
with one run per question, and it doesn't show that the resulting work gets better.

## Limits

Redaction is pattern matching and can miss things, so don't share the db. `related` is keyword matching. There's no team sync,
Jira connector or drift checking yet.

Landing page source is in `site/`. MIT licensed.
