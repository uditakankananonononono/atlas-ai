# Supplied grounding must respect the critique cutoff

Corpus retrieval filters future observations, but critique/build_report also
accept supplied GroundingHit records. They previously counted their IDs as
evidence even when timestamps were future or timezone-naive. Critique now refuses
such grounding and requires an aware cutoff. build_report uses the same check.
Local deterministic future/naive hit tests fail before and pass after; no web or
model verification is performed. Timestamps, IDs, URLs and content still come
from callers and are not authenticated. Citation entailment, forged timestamps,
revision without a cutoff and persistent source receipts remain unchanged.
This is temporal consistency checking, not provenance authentication or M03 closure.
