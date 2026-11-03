#!/bin/sh
# Starts the API on :8500, the site on :3610 and the comparison worker, all on this machine only. Ctrl-C stops them.
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r api/requirements.txt; }
[ -d web/node_modules ] || (cd web && npm install)
.venv/bin/uvicorn main:app --app-dir api --port 8500 &
API=$!
python3 -I worker/worker.py run --interval 2 &
WORKER=$!
trap 'kill $API $WORKER' EXIT
cd web && NEXT_PUBLIC_LIVE_API=1 npm run build && NEXT_PUBLIC_LIVE_API=1 npm start
