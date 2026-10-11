# TOLER1531 mutation campaign: disclosure and correction

Applies to the 1531 package chain db976cea -> e3d085b6 -> a50eb44e. Disclosure only; no code change.

Earlier claim, kept as reported: the 1531 packages said every mutant was killed in the final run (64/64, later 65/65), including the mutant I named "bounds exact wrong" (the equality `root * root == squares` replaced by `root * root >= squares` in the ceiling helper).

Correction: that mutant is mathematically equivalent. The root is the integer square root, so `root * root <= squares` always; `>=` and `==` are the same condition. A kill reported for it was not semantic proof. The cause I found is a stale bytecode cache in the working clone: a mutated source of the same size written within the same second as an existing cached file can be run from the cache, so a pass or fail may belong to another source. The 64/65 killed counts from those runs are therefore not reliable for that mutant, and I cannot say which other results were affected.

Re-run with the bytecode cache deleted before every mutant and the interpreter started with bytecode writing off: 65 mutants, 64 killed, 1 survived, the survivor being "bounds exact wrong" (equivalent). This re-run output is supplied beside this note. The 3 tests added after the first run were still pinned to real survivors of that run (assumption set, negative nominal, unit echo), but the first run's survivor list may also have been affected.

Status of the claim: "all mutants killed" is withdrawn. Current claim: 65 own mutants, 64 killed in a clean run, 1 equivalent survivor. The same cleanup was applied to the 1533, 1534 and 1540 mutation runs reported in their own packages. This is not an acceptance or closure claim, and the full repository suite is still not run.
