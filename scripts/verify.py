#!/usr/bin/env python3
"""Verify an RH Golf entry end to end: count it, build it, export it, judge it.

    # an entry as CI sees it: a public GitHub folder at a pinned commit, built in a sandbox
    python3 scripts/verify.py --code https://github.com/OWNER/REPO/tree/<commit>/<folder> --sandbox docker

    # your own working copy, built directly (no Docker; fine for your own code)
    python3 scripts/verify.py --src path/to/folder/with/Main.lean

The folder holds Main.lean, which proves the theorems, and everything Main imports. Steps:

1. Count (scripts/count_lines.py): the files Main reaches, comments blanked. These blanked files,
   and nothing else from the entry, are what gets built.
2. Prepare the trusted harness (harness/): Mathlib's cache, Statements, the judge and the exporter.
   --skip-harness when it is built already.
3. Build the entry in its own Lake workspace (<work>/build) whose lakefile this script writes: the
   harness's Lean, Mathlib and options, the challenge's Statements.lean, the counted files. With
   --sandbox docker it runs in a container with no network, no capabilities and a read-only root;
   the toolchain and Mathlib are mounted read-only, and the entry's code can write only <work>/build.
4. Export, in the same place: harness/ExportEntry.lean prints the entry's constants as text.
5. Judge, outside: harness/Judge.lean, on that text and trusted files only.

The verdict is written to <work>/verdict.json and summarized on stdout. Exit code 0 means the entry
proves at least one track.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HARNESS = os.path.join(ROOT, "harness")
sys.path.insert(0, HERE)
import count_lines  # noqa: E402

CODE_URL = re.compile(r"^https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100})/tree/([0-9a-f]{40})(?:/([^?#]*?))?/?$")
SANDBOX_IMAGE = "rhgolf-sandbox"
BUILD_TIMEOUT = int(os.environ.get("RHGOLF_BUILD_TIMEOUT", 5 * 3600))


def log(msg: str) -> None:
    print(f"[verify] {msg}", file=sys.stderr, flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, check=True, **kw)


def parse_code_url(url: str) -> tuple[str, str, str, str]:
    m = CODE_URL.match(url.strip())
    if not m:
        raise SystemExit(f"code must be https://github.com/OWNER/REPO/tree/<40-hex commit>/<folder>, not {url!r}")
    owner, repo, sha, sub = m.groups()
    sub = (sub or "").strip("/")
    if any(part in ("", ".", "..") for part in sub.split("/")) and sub:
        raise SystemExit(f"bad folder in {url!r}")
    return owner, repo, sha, sub


def fetch(url: str, dest: str) -> str:
    """Check out the pinned commit (and nothing else) into dest; return the entry folder."""
    owner, repo, sha, sub = parse_code_url(url)
    os.makedirs(dest, exist_ok=True)
    git = ["git", "-C", dest, "-c", "advice.detachedHead=false"]
    run(git + ["init", "-q"])
    run(git + ["fetch", "-q", "--depth", "1", f"https://github.com/{owner}/{repo}.git", sha], timeout=1800)
    run(git + ["checkout", "-q", "FETCH_HEAD"])
    got = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if got != sha:
        raise SystemExit(f"fetched {got}, expected {sha}")
    src = os.path.join(dest, *sub.split("/")) if sub else dest
    if not os.path.isdir(src):
        raise SystemExit(f"{sub or '/'} is not a folder at {sha}")
    return src


LAKE = shutil.which("lake") or os.path.expanduser("~/.elan/bin/lake")


def toolchain_dir() -> str:
    """The folder of the toolchain named in harness/lean-toolchain (holds bin/lean, bin/lake, lib/)."""
    out = subprocess.run(["elan", "which", "lean"], cwd=HARNESS, capture_output=True, text=True, check=True).stdout.strip()
    return os.path.dirname(os.path.dirname(os.path.realpath(out)))


def prepare_harness() -> None:
    run([LAKE, "exe", "cache", "get"], cwd=HARNESS)
    run([LAKE, "build", "Statements", "judge", "export-entry"], cwd=HARNESS)


def entry_lakefile(res: count_lines.Result) -> str:
    """The entry's workspace: the harness's package settings, Statements, and the counted modules."""
    with open(os.path.join(HARNESS, "lakefile.toml"), encoding="utf-8") as fh:
        harness = fh.read()
    head = harness[harness.index("name = "): harness.index("# the statements")]
    head = re.sub(r'(?m)^defaultTargets = .*$', 'defaultTargets = ["Entry"]', head)
    head = "# Written by scripts/verify.py for one entry: the harness's settings, Statements and the entry.\n" + head
    globs = ", ".join(json.dumps(m) for m in sorted(res.stripped))
    return (f"{head}[[lean_lib]]\nname = \"Statements\"\n\n"
            f"# the entry: the files that Main reaches, comments blanked, under entry/\n"
            f"[[lean_lib]]\nname = \"Entry\"\nsrcDir = \"entry\"\nroots = [\"Main\"]\nglobs = [{globs}]\n")


def assemble(res: count_lines.Result, build: str, sandbox: str) -> None:
    if os.path.exists(build):
        shutil.rmtree(build)
    count_lines.write_stripped(res, os.path.join(build, "entry"))
    for f in ("lean-toolchain", "lake-manifest.json", "Statements.lean"):
        shutil.copy(os.path.join(HARNESS, f), os.path.join(build, f))
    with open(os.path.join(build, "lakefile.toml"), "w", encoding="utf-8") as fh:
        fh.write(entry_lakefile(res))
    os.makedirs(os.path.join(build, ".lake"), exist_ok=True)
    if sandbox == "none":   # docker mounts the harness's packages read-only at the same place instead
        os.symlink(os.path.join(HARNESS, ".lake", "packages"), os.path.join(build, ".lake", "packages"))


def build_and_export(work: str, sandbox: str) -> None:
    build = os.path.join(work, "build")
    exporter = os.path.join(HARNESS, ".lake", "build", "bin", "export-entry")
    script = (f"set -e; lake build Entry 2>&1 | tee build.log | grep -v '^✔' | tail -n 400; "
              f"test ${{PIPESTATUS[0]}} -eq 0; "
              f"lake env {exporter} modules.txt > entry.ndjson; ls -l entry.ndjson")
    shutil.copy(os.path.join(work, "modules.txt"), os.path.join(build, "modules.txt"))
    if sandbox == "none":
        run(["bash", "-c", script], cwd=build, timeout=BUILD_TIMEOUT)
        return
    tc = toolchain_dir()
    if subprocess.run(["docker", "image", "inspect", SANDBOX_IMAGE], capture_output=True).returncode:
        with open(os.path.join(HARNESS, "sandbox.Dockerfile"), "rb") as fh:   # no build context: the Dockerfile alone
            run(["docker", "build", "-q", "-t", SANDBOX_IMAGE, "-"], input=fh.read())
    name = f"rhgolf-build-{os.getpid()}"
    cmd = ["docker", "run", "--rm", "--name", name, "--network", "none", "--cap-drop", "ALL",
           "--security-opt", "no-new-privileges", "--read-only", "--tmpfs", "/tmp:exec",
           "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp", "-e", f"PATH={tc}/bin:/usr/bin:/bin",
           "-v", f"{tc}:{tc}:ro", "-v", f"{exporter}:{exporter}:ro",
           "-v", f"{build}:{build}", "-v", f"{os.path.join(HARNESS, '.lake', 'packages')}:{os.path.join(build, '.lake', 'packages')}:ro",
           "-w", build, SANDBOX_IMAGE, "bash", "-c", script]
    try:
        run(cmd, timeout=BUILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True)
        raise


def log_tail(work: str, lines: int = 60) -> str:
    """The end of the build log, without the lines for modules that built fine."""
    try:
        with open(os.path.join(work, "build", "build.log"), encoding="utf-8", errors="replace") as fh:
            kept = [l.rstrip("\n") for l in fh if not l.startswith("✔")]
    except OSError:
        return ""
    return "\n".join(kept[-lines:])[-6000:]


def judge(work: str) -> dict:
    out = os.path.join(work, "result.json")
    if os.path.exists(out):
        os.remove(out)
    p = subprocess.run([LAKE, "env", os.path.join(HARNESS, ".lake", "build", "bin", "judge"),
                        os.path.join(HARNESS, "judge.json"), os.path.join(work, "build", "entry.ndjson"),
                        os.path.join(work, "imports.txt"), out], cwd=HARNESS, timeout=4 * 3600)
    if not os.path.exists(out):
        return {"ok": False, "error": f"the judge exited with {p.returncode} and wrote no verdict"}
    with open(out) as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    src_arg = ap.add_mutually_exclusive_group(required=True)
    src_arg.add_argument("--code", help="https://github.com/OWNER/REPO/tree/<commit>/<folder>")
    src_arg.add_argument("--src", help="a local folder holding Main.lean")
    ap.add_argument("--sandbox", choices=["docker", "none"], default="none")
    ap.add_argument("--work", help="work folder (default: a new temporary one)")
    ap.add_argument("--skip-harness", action="store_true", help="the harness is built already")
    ap.add_argument("--count-only", action="store_true", help="stop after counting")
    args = ap.parse_args(argv)

    work = os.path.abspath(args.work or tempfile.mkdtemp(prefix="rhgolf-"))
    os.makedirs(work, exist_ok=True)
    verdict: dict = {"code": args.code, "src": args.src, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def finish(ok: bool, **kw) -> int:
        verdict.update(kw, ok=ok, finished=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        with open(os.path.join(work, "verdict.json"), "w") as fh:
            json.dump(verdict, fh, indent=2)
        print(json.dumps(verdict, indent=2))
        return 0 if ok else 1

    try:
        src = fetch(args.code, os.path.join(work, "source")) if args.code else os.path.abspath(args.src)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, SystemExit) as e:
        why = e.code if isinstance(e, SystemExit) else "git could not fetch that commit (is the repository public, and the hash complete?)"
        return finish(False, stage="fetch", error=str(why))
    try:
        res = count_lines.count(src)
    except count_lines.CountError as e:
        return finish(False, stage="count", error=str(e))
    count_lines.write_lists(res, work)
    verdict["count"] = res.totals()
    log(f"score {res.score} lines in {len(res.files)} files")
    if args.count_only:
        return finish(True, stage="count")

    if not args.skip_harness:
        prepare_harness()
    assemble(res, os.path.join(work, "build"), args.sandbox)
    if args.code:   # the entry's other files never reach the build
        shutil.rmtree(os.path.join(work, "source"), ignore_errors=True)
    started = time.time()
    try:
        build_and_export(work, args.sandbox)
    except subprocess.CalledProcessError as e:
        return finish(False, stage="build", error=f"the build or the export failed (exit {e.returncode})",
                      build_minutes=round((time.time() - started) / 60, 1), log_tail=log_tail(work))
    except subprocess.TimeoutExpired:
        return finish(False, stage="build", error=f"the build took longer than {BUILD_TIMEOUT // 60} minutes")
    verdict["build_minutes"] = round((time.time() - started) / 60, 1)
    started = time.time()
    result = judge(work)
    verdict["judge_minutes"] = round((time.time() - started) / 60, 1)
    verdict["judge"] = result
    tracks = sorted(t for t, ok in (result.get("tracks") or {}).items() if ok)
    if result.get("ok") and tracks:
        return finish(True, stage="judge", score=res.score, tracks=tracks)
    return finish(False, stage="judge", error=result.get("error") or "no track proved")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
