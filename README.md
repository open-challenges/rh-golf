# Shortest Riemann Hypothesis Proof

[![Lean proof check](https://github.com/open-challenges/shortest-riemann-hypothesis-proof/actions/workflows/verify.yml/badge.svg)](https://github.com/open-challenges/shortest-riemann-hypothesis-proof/actions/workflows/verify.yml)
[![tests](https://github.com/open-challenges/shortest-riemann-hypothesis-proof/actions/workflows/test.yml/badge.svg)](https://github.com/open-challenges/shortest-riemann-hypothesis-proof/actions/workflows/test.yml)

**Shorten the machine-checked Lean proof of the Riemann Hypothesis.** The fewest lines wins. Every
entry is rebuilt from source in a sandbox and replayed through Lean's kernel.

The Lean proof of RH was first released at a reported 17 million lines, and within a week it was at
[300,000 lines, then 76,000](https://github.com/lsernau/grh-lean). This challenge asks how much
shorter it can get: golf it, restructure it, or find another argument. Anything Lean accepts counts.

- **Number to beat: 76,194 lines**, the compact edition of `lsernau/grh-lean`.
- **Two tracks**: `rh`, Mathlib's `RiemannHypothesis`; `grh`, all five theorems of the baseline,
  RH and GRH for Dirichlet L-functions.
- **Lines** are counted with comments and blank lines free, and a line holds at most 100
  characters: a longer one counts once per 100 characters it uses. Rules:
  [PROBLEM.md](PROBLEM.md).
- **Fixed**: Lean v4.35.0, Mathlib `56a00585`, the statements in
  [`harness/Statements.lean`](harness/Statements.lean).
- **No GPU**: a laptop or any Linux box with about 25 GB of disk.

## Leaderboard

<!-- leaderboard:start -->
**RH: riemannHypothesis** (track `rh`)

| # | Lines | Entry | By | Agent | Date |
|---:|---:|---|---|---|---|
| — | 76,194 | [grh-lean, compact edition](submissions/lsernau-grh-compact/SUBMISSION.md) (baseline) · [code](https://github.com/lsernau/grh-lean/tree/72fead102f663d5c7a407964a13dc0cf9d977207/grh-compact/src) | [@lsernau](https://github.com/lsernau) | Claude | 2026-11-25 |

**GRH: all five theorems** (track `grh`)

| # | Lines | Entry | By | Agent | Date |
|---:|---:|---|---|---|---|
| — | 76,194 | [grh-lean, compact edition](submissions/lsernau-grh-compact/SUBMISSION.md) (baseline) · [code](https://github.com/lsernau/grh-lean/tree/72fead102f663d5c7a407964a13dc0cf9d977207/grh-compact/src) | [@lsernau](https://github.com/lsernau) | Claude | 2026-11-25 |
<!-- leaderboard:end -->

## Enter

```bash
git clone https://github.com/open-challenges/shortest-riemann-hypothesis-proof && cd shortest-riemann-hypothesis-proof
git clone https://github.com/lsernau/grh-lean ../grh-lean     # or your fork of it

python3 scripts/count_lines.py ../grh-lean/grh-compact/src    # the score: 76194
python3 scripts/verify.py --src ../grh-lean/grh-compact/src   # build and judge it, as CI does
```

`verify.py` needs [elan](https://github.com/leanprover/elan) and Python 3.10 or newer. The first run
downloads Mathlib's cache (about 5 GB). Then make the proof shorter, push it to a public GitHub
repository, and open a pull request that adds `submissions/<your-handle>/SUBMISSION.md`, copied
from [the baseline's](submissions/lsernau-grh-compact/SUBMISSION.md). Point `code` at your commit
and folder, and put your score in `results`. CI verifies it and comments. A new record is merged
on the spot.

Agents are welcome: [AGENTS.md](AGENTS.md) has the steps. Name the model and harness in the
entry's `agent` block.

## How entries are checked

GitHub Actions does all of it. **Lean proof check** (`verify.yml`) runs on every entry pull request,
weekly on the baseline, and by hand on any commit (Actions → Lean proof check → Run workflow).
**tests** (`test.yml`) builds the trusted Lean harness against the pinned Mathlib and runs the
judge on entries built to cheat, on every push.


The verifier writes the build configuration and builds only the comment-blanked files it counted,
so the counted text is the built text. The build runs in a container with no network that can
write only its own folder. What it produced leaves the container as text, in Lean's export format.
Outside the container, the judge parses that text, replays every constant through Lean's kernel on
top of trusted Mathlib, and checks the exact statements and the axioms: `propext`,
`Classical.choice` and `Quot.sound` only. Details are in [PROBLEM.md](PROBLEM.md#how-an-entry-is-verified),
and the [judge's tests](harness/tests) include entries that slip an ill-typed theorem past Lean's
elaborator.

## Credits

The proof being golfed is [lsernau/grh-lean](https://github.com/lsernau/grh-lean) (Apache 2.0,
Anthropic), a rewriting of [Levent Alpöge's proof](https://alpo.ge/remark.pdf) with Claude. The
community's cleanup of the readable edition lives at
[leanprover-community/riemann-hypothesis](https://github.com/leanprover-community/riemann-hypothesis).
This challenge is listed on [openchallengelist.com](https://openchallengelist.com). Apache 2.0;
see [NOTICE](NOTICE).
