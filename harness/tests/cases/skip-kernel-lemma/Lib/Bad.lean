import Statements
import Lean
open Lean Elab Command
-- an ill-typed lemma in another module, used by an honest-looking Main
set_option debug.skipKernelTC true in
run_cmd liftCoreM do
  addDecl (.thmDecl { name := `badLemma, levelParams := [], type := mkConst ``RiemannHypothesis, value := mkConst ``True.intro })
