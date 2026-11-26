"""SUBMISSION.md files: parsing, validation and the standings they make."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import yaml

TRACKS = {"rh": "RH: riemannHypothesis", "grh": "GRH: all five theorems"}
SUBMISSIONS = "submissions"
FOLDER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
HANDLE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
CODE_URL = re.compile(r"^https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100})/tree/([0-9a-f]{40})(?:/([^?#]*?))?/?$")


class EntryError(Exception):
    pass


@dataclass
class Entry:
    folder: str
    title: str
    authors: list[str]
    date: str
    code: str
    results: dict[str, int]
    baseline: bool = False
    agent: dict = field(default_factory=dict)

    @property
    def short_code(self) -> str:
        m = CODE_URL.match(self.code)
        if not m:
            return self.code
        owner, repo, sha, sub = m.groups()
        return f"{owner}/{repo}@{sha[:7]}" + (f" {sub.strip('/')}" if sub else "")


def front_matter(text: str) -> dict:
    m = re.match(r"^﻿?---\r?\n(.*?)\r?\n---\r?\n?", text, re.S)
    if not m:
        raise EntryError("SUBMISSION.md must start with YAML front matter between --- lines")
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise EntryError(f"the front matter is not valid YAML: {str(e).splitlines()[0]}") from None
    if not isinstance(meta, dict):
        raise EntryError("the front matter must be a mapping")
    return meta


def parse(folder: str, text: str) -> Entry:
    meta = front_matter(text)
    if str(meta.get("spec", "")).strip() != "submission.md/v1":
        raise EntryError("spec: submission.md/v1 is required")
    authors = meta.get("authors") or ([meta["author"]] if meta.get("author") else [])
    if not isinstance(authors, list) or not authors or not all(isinstance(a, str) and HANDLE.match(a.lstrip("@")) for a in authors):
        raise EntryError("author (or authors) must be GitHub handles")
    code = str(meta.get("code", "")).strip()
    if not CODE_URL.match(code):
        raise EntryError("code must be https://github.com/OWNER/REPO/tree/<40-hex commit>/<folder with Main.lean>")
    results: dict[str, int] = {}
    for r in meta.get("results") or []:
        track, value = (r or {}).get("track"), (r or {}).get("value")
        if track not in TRACKS:
            raise EntryError(f"unknown track {track!r}; the tracks are {', '.join(TRACKS)}")
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise EntryError(f"the value for {track} must be the line count, a positive whole number")
        results[track] = value
    if not results:
        raise EntryError("results must list at least one track with its line count")
    date = meta.get("date")
    agent = meta.get("agent") if isinstance(meta.get("agent"), dict) else {}
    return Entry(folder=folder, title=str(meta.get("title") or folder)[:140], authors=[a.lstrip("@") for a in authors],
                 date=str(date)[:10] if date else "", code=code, results=results, baseline=meta.get("baseline") is True,
                 agent={k: str(v)[:80] for k, v in agent.items() if k in ("model", "harness", "role")})


def load(root: str) -> list[Entry]:
    out = []
    base = os.path.join(root, SUBMISSIONS)
    for folder in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        path = os.path.join(base, folder, "SUBMISSION.md")
        if FOLDER.match(folder) and os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                out.append(parse(folder, fh.read()))
    return out


def standings(entries: list[Entry]) -> dict[str, list[Entry]]:
    """Per track, best first; ties go to the earlier entry."""
    return {t: sorted((e for e in entries if t in e.results), key=lambda e: (e.results[t], e.date or "9999"))
            for t in TRACKS}


def best(entries: list[Entry]) -> dict[str, int]:
    return {t: rows[0].results[t] for t, rows in standings(entries).items() if rows}
