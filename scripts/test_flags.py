#!/usr/bin/env python3
"""Unit tests for flags.py: python3 -m unittest discover -s scripts"""
import os
import tempfile
import unittest

import count_lines as cl
import flags

HERE = os.path.dirname(os.path.abspath(__file__))


def scan_text(text: str) -> list[str]:
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "Main.lean"), "w", encoding="utf-8") as fh:
        fh.write(text)
    return flags.scan(cl.count(d))


class Flags(unittest.TestCase):
    def test_plain_proofs_are_not_flagged(self):
        self.assertEqual(scan_text("import Statements\ntheorem t : True := by decide\n-- run_cmd in a comment\n"), [])

    def test_constructs(self):
        self.assertTrue(any("code run while elaborating" in f for f in scan_text("run_cmd pure ()\n")))
        self.assertTrue(any("macro or elaborator" in f for f in scan_text("macro \"x\" : term => `(1)\n")))
        self.assertTrue(any("declarations built by hand" in f for f in scan_text("#check Lean.addDecl\n")))
        self.assertTrue(any("files, processes" in f for f in scan_text("def s := include_str \"a\"\n")))
        self.assertTrue(any("unsafe" in f for f in scan_text("unsafe def f : Nat := 1\n")))
        self.assertTrue(any("string literal of 250" in f for f in scan_text('def s := "' + "a" * 250 + '"\n')))
        self.assertTrue(any("numeral of 70 digits" in f for f in scan_text("def n := " + "7" * 70 + "\n")))

    def test_location(self):
        out = scan_text("theorem a : True := trivial\n#eval 1\n")
        self.assertEqual(out, ["code run while elaborating at Main:2: #eval 1"])

    def test_judge_attack_cases_are_flagged(self):
        cases = os.path.join(HERE, "..", "harness", "tests", "cases")
        for case in ("skip-kernel", "skip-kernel-lemma"):
            out = flags.scan(cl.count(os.path.join(cases, case)))
            self.assertTrue(any("code run while elaborating" in f for f in out), out)
            self.assertTrue(any("unsafe code or a trusted shortcut" in f for f in out), out)


if __name__ == "__main__":
    unittest.main()
