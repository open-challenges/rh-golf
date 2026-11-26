import LeanExport.Basic

/-!
# Export an entry's own constants

    export-entry <modules.txt> > entry.ndjson

Runs inside the sandbox, right after the build, on the `.olean` files the build wrote. It imports the
entry's modules and prints, in Lean's NDJSON export format, every constant that one of them defines,
together with what those constants need from other entry modules. Constants of Lean, Mathlib and
`Statements` are referred to by name only: the judge takes them from its own trusted copies.

Nothing here is trusted. The judge parses this text, replays every constant through the kernel
and checks the statements, so a wrong or forged export can only make an entry fail.
-/

open Lean LeanExport

def main (args : List String) : IO UInt32 := do
  let [modulesPath] := args
    | IO.eprintln "usage: export-entry <modules.txt>"; return 2
  initSearchPath (← findSysroot)
  let mods := (← IO.FS.readFile modulesPath).splitOn "\n" |>.map (·.trimAscii.toString)
    |>.filter (· ≠ "") |>.map String.toName
  let modSet : NameSet := mods.foldl (·.insert ·) {}
  let env ← importModules (mods.toArray.map ({ module := · })) {} (loadExts := false)
  let mut theirs : NameHashSet := {}
  let mut ours : Array Name := #[]
  for (n, _) in env.constants do
    let home := (env.getModuleIdxFor? n).map (env.header.moduleNames[·.toNat]!)
    if home.any modSet.contains then ours := ours.push n else theirs := theirs.insert n
  IO.eprintln s!"[export] {ours.size} constants from {mods.length} entry modules"
  M.run env do
    initState env []
    -- marking every other constant as already exported keeps Lean's and Mathlib's out of the file
    modify fun st => { st with visitedConstants := theirs }
    dumpMetadata
    for c in ours.qsort Name.lt do
      dumpConstant c
  return 0
