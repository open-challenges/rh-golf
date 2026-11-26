-- A stand-in for the real Statements.lean, so the judge can be tested without Mathlib.
def RiemannHypothesis : Prop := ∀ n : Nat, n + 0 = n
def RiemannZetaZerosOnLine : Prop := ∀ n : Nat, 0 + n = n
