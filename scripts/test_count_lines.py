#!/usr/bin/env python3
"""Unit tests for count_lines.py: python3 -m unittest discover -s scripts"""
import os
import tempfile
import unittest

import count_lines as cl


def score(text: str) -> int:
    return sum(cl.line_cost(line) for line in cl.strip_comments(text).split("\n"))


class Strip(unittest.TestCase):
    def test_keeps_layout(self):
        text = "theorem a /- c -/ : True := by\n  -- x\n  trivial /- y\n z -/\n"
        out = cl.strip_comments(text)
        self.assertEqual(len(out), len(text))
        self.assertEqual([i for i, c in enumerate(out) if c == "\n"], [i for i, c in enumerate(text) if c == "\n"])
        self.assertEqual(out.split("\n")[0], "theorem a         : True := by")

    def test_line_and_block_comments(self):
        self.assertEqual(cl.strip_comments("a -- b\nc").split("\n"), ["a     ", "c"])
        comment = "/- b /- nested -/ still -/"
        self.assertEqual(cl.strip_comments(f"a {comment} c"), "a " + " " * len(comment) + " c")
        self.assertEqual(cl.strip_comments("/-- doc -/ def x := 1").strip(), "def x := 1")
        self.assertEqual(cl.strip_comments("/-! module doc -/\nx").split("\n"), [" " * 17, "x"])
        # "/--" is one token: the "-" after "/-" cannot also close the comment
        self.assertEqual(cl.strip_comments("/--/ x -/ y").strip(), "y")
        self.assertEqual(cl.strip_comments("a --/- b\nc").split("\n")[1], "c")

    def test_unterminated_block_comment_runs_to_end(self):
        self.assertEqual(cl.strip_comments("a /- b\nc").split("\n"), ["a     ", " "])

    def test_strings(self):
        self.assertEqual(cl.strip_comments('x := "-- not a comment" -- yes'), 'x := "-- not a comment"       ')
        self.assertEqual(cl.strip_comments('x := "a\\"/-" /- c -/'), 'x := "a\\"/-"        ')
        self.assertEqual(cl.strip_comments('r"--" -- c'), 'r"--"     ')
        self.assertEqual(cl.strip_comments('r#"a"--"# -- c'), 'r#"a"--"#     ')

    def test_char_literals(self):
        # '"' must not open a string, so the comment after it is found
        self.assertEqual(cl.strip_comments("c = '\"' -- q"), "c = '\"'     ")
        self.assertEqual(cl.strip_comments("c = '\\'' -- q"), "c = '\\''     ")
        # a prime in a name is not a character literal
        self.assertEqual(cl.strip_comments("h' := \"--\" -- q"), "h' := \"--\"     ")

    def test_guillemets(self):
        self.assertEqual(cl.strip_comments("«a--b» -- c"), "«a--b»     ")


class Cost(unittest.TestCase):
    def test_widths(self):
        self.assertEqual(cl.line_cost(""), 0)
        self.assertEqual(cl.line_cost("    "), 0)
        self.assertEqual(cl.line_cost("x" * 100), 1)
        self.assertEqual(cl.line_cost("x" * 101), 2)
        self.assertEqual(cl.line_cost("x" * 250), 3)
        self.assertEqual(cl.line_cost("x" * 100 + "    "), 1)          # trailing spaces are free
        self.assertEqual(cl.line_cost("ℝ" * 100), 1)                   # characters, not bytes

    def test_packing_pays_up_to_the_width_only(self):
        short = ["exact h"] * 40
        self.assertEqual(score("\n".join(short)), 40)                 # forty short lines
        self.assertEqual(score("; ".join(short)), 4)                   # one line of 358 characters
        packed = "\n".join("; ".join(short[i:i + 11]) for i in range(0, 40, 11))
        self.assertEqual(score(packed), 4)                             # four lines of at most 97
        # no layout beats one line per 100 characters started
        self.assertGreaterEqual(score(packed), -(-len("; ".join(short)) // 100))

    def test_comments_and_blanks_are_free(self):
        self.assertEqual(score("theorem t : True := trivial\n\n-- why\n/-- doc\n  more -/\n"), 1)


class Imports(unittest.TestCase):
    def test_header(self):
        text = "module\nprelude\npublic import A.B\nmeta import C\nimport all D\nimport E\nopen F\nimport G\n"
        self.assertEqual(cl.parse_imports(text), ["A.B", "C", "D", "E"])
        self.assertEqual(cl.parse_imports("import «A B».C\nimport D"), ["A B.C", "D"])
        self.assertEqual(cl.parse_imports("theorem x : True := trivial"), [])


class Closure(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_only_what_main_reaches_counts(self):
        self.write("Main.lean", "import Statements\nimport Mathlib.Tactic\nimport Lib.A\n-- c\ntheorem m : True := trivial\n")
        self.write("Lib/A.lean", "import Lib.B\ntheorem a : True := trivial\n")
        self.write("Lib/B.lean", "theorem b : True := trivial\n")
        self.write("Lib/Unused.lean", "theorem u : True := trivial\n" * 50)
        self.write("Statements.lean", "def RiemannZetaZerosOnLine : Prop := True\n" * 50)
        res = cl.count(self.dir)
        self.assertEqual(sorted(res.stripped), ["Lib.A", "Lib.B", "Main"])
        self.assertEqual(res.score, 4 + 2 + 1)
        self.assertEqual(res.trusted_imports, {"Statements", "Mathlib.Tactic"})

    def test_missing_module(self):
        self.write("Main.lean", "import Lib.Gone\n")
        with self.assertRaises(cl.CountError):
            cl.count(self.dir)

    def test_reserved_names(self):
        self.write("Main.lean", "import Statements\n")
        self.write("Mathlib/Fake.lean", "theorem x : True := trivial\n")
        cl.count(self.dir)                      # not imported: ignored
        self.write("Main.lean", "import Mathlib.Fake\n")
        res = cl.count(self.dir)                # resolved to Mathlib, which the entry may not ship
        self.assertNotIn("Mathlib.Fake", res.stripped)

    def test_links_are_refused(self):
        self.write("Main.lean", "import Lib.A\n")
        os.makedirs(os.path.join(self.dir, "Lib"))
        other = os.path.join(tempfile.mkdtemp(), "A.lean")
        with open(other, "w") as fh:
            fh.write("theorem a : True := trivial\n")
        os.symlink(other, os.path.join(self.dir, "Lib", "A.lean"))
        with self.assertRaises(cl.CountError):
            cl.count(self.dir)

    def test_crlf_and_bom(self):
        with open(os.path.join(self.dir, "Main.lean"), "wb") as fh:
            fh.write("﻿theorem t : True := trivial\r\n\r\n".encode("utf-8"))
        res = cl.count(self.dir)
        self.assertEqual(res.score, 1)
        self.assertEqual(res.stripped["Main"], "theorem t : True := trivial\n\n")


if __name__ == "__main__":
    unittest.main()
