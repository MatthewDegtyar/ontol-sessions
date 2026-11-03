#!/usr/bin/env python3
"""Link Claude Code sessions to tickets in one local SQLite db, so people and agents can ask why something was built.

No dependencies. Run `python3 ontol.py --help`. See AGENTS.md.
"""
import argparse, glob, json, os, re, sqlite3, sys
from pathlib import Path

DEFAULT_DB = os.environ.get("ONTOL_DB", str(Path.home() / ".ontol/sessions.db"))
DEFAULT_SOURCE = str(Path.home() / ".claude/projects")
TICKET = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
MAX_TOOL_TEXT = 1500  # most of a transcript is tool output; keep the start of it
STOP = {"a", "an", "and", "the", "to", "for", "of", "in", "on", "with", "by", "per", "from", "at", "add"}
SECRETS = [r"ATATT[\w\-=]{20,}", r"sk-[A-Za-z0-9_\-]{20,}", r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_\w{20,}",
           r"xox[abprs]-[\w\-]{10,}", r"AKIA[0-9A-Z]{16}", r"(?i)bearer\s+[\w\-.=]{20,}", r"(?i)basic\s+[A-Za-z0-9+/=]{20,}",
           r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"]
SCHEMA = """
create table if not exists msg(id integer primary key, uuid text unique, session text, ts text, repo text, branch text,
                               ticket text, kind text, text text);
create index if not exists msg_ticket on msg(ticket);
create virtual table if not exists fts using fts5(text, content='msg', content_rowid='id');
create table if not exists ticket(key text primary key, title text, client text, owner text, status text,
                                  description text, pr text);
"""


def connect(path):
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(Path(path).expanduser())
    db.executescript(SCHEMA)
    return db


def redact(text):
    for pattern in SECRETS:
        text = re.sub(pattern, "[REDACTED]", text)
    return text


def ticket_from_branch(branch):
    match = TICKET.search((branch or "").upper())
    return match.group(1) if match else None


def blocks(record):
    """Yield (kind, text) for one transcript record, keeping the conversation and trimming tool output."""
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        yield record["type"], content
        return
    for block in content or []:
        kind = block.get("type")
        if kind == "text":
            yield record["type"], block["text"]
        elif kind == "tool_use":
            yield "tool_call", f"{block.get('name')}: {json.dumps(block.get('input'))[:MAX_TOOL_TEXT]}"
        elif kind == "tool_result":
            body = block.get("content")
            if isinstance(body, list):
                body = "\n".join(part.get("text", "") for part in body if isinstance(part, dict))
            yield "tool_result", str(body)[:MAX_TOOL_TEXT]


def ingest(db, source):
    files = sorted(glob.glob(str(Path(source).expanduser() / "**/*.jsonl"), recursive=True))
    added = 0
    for file in files:
        for line in open(file, errors="ignore"):
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("type") not in ("user", "assistant") or record.get("isSidechain"):
                continue
            branch = record.get("gitBranch")
            for n, (kind, text) in enumerate(blocks(record)):
                if not text or not text.strip():
                    continue
                cur = db.execute(
                    "insert or ignore into msg(uuid,session,ts,repo,branch,ticket,kind,text) values(?,?,?,?,?,?,?,?)",
                    (f"{record.get('uuid')}:{n}", record.get("sessionId", "")[:8], record.get("timestamp", ""),
                     Path(record.get("cwd") or "").name, branch, ticket_from_branch(branch), kind, redact(text)))
                added += cur.rowcount
    db.execute("insert into fts(fts) values('rebuild')")
    db.commit()
    return len(files), added


def load_tickets(db, path):
    rows = json.load(open(path))
    for t in rows:
        db.execute("insert or replace into ticket values(?,?,?,?,?,?,?)",
                   (t["key"], t.get("title"), t.get("client"), t.get("owner"), t.get("status"), t.get("description"), t.get("pr")))
    db.commit()
    return len(rows)


def fts_query(words):
    terms = [w for w in re.findall(r"[\w\-.]+", words) if w.lower() not in STOP]
    return " OR ".join(f'"{w}"' for w in terms)


def search(db, words, ticket=None, client=None, limit=10):
    sql = """select m.id, m.ticket, t.client, m.kind, snippet(fts,0,'','','…',40) from fts join msg m on m.id=fts.rowid
             left join ticket t on t.key=m.ticket where fts match ? and m.kind in ('user','assistant')"""
    args = [fts_query(words)]
    if ticket:
        sql += " and m.ticket=?"
        args.append(ticket)
    if client:
        sql += " and lower(t.client)=lower(?)"
        args.append(client)
    return db.execute(sql + " order by rank limit ?", (*args, limit)).fetchall()


def related(db, key, limit=5):
    """Earlier tickets whose sessions share words with this ticket, best match first."""
    row = db.execute("select title, description from ticket where key=?", (key,)).fetchone()
    if not row:
        return []
    return db.execute(
        """select m.ticket, t.title, t.client, t.status, count(*) hits from fts join msg m on m.id=fts.rowid
           join ticket t on t.key=m.ticket where fts match ? and m.ticket<>? and m.kind in ('user','assistant')
           group by m.ticket order by hits desc limit ?""", (fts_query(" ".join(filter(None, row))), key, limit)).fetchall()


def conversation(db, where, args):
    return db.execute(f"select id, kind, text from msg where {where} and kind in ('user','assistant') order by ts, id", args).fetchall()


def show(rows, width=600):
    for i, kind, text in rows:
        print(f"[{i}] {kind}: {' '.join(text.split())[:width]}\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", default=DEFAULT_DB, help=f"database path (default {DEFAULT_DB}, or set ONTOL_DB)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("ingest", help="load Claude Code transcripts"); c.add_argument("--source", default=DEFAULT_SOURCE)
    c = sub.add_parser("tickets", help="load tickets from a JSON file"); c.add_argument("file")
    c = sub.add_parser("search", help="search what people and agents said")
    c.add_argument("words"); c.add_argument("--ticket"); c.add_argument("--client")
    c = sub.add_parser("ticket", help="a ticket and the conversation behind it"); c.add_argument("key")
    c = sub.add_parser("client", help="everything done for one client"); c.add_argument("name")
    c = sub.add_parser("related", help="earlier work that resembles this ticket"); c.add_argument("key")
    c = sub.add_parser("around", help="the conversation near a message id"); c.add_argument("id", type=int)
    sub.add_parser("unlinked", help="sessions with no ticket on their branch")
    a = p.parse_args(argv)
    db = connect(a.db)

    if a.cmd == "ingest":
        files, added = ingest(db, a.source)
        print(f"{files} transcript files, {added} new messages, db at {a.db}")
    elif a.cmd == "tickets":
        print(f"{load_tickets(db, a.file)} tickets loaded")
    elif a.cmd == "search":
        for i, ticket, client, kind, text in search(db, a.words, a.ticket, a.client):
            print(f"[{i}] {ticket or 'no ticket'} ({client or '-'}) {kind}: {' '.join(text.split())}\n")
    elif a.cmd == "ticket":
        t = db.execute("select key,title,client,owner,status,pr,description from ticket where key=?", (a.key,)).fetchone()
        if t:
            print(f"{t[0]}: {t[1]}\nclient: {t[2]}  owner: {t[3]}  status: {t[4]}  pr: {t[5] or '-'}\n{t[6] or ''}\n")
        else:
            print(f"{a.key}: not in tickets\n")
        rows = conversation(db, "ticket=?", (a.key,))
        print(f"{len(rows)} messages\n")
        show(rows)
    elif a.cmd == "client":
        for key, title, status, owner, n in db.execute(
                """select t.key,t.title,t.status,t.owner,count(m.id) from ticket t left join msg m
                   on m.ticket=t.key and m.kind in ('user','assistant') where lower(t.client)=lower(?)
                   group by t.key order by t.key""", (a.name,)):
            print(f"{key}  {status:<12} {owner:<8} {n:>3} msgs  {title}")
    elif a.cmd == "related":
        rows = related(db, a.key)
        if not rows:
            print("nothing related found")
        for key, title, client, status, hits in rows:
            print(f"{key}  {client}  {status}  {hits} matching messages\n  {title}")
    elif a.cmd == "around":
        show(db.execute("select id,kind,text from msg where id between ? and ? and kind in ('user','assistant') order by id", (a.id - 4, a.id + 4)).fetchall(), 1200)
    elif a.cmd == "unlinked":
        for session, repo, branch, n in db.execute(
                "select session,repo,branch,count(*) from msg where ticket is null group by session,repo,branch"):
            print(f"{session}  {repo}  branch={branch}  {n} msgs")


if __name__ == "__main__":
    sys.exit(main())
