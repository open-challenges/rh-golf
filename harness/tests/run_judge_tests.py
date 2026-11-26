#!/usr/bin/env python3
"""Tests for the judge, with a stand-in Statements.lean so that no Mathlib is needed.

    python3 harness/tests/run_judge_tests.py [--lean PATH] [--judge CMD]

Each folder under cases/ is an entry. It is stripped and closed under imports by count_lines.py, the
same way a real entry is, compiled with `lean -o` (any code in it runs, as in the real build),
exported by ExportEntry.lean and judged by Judge.lean. --export and --judge default to running
those files with `lean --run`; CI passes the compiled programs.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
import count_lines  # noqa: E402

# what the judge must say about each case
EXPECT = {
    "good": {"ok": True, "tracks": {"rh": True, "grh": True}},
    "rh-only": {"ok": True, "tracks": {"rh": True, "grh": False}},
    "wrong-type": {"ok": False, "why": "its type is not exactly RiemannHypothesis"},
    "sorry": {"ok": False, "why": "sorryAx"},
    "axiom": {"ok": False, "why": "cheat"},
    "def-not-theorem": {"ok": False, "why": "not a theorem"},
    "fake-statement": {"ok": False, "why": "not defined by a trusted module"},
    "skip-kernel": {"ok": False, "why": "riemannHypothesis"},       # the kernel rejects it on replay
    "skip-kernel-lemma": {"ok": False, "why": "badLemma"},
}


def compile_entry(lean: str, src: str, out: str, trusted: str, res: count_lines.Result) -> None:
    """Compile the counted modules in import order, as Lake would."""
    deps = {m: [i for i in count_lines.parse_imports(t) if i in res.stripped] for m, t in res.stripped.items()}
    done: set[str] = set()

    def build(m: str) -> None:
        if m in done:
            return
        for d in deps[m]:
            build(d)
        olean = count_lines.module_path(out, m)[: -len(".lean")] + ".olean"
        os.makedirs(os.path.dirname(olean), exist_ok=True)
        env = {**os.environ, "LEAN_PATH": os.pathsep.join([trusted, out])}
        p = subprocess.run([lean, "-R", src, "-o", olean, count_lines.module_path(src, m)], env=env,
                           capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(f"lean failed on {m}:\n{p.stdout}{p.stderr}")
        done.add(m)

    for m in res.stripped:
        build(m)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lean", default=shutil.which("lean") or "lean")
    ap.add_argument("--judge", help="judge command (default: lean --run harness/Judge.lean)")
    ap.add_argument("--export", help="exporter command (default: lean --run harness/ExportEntry.lean)")
    ap.add_argument("--keep", action="store_true", help="keep the work folder")
    args = ap.parse_args()
    judge = shlex.split(args.judge) if args.judge else [args.lean, "--run", os.path.join(HERE, "..", "Judge.lean")]
    export = shlex.split(args.export) if args.export else [args.lean, "--run", os.path.join(HERE, "..", "ExportEntry.lean")]
    # the judge finds Lean's own library through `lean --print-prefix`
    path = os.pathsep.join([os.path.dirname(os.path.abspath(args.lean)), os.environ.get("PATH", "")])
    work = tempfile.mkdtemp(prefix="judge-tests-")
    failures = 0
    try:
        trusted = os.path.join(work, "trusted")
        os.makedirs(trusted)
        subprocess.run([args.lean, "-R", HERE, "-o", os.path.join(trusted, "Statements.olean"),
                        os.path.join(HERE, "Statements.lean")], check=True, env={**os.environ, "LEAN_PATH": trusted})
        for case in sorted(os.listdir(os.path.join(HERE, "cases"))):
            want = EXPECT.get(case)
            if want is None:
                print(f"?    {case}: no expectation", file=sys.stderr)
                failures += 1
                continue
            res = count_lines.count(os.path.join(HERE, "cases", case))
            src, out = os.path.join(work, case, "src"), os.path.join(work, case, "out")
            count_lines.write_stripped(res, src)
            compile_entry(args.lean, src, out, trusted, res)
            count_lines.write_lists(res, os.path.join(work, case))
            ndjson = os.path.join(work, case, "entry.ndjson")
            with open(ndjson, "w") as fh:     # the sandbox side: sees the entry's .olean files
                subprocess.run(export + [os.path.join(work, case, "modules.txt")], stdout=fh, check=True,
                               env={**os.environ, "LEAN_PATH": os.pathsep.join([trusted, out]), "PATH": path})
            result = os.path.join(work, case, "result.json")
            p = subprocess.run(judge + [os.path.join(HERE, "judge-toy.json"), ndjson, os.path.join(work, case, "imports.txt"),
                                        result],   # the trusted side: only the export and trusted files
                               env={**os.environ, "LEAN_PATH": trusted, "PATH": path}, capture_output=True, text=True)
            got = json.load(open(result))
            text = json.dumps(got)
            good = got.get("ok") == want["ok"] and (p.returncode == 0) == want["ok"]
            if "tracks" in want:
                good = good and got.get("tracks") == want["tracks"]
            if "why" in want:
                good = good and want["why"] in text
            print(f"{'ok  ' if good else 'FAIL'} {case}: {text[:300]}")
            if not good:
                failures += 1
                print(p.stderr[-2000:], file=sys.stderr)
    finally:
        if args.keep:
            print(f"work folder: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)
    print(f"{len(EXPECT) - failures}/{len(EXPECT)} judge tests passed" if not failures else f"{failures} judge tests failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
