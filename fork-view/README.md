# ProductOlogy

A demo of what a client fork can do that main can't, in terms a non-engineer can read. FastAPI backend, Next.js frontend.

```bash
./run.sh    # then open http://localhost:3610 (landing page) or /demo (the app)
```

## Deploy to Vercel

Import the repo and set **Root Directory** to `fork-view/web`. It needs no server: the site reads saved results from
`web/public/demo-data`. After changing anything in `data/` or `api/`, run `.venv/bin/python api/export.py`; a test fails if you forget.
Set `NEXT_PUBLIC_CONTACT_URL` to a `mailto:` or booking link to show the "Talk to us" buttons.

All the data is made up: a fictional product called Harbor with two client forks, in `data/`.

- **Computed from the code:** what's added, changed or shared, the groups (each route's first path segment), the lines (a client feature connects to the main feature whose handler makes the same calls), and each file's diff against main. The rule behind each merge suggestion is computed too.
- **Hand-written for this demo:** which extra files belong to which extension (a real version would use the commits on each ticket's branch), the icons and group titles, plain-English names, which capabilities count as the same thing, and the ticket and session context
  (`data/labels.json`, `data/forks.json`). A real version would get these from an LLM, Jira and recorded sessions.

It only compares routes, so UI or logic changes outside a route handler don't show up.

## Worker: compare real repos

`worker/worker.py` compares a public GitHub repo with a fork and writes results to `web/public/pairs/`, which the site shows at `/pairs`.
Standard library only.

```bash
python3 -I worker/worker.py add owner/repo owner/fork    # queued, waits for approval (--approve skips the wait)
python3 -I worker/worker.py list
python3 -I worker/worker.py approve <id>
python3 -I worker/worker.py run --once                   # or leave `run` going to keep checking
```

It only reads git data: no checkout, no install, nothing from the repo is run, and no credentials are used. The diff runs from the
merge-base, so upstream work the fork hasn't pulled isn't counted. Lockfiles, tests, docs, translations, assets and tooling are counted
separately from product code. Product areas come from folder names, so some will read poorly.

`./run.sh` also starts the worker and turns on the form at `/demo`, where you paste two links. Requests from that form skip approval, so the
server only listens on this machine and refuses other sites. On a hosted build the form is switched off.

Not built: taking requests on the hosted site, or uploading results to it. The queue is local files, and `web/public/pairs/` is gitignored.
Requests are tracked with an HttpOnly cookie, so a person can leave and come back. A browser can have one active request at a time.
The cookie is a convenience, not a security control: clearing it gets around the limit, so a public version also needs a limit per IP or login.
