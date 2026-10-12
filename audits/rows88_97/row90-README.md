# Row 90 supplied product-evidence extraction

Exact selector: tests/modules/test_group90_product_evidence.py and
tests/release/test_scoped_mutations.py with --noconftest -q -rf, Python 3.12.
Per-run timeout 40 seconds. Run row90.json through scoped_mutations.py as in
README. Core mutations: source SHA, exact span start, disagreement retention,
numeric commission bound and no safety-assessment claim. Five CAUGHT by FAILED
tests; source SHA restores checked per mutation. External receipts carry actual
logs and results. No runtime edit.

UNTESTED: automatic platform retrieval, enrollment, ingredient safety, actual
founder truth, parser coverage outside explicit phrases and business outcomes.
Regex provenance is supplied text, not independently verified source truth.
Literal row remains PARTIAL. No quality or superiority promotion.
