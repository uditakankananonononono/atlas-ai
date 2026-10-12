# Atlas repair queue batch 1

Base: `78ef85579f738497387e5b6ec84f9c1c3d94a402`. No push.

Test-first: 16 failing cases reproduced before implementation changes. After fixes: 17 new targeted tests pass; selected regression totals 508 passing tests. Ranking-penalty regression was added after the implementation change and is not counted in the original 16 red cases.

| Card | Status | Evidence / limit |
|---|---|---|
| ATLAS-m05.A01 | NARROW DEFECT FIXED | Corrected INTEGRATION.md to match existing refusal behavior. |
| ATLAS-m05.A02 | NARROW DEFECT FIXED | Corrected INTEGRATION.md to match existing refusal behavior. |
| ATLAS-m17a.A01 | NARROW DEFECT FIXED | New regression test covers the listed defect. |
| ATLAS-m17a.A02 | NARROW DEFECT FIXED | New regression test covers the listed defect. |
| ATLAS-m17a.A03 | NARROW DEFECT FIXED | New regression test covers the listed defect. |
| ATLAS-m17a.A04 | NARROW DEFECT FIXED | Added explicit guilt-trip/pressure/manipulate/threaten intent patterns. Keeps blocked + refusal contract. Lexical scanner is not complete semantic intent detection. |
| ATLAS-m17n.A01 | NARROW DEFECT FIXED | New regression test covers the listed defect. |
| ATLAS-m17n.A02 | NARROW DEFECT FIXED | Rejects all openings over 55 words, including those prefixed with a scaffold marker. This is conservative length gating, not semantic authorship detection. |
| ATLAS-m17n.A03 | NARROW DEFECT FIXED | Deduplicates by owner/content hash, bounded global cache with oldest eviction. In-process only; collection responses may repeat evidence while storage does not. |
| ATLAS-m17n.A04 | OPEN; NOT IN BATCH 1 | Requires separate scoped runtime/trust integration; no superficial completion claim. |
| ATLAS-m17n.A05 | CLAIM CORRECTED; IMPLEMENTATION OPEN | Corrected integration doc to distinguish shipped cache/public-JSON wiring from absent PRAW/Whisper/Postgres/vector corpus. Original backend implementation remains open. |
| ATLAS-m18.A01 | NARROW DEFECT FIXED | Scam signals now reach ranking; recruiter no longer matches recruitment flag. Clarified max_scam_signals as maximum allowed, above-max rejects; preserved single-weak-signal contract. |
| ATLAS-m18.A02 | NARROW DEFECT FIXED | New regression test covers the listed defect. |
| ATLAS-m18.A03 | NARROW DEFECT FIXED | New regression test covers the listed defect. |
| ATLAS-m18.A04 | NARROW DEFECT FIXED | Requires nonempty score explanation list, at least 3 sensitivities and an experiment string. Does not validate score correctness or real-world viability. |
| ATLAS-m18.A05 | OPEN; NOT IN BATCH 1 | Requires separate scoped runtime/trust integration; no superficial completion claim. |
| ATLAS-m18.A06 | OPEN; NOT IN BATCH 1 | Requires separate scoped runtime/trust integration; no superficial completion claim. |
| ATLAS-m19.A01 | OPEN; NOT IN BATCH 1 | Requires separate scoped runtime/trust integration; no superficial completion claim. |
| ATLAS-m19.A02 | NARROW DEFECT FIXED | Reserves aggregate pending preview costs under process lock. spent remains actual spend, not estimated cost. No deployment consumer exists; reservation release/account reconciliation remain future work. |
| ATLAS-m19.A03 | NARROW DEFECT FIXED | Refuses model-supplied preview links, unsupported artifact names and high confidence without evidence. Supplied evidence is not independently verified; no claim of truth validation. |
| ATLAS-m19.A04 | OPEN; NOT IN BATCH 1 | Requires separate scoped runtime/trust integration; no superficial completion claim. |
| ATLAS-m19.A05 | OPEN; NOT IN BATCH 1 | Requires separate scoped runtime/trust integration; no superficial completion claim. |
| ATLAS-m19.A06 | OPEN; NOT IN BATCH 1 | Requires separate scoped runtime/trust integration; no superficial completion claim. |

## Known bounds

Advice deduplication is service-level and sequential; the repository has no unique-key/CAS contract, so cross-process concurrent compiles remain unproven. Narrative cache is not durable. Provider fallback catches operational RuntimeError/OSError and parsing errors, not arbitrary programming errors or cancellation. Source URL validation ties blueprints to collected sources, not source truth. Feasibility checks shape requirements, not calibrated scores. Full repository suite and live integration outcomes were not run.

Rows m13-m16 are not changed by this batch.
