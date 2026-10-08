# Grant corpus source identity collisions

The in-memory GrantCorpus used dict comprehensions, silently retaining the last
record when multiple documents or opportunities had the same ID. Citation IDs
could therefore resolve to a different URL/content depending on input order.
Construction now refuses duplicate IDs within each collection, even for identical
records. Callers must deduplicate or assign distinct IDs before construction.
Document and opportunity ID namespaces remain separate.

Real in-memory source records with the same ID and different URLs reproduce the
old silent overwrite. Tests verify refusal for both namespaces; existing retrieval,
report and review tests still pass. This is identity collision handling, not source
authentication, citation entailment or a claim-verification engine. Caller-supplied
URLs/content/timestamps remain unverified. SQLite/persistent FundedCorpus, other
M03 paths and opportunity revision/versioning are unchanged. No full M03 closure.
