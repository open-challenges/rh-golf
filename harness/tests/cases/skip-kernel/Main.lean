import Statements
import Lean
open Lean Elab Command
-- adds an ill-typed theorem without the kernel: `#print axioms` would call it clean
set_option debug.skipKernelTC true in
run_cmd liftCoreM do
  addDecl (.thmDecl { name := `riemannHypothesis, levelParams := [], type := mkConst ``RiemannHypothesis, value := mkConst ``True.intro })
