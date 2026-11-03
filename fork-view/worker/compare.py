"""Compare a fork with its upstream using git data only: nothing is checked out, installed or run.

The diff runs from the merge-base to the fork, so upstream work the fork hasn't pulled doesn't look like fork work.
"""
import os, re, subprocess
from pathlib import Path

GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_LFS_SKIP_SMUDGE": "1",
           "GIT_ASKPASS": "/bin/false", "SSH_ASKPASS": "/bin/false", "PATH": os.environ.get("PATH", ""), "HOME": os.devnull}
GIT_SAFE = ["-c", "core.hooksPath=/dev/null", "-c", "credential.helper=", "-c", "core.quotepath=off", "-c", "protocol.file.allow=never",
            "-c", "diff.noprefix=false", "-c", "diff.renames=true", "-c", "core.attributesFile=/dev/null"]
MAX_PATCH_LINES = 400  # per file, so one giant file can't swamp the page
TICKET = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b|(?<![\w/])#\d+\b")
TOOLING = re.compile(r"(^|/)(\.github|\.vscode|\.idea|\.husky|\.changeset|docker|scripts?|deploy|deployment|\.claude|\.cursor)(/|$)|(^|/)(dockerfile[^/]*|docker-compose[^/]*|\.[^/]*rc(\.\w+)?|\.env[^/]*|\.gitignore|\.dockerignore|\.[^/]*ignore|makefile|turbo\.json|package\.json|tsconfig[^/]*|[^/]*\.config\.\w+|vercel\.json|netlify\.toml)$", re.I)
GENERATED = re.compile(r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb?|poetry\.lock|uv\.lock|cargo\.lock|go\.sum|composer\.lock|gemfile\.lock)$|(^|/)(dist|build|out|\.next|vendor|node_modules|__snapshots__|generated)(/|$)|\.(min\.js|map|snap)$", re.I)
TRANSLATION = re.compile(r"(^|/)(locales?|i18n|lang|intl|translations?|messages)(/|$)|(^|/)[a-z]{2}(-[A-Za-z]{2})?\.(json|po|ya?ml)$", re.I)
TEST = re.compile(r"(^|/)(tests?|__tests__|e2e|cypress|playwright|spec|fixtures?)(/|$)|\.(test|spec)\.\w+$", re.I)
DOCS = re.compile(r"(^|/)(docs?|documentation)(/|$)|(^|/)(readme|changelog|contributing|license|code_of_conduct|security)[^/]*$|\.mdx?$", re.I)
ASSET = re.compile(r"\.(png|jpe?g|gif|svg|ico|webp|avif|woff2?|ttf|otf|eot|mp4|webm|mp3|pdf|zip)$", re.I)
DATABASE = re.compile(r"(^|/)(migrations?|prisma)(/|$)|\.sql$", re.I)
WRAPPERS = {"src", "app", "apps", "lib", "libs", "packages", "pkg", "internal", "pages", "components", "component", "modules", "features", "routes", "api", "server", "client", "web", "www", "frontend", "backend", "core", "common", "shared", "services", "service", "ui", "views", "controllers", "models", "hooks", "utils", "helpers", "store", "stores", "migrations", "db", "database", "prisma", "public", "assets", "styles"}
ROUTE_FILE = re.compile(r"(?:^|/)(?:app|pages)(/.*?)?/(page|route)\.[jt]sx?$|(?:^|/)pages(/.+?)\.[jt]sx?$")
ROUTE_CODE = re.compile(r"""(?:@(?:\w+\.)?(get|post|put|patch|delete)\(\s*['"](/[^'"]*)['"]|\b(?:app|router|server|fastify)\.(get|post|put|patch|delete)\(\s*['"](/[^'"]*)['"])""", re.I)
DATA_CODE = re.compile(r"^\s*(?:model\s+(\w+)\s*\{|create\s+table\s+(?:if\s+not\s+exists\s+)?[\"'`]?(?:\w+[\"'`]?\.[\"'`]?)?(\w+))", re.I)


def git(repo, *args, timeout=600):
    r = subprocess.run(["git", *GIT_SAFE, *args], cwd=repo, env=GIT_ENV, capture_output=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"git {args[0]} failed: {r.stderr.decode(errors='replace')[-400:]}")
    return r.stdout.decode(errors="replace")


def classify(path):
    """Say why a file isn't product code, or return 'product'."""
    for kind, pattern in (("generated", GENERATED), ("tests", TEST), ("translations", TRANSLATION), ("docs", DOCS), ("assets", ASSET), ("tooling", TOOLING)):
        if pattern.search(path):
            return kind
    return "product"


def module_of(path):
    """Name the product area a file belongs to: its first folder that isn't just structure."""
    if DATABASE.search(path):
        return "database"
    # Route groups and dynamic segments like (main), [id], _authenticated+ and _app are framework structure.
    parts = [p.lstrip("_").rstrip("+") for p in path.split("/")[:-1] if not (p.startswith("(") and p.endswith(")")) and not p.startswith(("[", "$"))]
    parts = [p for p in parts if p]
    # Monorepo package names ('apps/web', 'packages/ui') are structure, not product.
    if len(parts) > 1 and parts[0] in ("apps", "packages", "services", "libs"):
        parts = parts[2:] if parts[1] in WRAPPERS or len(parts) > 2 else parts[1:]
    for p in parts:
        if p.lower() not in WRAPPERS:
            return p
    stem = path.rsplit("/", 1)[-1].split(".")[0]
    return parts[-1] if parts else stem


def route_from_path(path):
    m = ROUTE_FILE.search(path)
    if not m:
        return None
    if m.group(2):
        route = re.sub(r"/\([^/]+\)", "", m.group(1) or "") or "/"
        return ("API" if m.group(2) == "route" else "Page", route)
    route = re.sub(r"/index$", "", m.group(3)) or "/"
    return ("API" if route.startswith("/api") else "Page", route)


def parse_status(text):
    fields, out, i = text.split("\0"), {}, 0
    while i < len(fields) - 1:
        code = fields[i]
        if code[:1] in ("R", "C"):
            out[fields[i + 2]] = {"status": "renamed" if code[0] == "R" else "added", "from": fields[i + 1]}
            i += 3
        else:
            out[fields[i + 1]] = {"status": {"A": "added", "D": "removed"}.get(code[:1], "modified")}
            i += 2
    return out


def parse_patches(text):
    """Map path to (hunk lines, additions, deletions), keeping only what follows the first @@."""
    out = {}
    for chunk in re.split(r"(?m)^(?=diff --git )", text):
        if not chunk.startswith("diff --git "):
            continue
        lines = chunk.split("\n")
        path = None
        for line in lines:
            if line.startswith("+++ b/"):
                path = line[6:].rstrip("\t")
            elif line.startswith("rename to "):
                path = line[10:]
            elif line.startswith("@@"):
                break
        if path is None:
            m = re.match(r"diff --git a/.+ b/(.+)$", lines[0])
            path = m.group(1) if m else None
            for line in lines:
                if line.startswith("--- a/"):
                    path = line[6:]
        if path is None:
            continue
        first = next((i for i, l in enumerate(lines) if l.startswith("@@")), None)
        hunks = [l for l in lines[first:] if not l.startswith("\\")] if first is not None else []
        while hunks and hunks[-1] == "":
            hunks.pop()
        out[path] = (hunks, sum(l.startswith("+") for l in hunks), sum(l.startswith("-") for l in hunks))
    return out


def surfaces_of(path, status, hunks):
    found = []
    route = route_from_path(path)
    if route and status == "added":
        found.append({"kind": route[0], "name": route[1]})
    for line in hunks:
        if not line.startswith("+"):
            continue
        code = line[1:]
        m = ROUTE_CODE.search(code)
        if m:
            verb, target = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            found.append({"kind": "API", "name": f"{verb.upper()} {target}"})
        m = DATA_CODE.match(code)
        if m:
            found.append({"kind": "Data", "name": m.group(1) or m.group(2)})
    return found


def commits_by_file(repo, base, head):
    """Non-merge commits unique to the fork, keyed by the files they touched. Author emails are never read."""
    text = git(repo, "log", "--no-merges", "--name-only", "--format=%x01%h%x02%s%x02%an%x02%cs", f"{base}..{head}")
    commits, by_file = [], {}
    for block in text.split("\x01")[1:]:
        head_line, _, rest = block.partition("\n")
        sha, subject, author, date = head_line.split("\x02")
        c = {"sha": sha, "subject": subject, "author": author, "date": date, "refs": sorted(set(TICKET.findall(subject)))}
        commits.append(c)
        for path in filter(None, rest.split("\n")):
            by_file.setdefault(path, []).append(c)
    return commits, by_file


def compare(repo, base_ref, head_ref):
    """Compare two refs in one git repo and return the summary and each module's files."""
    base, head = git(repo, "rev-parse", base_ref).strip(), git(repo, "rev-parse", head_ref).strip()
    try:
        merge_base = git(repo, "merge-base", base, head).strip()
    except RuntimeError:
        raise ValueError("These two repos share no history, so the second isn't a fork of the first.")
    behind, ahead = git(repo, "rev-list", "--left-right", "--count", f"{base}...{head}").split()
    statuses = parse_status(git(repo, "diff", "--no-ext-diff", "--no-textconv", "-M", "--name-status", "-z", merge_base, head))
    patches = parse_patches(git(repo, "diff", "--no-color", "--no-ext-diff", "--no-textconv", "-M", "-U3", merge_base, head))
    _, by_file = commits_by_file(repo, merge_base, head)
    main_paths = set(filter(None, git(repo, "ls-tree", "-r", "--name-only", "-z", merge_base).split("\0")))
    main_modules = {module_of(p) for p in main_paths if classify(p) == "product"}

    modules, ignored = {}, {}
    for path, info in sorted(statuses.items()):
        kind = classify(path)
        hunks, add, rem = patches.get(path, ([], 0, 0))
        if kind != "product":
            bucket = ignored.setdefault(kind, {"files": 0, "additions": 0, "deletions": 0})
            bucket["files"] += 1; bucket["additions"] += add; bucket["deletions"] += rem
            continue
        m = modules.setdefault(module_of(path), {"files": [], "surfaces": [], "commits": {}})
        truncated = len(hunks) > MAX_PATCH_LINES
        m["files"].append({"path": path, "status": info["status"], "from": info.get("from"), "additions": add, "deletions": rem,
                           "diff": hunks[:MAX_PATCH_LINES], "truncated": truncated})
        for s in surfaces_of(path, info["status"], hunks):
            s["path"] = path
            if not any(x["kind"] == s["kind"] and x["name"] == s["name"] for x in m["surfaces"]):
                m["surfaces"].append(s)
        for c in by_file.get(path, []):
            m["commits"][c["sha"]] = c

    out = []
    for name, m in modules.items():
        add, rem = sum(f["additions"] for f in m["files"]), sum(f["deletions"] for f in m["files"])
        out.append({"id": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "root", "name": name, "is_new": name not in main_modules,
                    "additions": add, "deletions": rem, "surfaces": m["surfaces"], "commits": list(m["commits"].values()), "files": m["files"]})
    out.sort(key=lambda m: (m["is_new"] is False, -(m["additions"] + m["deletions"])))
    seen = {}
    for m in out:  # keep ids unique after slugging
        seen[m["id"]] = seen.get(m["id"], 0) + 1
        if seen[m["id"]] > 1:
            m["id"] += f"-{seen[m['id']]}"
    product = [f for m in out for f in m["files"]]
    return {"base_sha": base[:12], "head_sha": head[:12], "merge_base": merge_base[:12], "ahead": int(ahead), "behind": int(behind),
            "product": {"files": len(product), "additions": sum(f["additions"] for f in product), "deletions": sum(f["deletions"] for f in product)},
            "ignored": ignored, "modules": out}
