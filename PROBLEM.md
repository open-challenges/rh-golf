---
spec: problem.md/v1
name: RH Golf
tagline: Shorten the machine-checked Lean proof of the Riemann Hypothesis. Fewest lines wins; every entry is rebuilt and replayed through Lean's kernel.
status: active
domain: formal-methods
tags: [lean4, riemann-hypothesis, proof-golf, mathlib, formal-verification]
compute: cpu
compute_details: No GPU. Mathlib comes prebuilt from its cache; building the 76K-line baseline takes one to two hours on 12 cores with 24 GB of memory. CI verifies every entry on a 4-core, 16 GB runner.
deadline: rolling
prizes: recognition only
organizer:
  name: Open Challenge List
  url: https://openchallengelist.com
website: https://github.com/open-challenges/rh-golf
leaderboard: https://github.com/open-challenges/rh-golf#leaderboard

tracks:
  - id: rh
    name: "RH: riemannHypothesis"
    metric: lines
    unit: lines
    direction: minimize
    baseline: 76194
    description: Lines of a Lean 4 proof of Mathlib's RiemannHypothesis, comments and blank lines free, a line counting once per 100 characters it uses. Lean v4.35.0, Mathlib 56a00585.
  - id: grh
    name: "GRH: all five theorems"
    metric: lines
    unit: lines
    direction: minimize
    baseline: 76194
    description: The same count for a proof of all five theorems of the baseline, RH and GRH for Dirichlet L-functions, with the statements of its Statements.lean.

submit:
  how: pull-request
  path: submissions/<handle>/
  format: Only SUBMISSION.md. Its code field pins a commit of your public GitHub repository and the folder holding Main.lean.
  requirements: [Lean v4.35.0 through elan, Mathlib 56a00585 (Lake fetches it), Python 3.10+, about 25 GB of disk]
  verification: CI counts the lines, builds the entry from source in a sandbox with no network, exports its constants and replays every one through Lean's kernel on top of trusted Mathlib. The statements must match exactly; the only axioms allowed are propext, Classical.choice and Quot.sound.
  eligibility: Open to everyone.
  cost: free
  agents: welcome
  attribution: Name the model and harness in the agent block of SUBMISSION.md.

quickstart: |
  git clone https://github.com/open-challenges/rh-golf && cd rh-golf
  git clone --depth 1 https://github.com/lsernau/grh-lean ../grh-lean
  python3 scripts/count_lines.py ../grh-lean/grh-compact/src     # 76194: the number to beat
  python3 scripts/verify.py --src ../grh-lean/grh-compact/src    # build and judge it locally
---

# RH Golf

On 20 November 2026 Levent Alpöge released a Lean proof of the Riemann Hypothesis, written with
Claude, reported at about 17 million lines. Five days later a rewriting by Luke Sernau, colleagues at
Anthropic and Claude, [lsernau/grh-lean](https://github.com/lsernau/grh-lean), brought it to about
300,000 lines of code, and its compact edition to 76,000. How short can it get?

Take any proof that Lean accepts, make it shorter, and enter it. Nothing else constrains the
argument: a different proof counts as much as a golfed one.

## What is proved

The theorems and their statements are those of the compact edition, in its
[`Statements.lean`](harness/Statements.lean), which imports only Mathlib.

| Track | Theorems your `Main.lean` must prove, in the root namespace |
|---|---|
| `rh` | `theorem riemannHypothesis : RiemannHypothesis` (Mathlib's definition) |
| `grh` | `riemannHypothesis` and the other four: `riemannZeta_eq_zero_re : RiemannZetaZerosOnLine`, `LFunction_ne_zero_of_half_lt_re : DirichletLNonvanishingRightOfHalf`, `LFunction_eq_zero_re : DirichletLZerosOnLine`, `LFunction_eq_zero_re_of_isPrimitive : PrimitiveDirichletLZerosOnLine` |

The baseline proves all five in 76,194 lines, so it starts both tracks.

Fixed for everyone: Lean v4.35.0, Mathlib at commit `56a005855ea17e0b0958f73ec801ae140b0a1679` and
the packages it pins, and the compact edition's options (`maxHeartbeats 4000000`,
`autoImplicit false`, `maxSynthPendingDepth 3`, `--tstack=400000`). The verifier writes the
lakefile, so the options are the same for every entry; a `set_option` inside your files is part of
your entry and is counted like any other line.

## The score: lines

[`scripts/count_lines.py`](scripts/count_lines.py) is the scorer.

1. **Which files.** `Main.lean` and every file of your entry that it imports, directly or not.
   Files that `Main` doesn't reach are ignored and not built. `Statements.lean` never counts: the
   challenge's copy replaces yours.
2. **Comments and blank lines are free.** `--` comments and `/- ... -/` blocks, docstrings
   included, are blanked out.
3. **A line holds at most 100 characters.** Every other line costs ⌈width / 100⌉, its width in
   characters once trailing spaces are dropped. A line of 100 characters or fewer costs 1, and a
   250-character line costs 3. Packing short lines together pays off only up to 100 characters,
   Mathlib's line limit, so no layout scores below one line per 100 characters of code.

The baseline has 76,137 lines of code, 56 of them over 100 characters, so it scores 76,194.

The verifier builds the comment-blanked text it counted and nothing else from your repository. So a
comment can never carry anything the proof needs, and the text that was counted is the text that
was built.

## Rules

- The proof must be ordinary Lean source. No proof or code stored as data and turned into Lean at
  build time: no strings, numbers or blobs that a metaprogram decodes, decompresses or parses into
  declarations, and no reading files or the environment while building. Macros, tactics and other
  metaprograms written out in your files are fine; they are counted like everything else.
  Maintainers reject entries that break this rule, whatever the judge said.
- The only dependencies are Lean and the pinned Mathlib with its packages. Import whatever you need
  from them. Your modules may not use the names of their top-level modules (`Mathlib`, `Lean`, ...).
- The only axioms allowed are `propext`, `Classical.choice` and `Quot.sound`: no `sorry`, no
  `native_decide`, no axioms of your own.
- The entry has to build within 280 minutes on the CI runner (4 cores, 16 GB of memory).
- Ties go to the earlier entry.
- Give credit. The compact edition is Apache 2.0, from Anthropic, building on Levent Alpöge's
  proof with Claude: keep its NOTICE and attribution in your repository if you start from it.

## How to submit

1. Put your proof in a public GitHub repository: a folder holding `Main.lean` and the files it
   imports. A fork of [lsernau/grh-lean](https://github.com/lsernau/grh-lean) works as is; the folder
   is `grh-compact/src`.
2. Check it: `python3 scripts/count_lines.py <folder>` for the score, and
   `python3 scripts/verify.py --src <folder>` to build and judge it as CI will.
3. Add `submissions/<your-handle>/SUBMISSION.md` (or `submissions/<your-handle>-<name>/` for
   another entry) in a pull request that changes nothing else. Start from the
   [baseline's](submissions/lsernau-grh-compact/SUBMISSION.md): `code` is
   `https://github.com/<you>/<repo>/tree/<full commit hash>/<folder>`, `results` lists each track
   you entered with exactly the score the counter gives, `author` is your GitHub handle, and the
   `agent` block names the model and harness, if one did the work.
4. CI verifies the commit and comments the result. A new record on any track you entered is merged
   at once, unless the entry runs code while elaborating (`#eval`, `run_cmd`, macros or
   elaborators, hand-built declarations, input and output, `unsafe`) or has very long string or
   number literals (see [`scripts/flags.py`](scripts/flags.py)). Such a record, and any verified
   entry that is not a record, waits for a maintainer.

## How an entry is verified

[`.github/workflows/verify.yml`](.github/workflows/verify.yml), with
[`scripts/verify.py`](scripts/verify.py):

1. **Count.** Fetch the pinned commit, count, and keep only the counted files, comments blanked.
2. **Build** in a Lake workspace the verifier writes, inside a container with no network, no
   capabilities and a read-only root, where your code can write only its own build folder. Lean
   and Mathlib come in read-only.
3. **Export.** In the same container, [`harness/ExportEntry.lean`](harness/ExportEntry.lean)
   writes your entry's constants as text, in Lean's export format. Constants of Lean, Mathlib and
   `Statements` are referred to by name only.
4. **Judge.** Outside the container, [`harness/Judge.lean`](harness/Judge.lean) imports the
   trusted Mathlib and `Statements`, parses the export with Lean's own parser and replays every
   constant through Lean's kernel. It then checks that each theorem has exactly its statement as
   its type, that the statement comes from Mathlib or `Statements`, and that its axioms are the
   three allowed. Nothing your code could have written is loaded as compiled code, so an entry
   that slips an ill-typed proof past the elaborator, or writes forged `.olean` files, is
   rejected by the kernel. [`harness/tests`](harness/tests) holds such entries, and CI runs them.

[Comparator](https://github.com/leanprover/comparator), the Lean FRO's checker, replays the whole
proof, Mathlib included, through two kernels, but it needs 64 GB of memory and a few hours. CI's
runners have 16 GB. [`harness/comparator.json`](harness/comparator.json) and
[`harness/Challenge.lean`](harness/Challenge.lean) are there for anyone who wants to run it on a
record by hand.
