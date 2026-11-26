"""Constructs a maintainer should look at before a record goes on the board.

The rules forbid storing the proof as data that a metaprogram turns into declarations at build time,
and reading files, the network or the environment while building. The judge can't tell such an
entry from an honest one: what it checks is the proof that came out. So the verifier lists, in the
counted text, what that would take: code run while elaborating, hand-built declarations, input and
output, long string or number literals. A flag doesn't reject anything. It stops a record from
being merged automatically, and the pull request comment shows where to look. The baseline has
none of these.
"""
from __future__ import annotations

import re

import count_lines

# (pattern, what it is): matched on the counted text, comments already blanked
PATTERNS = [
    (r"\b(?:run_cmd|run_tac|run_elab|run_meta)\b|#eval\b|#exec\b", "code run while elaborating"),
    (r"\b(?:initialize|builtin_initialize)\b", "initialization code"),
    (r"\b(?:macro|macro_rules|elab|elab_rules|command_elab|term_elab|tactic_elab)\b", "a macro or elaborator"),
    (r"\b(?:runParserCategory|parseCommand|processCommands|elabCommand\w*|elabTerm\w*|evalConst\w*|evalExpr\w*|Frontend)\b", "parsing or elaborating text"),
    (r"\b(?:addDecl|addAndCompile|addDeclCore|thmDecl|defnDecl|mkAuxTheorem|mkAuxDefinition)\b", "declarations built by hand"),
    (r"\bIO\.(?:FS|Process|getEnv|readFile|appendFile|currentDir)\b|\binclude_str\b|\breadBinFile\b|\bSystem\.FilePath\b", "files, processes or the environment"),
    (r"\bunsafe\b|\bimplemented_by\b|@\[\s*extern\b|\bofReduceBool\b|\bnative_decide\b|\bskipKernelTC\b", "unsafe code or a trusted shortcut"),
]
LONG_STRING = 200     # characters in one string literal
LONG_NUMBER = 60      # digits in one numeral

_STRING = re.compile(r'"(?:[^"\\]|\\.)*"', re.S)
_NUMBER = re.compile(r"(?<![\w.])\d{%d,}" % LONG_NUMBER)


def scan(res: count_lines.Result, limit: int = 30) -> list[str]:
    """One line per finding: `what at Module:line: text`, at most `limit`, then a count of the rest."""
    found: list[str] = []
    total = 0
    for mod in sorted(res.stripped):
        text = res.stripped[mod]
        lines = text.split("\n")

        def at(pos: int) -> int:
            return text.count("\n", 0, pos) + 1

        hits: list[tuple[int, str]] = []
        for pat, what in PATTERNS:
            hits += [(m.start(), what) for m in re.finditer(pat, text)]
        hits += [(m.start(), f"a string literal of {len(m.group()) - 2} characters") for m in _STRING.finditer(text) if len(m.group()) - 2 > LONG_STRING]
        hits += [(m.start(), f"a numeral of {len(m.group())} digits") for m in _NUMBER.finditer(text)]
        for pos, what in sorted(hits):
            total += 1
            if len(found) < limit:
                line = at(pos)
                found.append(f"{what} at {mod}:{line}: {lines[line - 1].strip()[:80]}")
    if total > limit:
        found.append(f"... and {total - limit} more")
    return found
