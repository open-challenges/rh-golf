---
spec: submission.md/v1
problem: ../../PROBLEM.md
title: grh-lean, compact edition
author: lsernau
date: 2026-11-25
baseline: true

results:
  - track: rh
    value: 76194
  - track: grh
    value: 76194

agent:
  model: Claude
  role: author

code: https://github.com/lsernau/grh-lean/tree/72fead102f663d5c7a407964a13dc0cf9d977207/grh-compact/src
---

# The compact edition of lsernau/grh-lean

The starting point, not an entry of its own: the compact edition of
[lsernau/grh-lean](https://github.com/lsernau/grh-lean) at commit `72fead1` (25 November 2026), a
rewriting of Levent Alpöge's Lean proof with Claude by Luke Sernau, his colleagues at Anthropic, and
Claude. Its README says the Lean text was written by Claude. It proves all five theorems of
`Statements.lean` on Lean v4.35.0 and Mathlib `56a00585`, using only `propext`, `Classical.choice`
and `Quot.sound`. Apache 2.0.

## Count

`python3 scripts/count_lines.py grh-compact/src`: 793 files, 76,137 lines of code (95,018 non-blank
lines with comments, 112,811 in all). 56 of those lines are longer than 100 characters, and each of
them costs one line per 100 characters, so the score is 76,194.

## Reproduce

```bash
git clone --depth 1 https://github.com/lsernau/grh-lean ../grh-lean
python3 scripts/verify.py --src ../grh-lean/grh-compact/src
```
