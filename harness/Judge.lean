import Lean
import LeanExport.Parse

/-!
# The RH Golf judge

    judge <judge.json> <entry.ndjson> <imports.txt> <result.json>

Decides whether a built entry proves the theorems, trusting nothing the entry's code could have
touched:

1. The base environment is imported from trusted files only: Lean, Mathlib and what it pins, and
   the challenge's own `Statements`, found through `LEAN_PATH`. Which of them to import is
   `imports.txt`: the modules the entry's source files import from outside the entry, read from the
   very text that was counted and built.
2. The entry's constants arrive as text, in Lean's NDJSON export format (`entry.ndjson`, written by
   `export-entry` inside the build sandbox). Lean's own parser reads them; the entry's `.olean`
   files, which the entry's code could have written byte by byte, are never loaded here. A constant
   whose name is already in the base environment is dropped: the trusted one stands.
3. Every remaining constant is replayed into the base environment through Lean's kernel.
4. In the replayed environment, each theorem named in `judge.json` must be a theorem whose type is
   exactly its statement constant, that constant must come from its home module (`RiemannHypothesis`
   from Mathlib, the others from `Statements`), and every axiom the theorem depends on must be
   permitted. Axioms are collected by walking the replayed constants.
-/

open Lean

structure TheoremSpec where
  name : String
  type : String
  home : String
  deriving FromJson, ToJson

structure Config where
  theorems : Array TheoremSpec
  tracks : Array (String × Array String)
  permitted_axioms : Array String
  deriving FromJson

def log (msg : String) : IO Unit := IO.eprintln s!"[judge] {msg}"

/-- `"Mathlib.NumberTheory.LSeries"` → `Mathlib.NumberTheory.LSeries` -/
def toName (s : String) : Name := s.toName

/-- All axioms that `root` depends on, walking types, values and constructors in `env`. -/
def axiomsOf (env : Kernel.Environment) (root : Name) : Except String (Array Name) := Id.run do
  let mut seen : NameSet := {}
  let mut todo : Array Name := #[root]
  let mut axs : NameSet := {}
  while h : todo.size > 0 do
    let c := todo[todo.size - 1]
    todo := todo.pop
    if seen.contains c then continue
    seen := seen.insert c
    let some ci := env.find? c | return .error s!"{root} depends on {c}, which is not in the environment"
    if ci matches .axiomInfo _ then axs := axs.insert c
    todo := todo ++ ci.type.getUsedConstants
    if let some v := ci.value? (allowOpaque := true) then
      todo := todo ++ v.getUsedConstants
    if let .inductInfo v := ci then
      todo := todo ++ v.ctors.toArray
  return .ok (axs.toArray.qsort Name.lt)

def jsonArr (xs : Array String) : Json := Json.arr (xs.map Json.str)

/-- Why `t` is not proved in `env`, if it isn't (axioms aside). `base` holds only trusted modules. -/
def theoremProblem (base : Environment) (env : Kernel.Environment) (t : TheoremSpec) : Option String := Id.run do
  let thm := toName t.name
  let stmt := toName t.type
  let some ci := env.find? thm | return some "not found"
  let .thmInfo v := ci | return some "not a theorem"
  unless v.levelParams.isEmpty do return some "has universe parameters"
  unless v.type == .const stmt [] do return some s!"its type is not exactly {stmt}"
  let some idx := base.getModuleIdxFor? stmt | return some s!"{stmt} is not defined by a trusted module"
  let home := base.header.moduleNames[idx.toNat]!
  unless (toName t.home).isPrefixOf home do return some s!"{stmt} comes from {home}, not {t.home}"
  return none

/-- The largest export accepted, in bytes. -/
def maxExportBytes : UInt64 := 16 * 1024 * 1024 * 1024

def readLines (path : System.FilePath) : IO (List String) :=
  return (← IO.FS.readFile path).splitOn "\n" |>.map (·.trimAscii.toString) |>.filter (· ≠ "")

def main (args : List String) : IO UInt32 := do
  let [cfgPath, exportPath, importsPath, outPath] := args
    | IO.eprintln "usage: judge <judge.json> <entry.ndjson> <imports.txt> <result.json>"; return 2
  let write (j : Json) : IO Unit := IO.FS.writeFile outPath (j.pretty ++ "\n")
  let fail (msg : String) : IO UInt32 := do
    log s!"REJECTED: {msg}"
    write <| Json.mkObj [("ok", toJson false), ("error", toJson msg)]
    return 1
  try
    let cfg ← IO.ofExcept <| (Json.parse (← IO.FS.readFile cfgPath)) >>= fromJson? (α := Config)
    initSearchPath (← findSysroot)

    -- 1. the trusted base
    -- every file that is not a `prelude` imports `Init` without saying so
    let imports := (#["Init"] ++ (← readLines importsPath).toArray).map fun m => ({ module := toName m } : Import)
    log s!"importing {imports.size} trusted modules"
    let base ← importModules imports {} (loadExts := false)

    -- 2. the entry's constants, as text
    let size := (← System.FilePath.metadata exportPath).byteSize
    if size > maxExportBytes then return ← fail s!"the export is {size} bytes, over the limit"
    log s!"parsing the export ({size / 1024 / 1024} MiB)"
    let exported ← IO.FS.withFile exportPath .read fun h => LeanExport.parseStream (.ofHandle h)
    let mut newConsts : Std.HashMap Name ConstantInfo := {}
    let mut skipped := 0
    for (name, ci) in exported.constMap do
      if base.contains name then skipped := skipped + 1 else newConsts := newConsts.insert name ci

    -- 3. replay through the kernel
    log s!"replaying {newConsts.size} constants through the kernel ({skipped} already trusted, dropped)"
    let start ← IO.monoMsNow
    let env ← base.toKernelEnv.replay newConsts
    let replayMs := (← IO.monoMsNow) - start
    log s!"the kernel accepted all of them in {replayMs / 1000} s"

    -- 4. statements and axioms
    let permitted : NameSet := cfg.permitted_axioms.foldl (fun s a => s.insert (toName a)) {}
    let mut results : Array (String × Json) := #[]
    let mut proved : NameSet := {}
    for t in cfg.theorems do
      let thm := toName t.name
      let problem? := theoremProblem base env t
      match problem? with
      | some p => results := results.push (t.name, Json.mkObj [("proved", toJson false), ("reason", toJson p)])
      | none =>
        match axiomsOf env thm with
        | .error e => results := results.push (t.name, Json.mkObj [("proved", toJson false), ("reason", toJson e)])
        | .ok axs =>
          let bad := axs.filter (!permitted.contains ·)
          let axj := jsonArr (axs.map (·.toString))
          if bad.isEmpty then
            proved := proved.insert thm
            results := results.push (t.name, Json.mkObj [("proved", toJson true), ("axioms", axj)])
          else
            results := results.push (t.name, Json.mkObj [("proved", toJson false), ("axioms", axj),
              ("reason", toJson s!"uses axioms outside the permitted ones: {bad.toList}")])
    let tracks := cfg.tracks.map fun (tr, thms) => (tr, Json.bool (thms.all (proved.contains <| toName ·)))
    for (n, j) in results do log s!"{n}: {j.compress}"
    let ok := tracks.any fun (_, j) => j == Json.bool true
    write <| Json.mkObj [("ok", toJson ok), ("tracks", Json.mkObj tracks.toList), ("theorems", Json.mkObj results.toList),
      ("trusted_imports", toJson imports.size), ("replayed_constants", toJson newConsts.size),
      ("replay_seconds", toJson (replayMs / 1000))]
    log (if ok then s!"ACCEPTED for {(tracks.filter (·.2 == Json.bool true)).map (·.1)}" else "REJECTED: no track proved")
    return if ok then 0 else 1
  catch e =>
    fail (toString e)
