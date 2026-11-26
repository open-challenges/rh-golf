#!/usr/bin/env python3
"""Read the entry a pull request submits, as data: never checks out or runs anything from it.

    REPO=owner/name GH_TOKEN=... python3 scripts/pr_entry.py <pr number> > entry.json

A valid entry pull request adds or changes exactly one file, submissions/<folder>/SUBMISSION.md,
where <folder> is the author's GitHub handle, optionally followed by -something, and the author is
among the entry's authors. Prints {"ok": true, ...} with the parsed entry, or {"ok": false,
"error": ...}; the exit code is 0 either way, so that the workflow can report the reason.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entries  # noqa: E402


def gh(*args: str) -> str:
    return subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True).stdout


def read(pr: int) -> dict:
    repo = os.environ["REPO"]
    info = json.loads(gh(f"repos/{repo}/pulls/{pr}"))
    login = info["user"]["login"]
    pages = json.loads(gh("--paginate", "--slurp", f"repos/{repo}/pulls/{pr}/files?per_page=100"))
    files = [f for page in pages for f in page]
    # the commit the workflow run is about, not whatever the branch points at by now
    sha = os.environ.get("HEAD_SHA") or info["head"]["sha"]
    base = {"pr": pr, "author": login, "head_sha": sha}
    if len(files) != 1:
        return {**base, "ok": False, "error": f"an entry pull request changes exactly one file, submissions/<you>/SUBMISSION.md; this one changes {len(files)}"}
    f = files[0]
    parts = f["filename"].split("/")
    if len(parts) != 3 or parts[0] != entries.SUBMISSIONS or parts[2] != "SUBMISSION.md" or f["status"] not in ("added", "modified"):
        return {**base, "ok": False, "error": f"{f['filename']} ({f['status']}): an entry adds or changes submissions/<you>/SUBMISSION.md and nothing else"}
    folder = parts[1]
    if not entries.FOLDER.match(folder) or not (folder.lower() == login.lower() or folder.lower().startswith(login.lower() + "-")):
        return {**base, "ok": False, "error": f"the folder must be named after you: submissions/{login}/ or submissions/{login}-<something>/"}
    head = info["head"]["repo"]
    if not head:
        return {**base, "ok": False, "error": "the pull request's branch is gone"}
    text = gh(f"repos/{head['full_name']}/contents/{f['filename']}?ref={sha}", "-H", "Accept: application/vnd.github.raw")
    try:
        e = entries.parse(folder, text)
    except entries.EntryError as err:
        return {**base, "ok": False, "folder": folder, "error": f"SUBMISSION.md: {err}"}
    if login.lower() not in (a.lower() for a in e.authors):
        return {**base, "ok": False, "folder": folder, "error": f"you ({login}) must be among the entry's authors"}
    if e.baseline:
        return {**base, "ok": False, "folder": folder, "error": "baseline: true is for the challenge's own reference entry"}
    return {**base, "ok": True, "folder": folder, "code": e.code, "results": e.results, "title": e.title,
            "authors": e.authors, "date": e.date, "agent": e.agent}


if __name__ == "__main__":
    print(json.dumps(read(int(sys.argv[1])), indent=2))
