#!/usr/bin/env python3
"""Turn a verification into a pull request comment and a decision.

    python3 scripts/report.py --verdict verdict.json [--entry entry.json] --out DIR

Writes DIR/comment.md and DIR/decision.json: {"labels": [...], "merge": bool}. An entry is merged
automatically when the judge accepted it, its declared values are exactly what was verified, and it
beats the standing best of a track it entered. A verified entry that sets no record waits for a
maintainer.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entries  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fmt(n) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


def decide(entry: dict | None, verdict: dict, bests: dict[str, int]) -> tuple[list[str], bool, list[str]]:
    """labels, merge, lines of explanation"""
    if entry is not None and not entry.get("ok"):
        return ["invalid"], False, [f"❌ **Not an entry yet**: {entry.get('error')}"]
    if not verdict.get("ok"):
        why = [f"❌ **Rejected** at the {verdict.get('stage', '?')} step: {verdict.get('error', 'unknown error')}"]
        if verdict.get("log_tail"):
            why += ["", "<details><summary>End of the build log</summary>", "", "```", verdict["log_tail"][-5000:], "```", "", "</details>"]
        return ["rejected"], False, why
    if verdict.get("stage") != "judge" or "score" not in verdict:
        return ["rejected"], False, [f"❌ **Not verified**: the run stopped after the {verdict.get('stage', 'setup')} step. "
                                     "See the workflow run; a maintainer can re-run it."]
    score, tracks = verdict["score"], set(verdict.get("tracks") or [])
    names = ", ".join(f"`{t}`" for t in sorted(tracks))
    lines = [f"✅ **Verified: {fmt(score)} lines**, proving track{'s' if len(tracks) > 1 else ''} {names}."]
    if entry is None:
        return ["verified"], False, lines
    wrong = [f"- `{t}`: the entry says {fmt(v)}, " + (f"the verified count is {fmt(score)}" if t in tracks else "the judge did not confirm this track")
             for t, v in entry["results"].items() if t not in tracks or v != score]
    if wrong:
        return ["needs-fix"], False, lines + ["", "The values in SUBMISSION.md must be exactly what was verified:", *wrong,
                                              "", "Update SUBMISSION.md; the new commit is verified again."]
    found = verdict.get("flags") or []
    review = ["", "It uses constructs that a maintainer checks before it goes on the board, because the rules forbid "
              "a proof stored as data and turned into declarations at build time:", "",
              *[f"- {f}" for f in found]] if found else []
    records = [t for t in entry["results"] if score < bests.get(t, float("inf"))]
    if records:
        was = "; ".join(f"`{t}` was {fmt(bests[t])}" if t in bests else f"`{t}` had no entry" for t in records)
        if found:
            return ["verified", "record", "needs-review"], False, lines + ["", f"🏆 **New record** ({was})."] + review + [
                "", "A maintainer will review it and merge it."]
        return ["verified", "record"], True, lines + ["", f"🏆 **New record** ({was}). Merging it onto the leaderboard."]
    beat = "; ".join(f"`{t}` best is {fmt(bests[t])}" for t in entry["results"] if t in bests)
    return ["verified"] + (["needs-review"] if found else []), False, lines + [
        "", f"Not a record ({beat}). A maintainer will merge it onto the leaderboard."] + review


def details(verdict: dict, entry: dict | None) -> list[str]:
    c, j = verdict.get("count") or {}, verdict.get("judge") or {}
    rows = []
    code = (entry or {}).get("code") or verdict.get("code")
    if code:
        rows.append(("Entry", code))
    if c:
        rows.append(("Lines (the score)", f"{fmt(c.get('score'))}: {fmt(c.get('code_lines'))} lines of code in {fmt(c.get('files'))} files, "
                                          f"{fmt(c.get('lines_over_100'))} of them over 100 characters"))
    for name, t in (j.get("theorems") or {}).items():
        mark = "✅" if t.get("proved") else "—"
        rows.append((f"`{name}`", f"{mark} " + (f"axioms: {', '.join(t.get('axioms') or []) or 'none'}" if t.get("proved") else t.get("reason", ""))))
    if verdict.get("build_minutes") is not None:
        rows.append(("Build", f"{verdict['build_minutes']} min in the sandbox (no network)"))
    if j.get("replayed_constants") is not None:
        rows.append(("Kernel replay", f"{fmt(j['replayed_constants'])} constants in {j.get('replay_seconds')} s; judge {verdict.get('judge_minutes')} min"))
    if not rows:
        return []
    return ["", "| | |", "|---|---|", *[f"| {k} | {str(v).replace('|', '/')} |" for k, v in rows]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdict", required=True)
    ap.add_argument("--entry")
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-url", default="")
    args = ap.parse_args()
    verdict = json.load(open(args.verdict)) if os.path.exists(args.verdict) else {"ok": False, "stage": "setup", "error": "no verdict was written"}
    entry = json.load(open(args.entry)) if args.entry and os.path.exists(args.entry) else None
    bests = entries.best(entries.load(ROOT))
    labels, merge, lines = decide(entry, verdict, bests)
    body = ["### RH Golf verification", "", *lines, *details(verdict, entry)]
    if args.run_url:
        repo = os.environ.get("GITHUB_REPOSITORY", "open-challenges/rh-golf")
        body += ["", f"[Workflow run]({args.run_url}) · [rules](https://github.com/{repo}/blob/main/PROBLEM.md)"]
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "comment.md"), "w") as fh:
        fh.write("\n".join(body) + "\n")
    with open(os.path.join(args.out, "decision.json"), "w") as fh:
        json.dump({"labels": labels, "merge": merge}, fh)
    print("\n".join(body))
    return 0


if __name__ == "__main__":
    sys.exit(main())
