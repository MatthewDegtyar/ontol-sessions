"""Write the API's answers to static files, so the website can run the demo with no Python server.

usage: .venv/bin/python api/export.py
"""
import json
from pathlib import Path

import main

OUT = Path(__file__).resolve().parent.parent / "web/public/demo-data"


def snapshot():
    files = {"index.json": main.forks()}
    for fork in main.FORKS:
        view = main.compare_view(fork)
        files[f"{fork}.json"] = {"view": view, "capabilities": {c["key"]: main.capability(fork, c["key"]) for c in view["client"]}}
    return files


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in snapshot().items():
        (OUT / name).write_text(json.dumps(data, indent=1) + "\n")
    print("wrote", OUT)
