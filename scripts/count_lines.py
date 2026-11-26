#!/usr/bin/env python3
"""The line counter of the Shortest Riemann Hypothesis Proof challenge: the score of an entry.

    python3 scripts/count_lines.py path/to/src             # score, per-file table on --verbose
    python3 scripts/count_lines.py path/to/src --json      # machine-readable
    python3 scripts/count_lines.py path/to/src --strip-to out/   # also write the files that are built

What counts
-----------
Only the files that the module `Main` imports, directly or through other files of the entry, plus
`Main.lean` itself. `Statements.lean` is the challenge's own file and never counts; Mathlib, Lean
and the other packages Mathlib pins don't count either. Files that `Main` doesn't reach are ignored
(and not built).

In those files, comments are removed: `--` to the end of the line and `/- ... -/` blocks, nested,
doc comments and module docs included. Each comment character becomes a space, so line breaks and
columns stay where they were. Then every line that is not blank costs

    ceil(width / 100)

lines, where width is the number of characters (Unicode code points) once trailing spaces are
dropped. A line of up to 100 characters is one line; a 250-character line is three. So short lines
may be packed together up to 100 characters, as in any golf, but a longer line saves nothing:
no layout scores below one line per 100 characters of code. Comments and blank lines are free.

The checker builds exactly the text this script writes with --strip-to, so a comment can never carry
anything the proof needs: what is counted is what is built.

The lexer follows Lean 4's: `--` and `/-` start comments anywhere outside string literals,
character literals, raw strings (r"...", r#"..."#) and «guillemet» names, and block comments nest.
Braces inside a string are taken as plain text, so a comment marker inside a string nested in an
interpolated string ("{f "--"}") would be misread; the build of the stripped text then fails and
the entry is rejected rather than miscounted.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field

WIDTH = 100
ROOT_MODULE = "Main"
# the challenge's own module: never counted, always replaced by the challenge's copy
TRUSTED_MODULES = {"Statements"}
# packages a proof may import from (the toolchain and what the pinned Mathlib requires);
# an entry may not ship modules under these names
EXTERNAL_ROOTS = {
    "Init", "Std", "Lean", "Lake", "LeanChecker", "LeanExport", "LeanIR", "Leanc",
    "Mathlib", "Batteries", "Aesop", "Qq", "ProofWidgets", "Plausible", "LeanSearchClient", "ImportGraph",
}


def _is_ident_char(c: str) -> bool:
    return c.isalnum() or c in "_'!?"


_CHAR_LIT = re.compile(r"'(?:\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)|[^\\'\n])'")
_RAW_OPEN = re.compile(r'r(#*)"')


def strip_comments(text: str) -> str:
    """Replace every comment character with a space, keeping newlines. Everything else is kept as is."""
    out = list(text)
    n, i = len(text), 0

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "-" and nxt == "-":                      # line comment
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif c == "/" and nxt == "-":                    # block comment, doc comment, module doc
            j = i + 2
            if j < n and text[j] in "-!":                # "/--" and "/-!" are one token in Lean
                j += 1
            depth = 1
            while j < n and depth:
                if text[j] == "-" and j + 1 < n and text[j + 1] == "/":
                    depth -= 1
                    j += 2
                elif text[j] == "/" and j + 1 < n and text[j + 1] == "-":
                    depth += 1
                    j += 2
                else:
                    j += 1
            blank(i, j)
            i = j
        elif c == '"':                                   # string literal
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            i = j + 1
        elif c == "r" and (i == 0 or not _is_ident_char(text[i - 1])) and (m := _RAW_OPEN.match(text, i)):
            close = '"' + m.group(1)                     # raw string: no escapes, ends at "###
            j = text.find(close, m.end())
            i = n if j < 0 else j + len(close)
        elif c == "'" and (i == 0 or not _is_ident_char(text[i - 1])) and (m := _CHAR_LIT.match(text, i)):
            i = m.end()                                  # character literal ('"' must not open a string)
        elif c == "«":                                   # «escaped name»: anything up to »
            j = text.find("»", i + 1)
            i = n if j < 0 else j + 1
        else:
            i += 1
    return "".join(out)


def line_cost(line: str) -> int:
    width = len(line.rstrip(" \t\r"))
    return 0 if width == 0 else math.ceil(width / WIDTH)


def normalize(raw: bytes, path: str) -> str:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CountError(f"{path}: not UTF-8 ({e})") from None
    return text.removeprefix("﻿").replace("\r\n", "\n")


_HEADER_MODIFIERS = {"public", "meta"}


def parse_imports(stripped: str) -> list[str]:
    """Module names imported by a file's header: [module] [prelude] ([public] [meta] import [all] Name)*."""
    toks = re.findall(r"«[^»]*»(?:\.(?:«[^»]*»|[^\s.«]+))*|[^\s«]+(?:\.«[^»]*»)*", stripped[:200_000])
    i, imports = 0, []
    if i < len(toks) and toks[i] == "module":
        i += 1
    if i < len(toks) and toks[i] == "prelude":
        i += 1
    while i < len(toks):
        j = i
        while j < len(toks) and toks[j] in _HEADER_MODIFIERS:
            j += 1
        if j >= len(toks) or toks[j] != "import":
            break
        j += 1
        if j < len(toks) and toks[j] == "all":
            j += 1
        if j >= len(toks):
            break
        imports.append(toks[j].replace("«", "").replace("»", ""))
        i = j + 1
    return imports


def module_path(root: str, module: str) -> str:
    return os.path.join(root, *module.split(".")) + ".lean"


class CountError(Exception):
    pass


@dataclass
class FileStat:
    module: str
    path: str
    physical: int = 0
    nonblank_with_comments: int = 0
    code_lines: int = 0
    long_lines: int = 0
    score: int = 0


@dataclass
class Result:
    score: int = 0
    files: list[FileStat] = field(default_factory=list)
    stripped: dict[str, str] = field(default_factory=dict)   # module -> text that is built
    trusted_imports: set[str] = field(default_factory=set)   # what the counted files import from outside the entry

    def totals(self) -> dict:
        return {
            "score": self.score,
            "files": len(self.files),
            "code_lines": sum(f.code_lines for f in self.files),
            "lines_over_100": sum(f.long_lines for f in self.files),
            "nonblank_with_comments": sum(f.nonblank_with_comments for f in self.files),
            "physical_lines": sum(f.physical for f in self.files),
        }


def count(src_root: str, root_module: str = ROOT_MODULE) -> Result:
    """Score the entry whose sources are under src_root, starting from module root_module."""
    if not os.path.isfile(module_path(src_root, root_module)):
        folder = os.path.basename(os.path.normpath(src_root))
        raise CountError(f"there is no {root_module}.lean in the folder {folder!r}: point at the folder that holds it")
    res, seen, todo = Result(), set(), [root_module]
    while todo:
        mod = todo.pop()
        if mod in seen:
            continue
        seen.add(mod)
        path = module_path(src_root, mod)
        real = os.path.realpath(path)
        if os.path.islink(path) or not real.startswith(os.path.realpath(src_root) + os.sep):
            raise CountError(f"{mod}: {os.path.relpath(path, src_root)} is a link or lies outside the source folder")
        with open(path, "rb") as fh:
            text = normalize(fh.read(), os.path.relpath(path, src_root))
        stripped = strip_comments(text)
        st = FileStat(mod, os.path.relpath(path, src_root))
        for raw_line, line in zip(text.split("\n"), stripped.split("\n")):
            st.physical += 1
            st.nonblank_with_comments += 1 if raw_line.strip() else 0
            cost = line_cost(line)
            st.code_lines += 1 if cost else 0
            st.long_lines += 1 if cost > 1 else 0
            st.score += cost
        if text.endswith("\n"):
            st.physical -= 1                             # the empty piece after the final newline
        res.files.append(st)
        res.stripped[mod] = stripped
        res.score += st.score
        for imp in parse_imports(stripped):
            top = imp.split(".")[0]
            if imp in TRUSTED_MODULES or top in EXTERNAL_ROOTS:
                res.trusted_imports.add(imp)
                continue
            if not os.path.isfile(module_path(src_root, imp)):
                raise CountError(f"{mod} imports {imp}, which is neither in the entry nor in Mathlib or Lean")
            todo.append(imp)
    for st in res.files:
        if st.module.split(".")[0] in EXTERNAL_ROOTS | TRUSTED_MODULES:
            raise CountError(f"{st.path}: an entry may not ship a module named {st.module}")
    res.files.sort(key=lambda f: f.module)
    return res


def write_stripped(res: Result, out_root: str) -> None:
    for mod, text in res.stripped.items():
        path = module_path(out_root, mod)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def write_lists(res: Result, out_dir: str) -> None:
    """modules.txt: the entry's modules (what is built and exported); imports.txt: the trusted modules they
    import (what the judge's base environment is made of)."""
    os.makedirs(out_dir, exist_ok=True)
    for name, items in (("modules.txt", res.stripped), ("imports.txt", res.trusted_imports)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write("".join(f"{m}\n" for m in sorted(items)))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src", help="folder holding Main.lean (for lsernau/grh-lean: grh-compact/src)")
    ap.add_argument("--main", default=ROOT_MODULE, help="root module (default: Main)")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--verbose", action="store_true", help="per-file table")
    ap.add_argument("--strip-to", metavar="DIR", help="write the counted files, comments blanked, under DIR")
    ap.add_argument("--lists-to", metavar="DIR", help="write modules.txt and imports.txt into DIR")
    args = ap.parse_args(argv)
    try:
        res = count(args.src, args.main)
    except CountError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.strip_to:
        write_stripped(res, args.strip_to)
    if args.lists_to:
        write_lists(res, args.lists_to)
    t = res.totals()
    if args.json:
        out = {**t, "width": WIDTH, "per_file": [vars(f) for f in res.files] if args.verbose else None}
        print(json.dumps({k: v for k, v in out.items() if v is not None}, indent=2))
        return 0
    if args.verbose:
        for f in sorted(res.files, key=lambda f: -f.score):
            print(f"{f.score:8d}  {f.path}")
    print(f"score: {t['score']} lines ({t['code_lines']} lines of code, {t['lines_over_100']} of them over "
          f"{WIDTH} characters) in {t['files']} files; {t['nonblank_with_comments']} non-blank lines with "
          f"comments, {t['physical_lines']} in all")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
