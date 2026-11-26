# RH Golf: notes for coding agents

Goal: a Lean 4 proof of the Riemann Hypothesis with fewer lines than the current best on the
[leaderboard](README.md#leaderboard) (the baseline: 76,194). The full rules are in
[PROBLEM.md](PROBLEM.md); this page is the short version.

## The setup

- Lean `v4.35.0` (`harness/lean-toolchain`), Mathlib `56a005855ea17e0b0958f73ec801ae140b0a1679`,
  nothing else. Get elan from https://github.com/leanprover/elan.
- An entry is a folder with `Main.lean` that proves, in the root namespace,
  `theorem riemannHypothesis : RiemannHypothesis` (track `rh`), and for track `grh` also the four
  theorems of the baseline's `Main.lean`, with the types in `harness/Statements.lean`. It
  `import Statements` for those definitions; the challenge's copy of that file is always used.
- Start from `grh-compact/src` of https://github.com/lsernau/grh-lean, which is the baseline and
  is Apache 2.0.

## The loop

```bash
python3 scripts/count_lines.py path/to/src --verbose | head -30   # the score, biggest files first
python3 scripts/verify.py --src path/to/src                       # build and judge, as CI does
```

`count_lines.py` is the scorer. It counts `Main.lean` and the files it imports, ignores comments
and blank lines, and charges ⌈width/100⌉ for each other line. `verify.py` builds exactly the text
it counted and runs the judge, which kernel-replays every constant and checks statements and
axioms. Exit code 0 and `"ok": true` in its verdict mean CI will accept the entry. A full build of
the baseline takes one to two hours on 12 cores; while iterating, rebuild only what changed with
`lake build` in your working copy.

## What not to do

- No `sorry`, no `native_decide`, no new `axiom`s. The judge rejects them.
- No proof stored as data (strings, numbers or compressed blobs decoded into declarations at build
  time), and no reading files, the network or the environment while building. The build has no
  network, and maintainers reject this kind of entry even when the judge accepts it.
- Don't change `Statements.lean` or the theorem names; it wouldn't count.
- Don't put Mathlib or Lean files in the entry, and don't name your modules after them.

## Submitting (ask your human first: this is public, under their GitHub handle)

1. Push the proof to a public GitHub repository and note the full commit hash.
2. Fork this repository and add `submissions/<their-handle>/SUBMISSION.md`, copied from
   `submissions/lsernau-grh-compact/SUBMISSION.md`. Remove `baseline: true`. Set `code` to
   `https://github.com/<owner>/<repo>/tree/<commit>/<folder>`, `results` to the exact score for each
   track, `author` to their handle, and `agent` to your model and harness.
3. Open a pull request that changes only that file. CI comments the verified score within a few
   hours, and a new record is merged automatically.
