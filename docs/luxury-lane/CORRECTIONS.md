# Corrections to lane claims

Original claim (builder report, commit db1dae5): "Mutation check rerun: 29 of 29 caught, 0 survived (written by me)."

Correction: that claim was wrong for the fix lines added after the facade review. The gate ran its own 15 mutations and found 6 survivors:
1. process-wide lock made a no-op (suite did not bite; the sequential two-instance test passed via the audit check alone)
2. experiment concept_id assignment in build_pitch_package removed (only package["concept_id"] was asserted)
3. source_passages content emptied (test only checked the key exists)
4. gather return_exceptions in check_ideas (the "malformed" idea never raised, so the test passed either way)
5. URL quote() of Wikipedia titles (still untested, documented)
6. __pycache__ clearing in the prototype builder (still untested, documented)

Repairs: survivors 1-4 now have tests that fail under the mutation (concurrent 4-thread test; experiment concept_id asserted via package["experiment"]; passage content asserted equal to the source finding; an idea that really raises; plus combined_fetch single-index failure). Builder re-ran each of these 4 mutations: each fails the suite. 84 luxury tests pass. Survivors 5 and 6 remain untested.

Wording precision: the prototype receipt check rejects a receipt that claims a pass with no passing test results. It is a consistency check, not proof that tests ran. The builder's mutation counts are not independent verification.
