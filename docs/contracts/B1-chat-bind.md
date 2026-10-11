# B1 chat binding: IMPLEMENTED-BOUNDED

Source pin: "WHOLE CHAT FROM THE BEGINNING IN WHATSAPP"; "BIND EVERY WORd".
Owner-source recovery was performed privately; no owner history is in this patch.

## Behavior

Stdlib-only offline core at `backend/app/modules/m20_general_cognitive_worker/c30_b1`.
Every character of every supplied owner message is retained in private review spans.
Nothing is silently discarded by a request-detection heuristic. Every span starts
UNMAPPED. A reviewer may exclude a non-request with a recorded reason or bind a
request to IMPLEMENTED, PARKED_BY_USER, STOPPED_BY_USER, SUPERSEDED,
REFUSED_WITH_SUBSTITUTE, or UNMAPPED. Counts are computed from those bindings.
The completeness gate fails unless the source is nonempty and UNMAPPED is zero.

IMPLEMENTED requires unit, test, mutation, and commit references. This is evidence
metadata, not automatic code verification. Stops and retractions pin later owner
spans. Revisions require a newer pin and a reason. Stop/park pins require explicit
stop-like wording. Topic association is a reviewer decision, not semantic inference. The stop-pin regex
is only a keyword plausibility guard on a human-assigned classification, not
semantic proof that the message stopped that topic.
Stopped, parked, superseded rows refuse execution. A ledger classification does not
grant execution authority. The offline guard permits reads only.

The SQLite DB adapter queries phone_messages only, author=user, owner channels
WhatsApp/iMessage/SMS/RCS. It independently counts rows, hashes normalized rows,
and can reconcile a second read. Use a read-only connection and a transaction for
snapshot consistency. All earlier records are queried, not a rolling date window.
Supply timezone-bearing ISO timestamps. Adapter uses SQLite julianday for offsets.
The adapter counts all owner-channel rows before timestamp filtering and refuses
PLAN_REFUSED_DB_COUNT if filtered and unfiltered counts differ, including NULL,
unparseable, and future timestamps. Use a snapshot database containing only the
intended as-of records. It does not silently drop invalid dates.

`route_adapter.Routes` handles POST `/api/v1/c30/chat-bind/run` and GET
`/api/v1/c30/chat-bind/report`. Caller must authenticate the tenant before invoking
this adapter. Tenant store is supplied by the host; raw ledger is never returned.
Private ledger output must stay in private storage, never a public repo.

## Integration and tests

Run `python3 -m unittest discover -s tests/b1_chat_bind -v`.
Run `python3 tests/b1_chat_bind/mutation_battery.py`.

New files only. The host must mount the adapter behind existing authentication,
provide private persistent tenant storage, and connect the program-wide c30.policy.
No existing router or policy was changed by this patch.

## LIMITS

This is a completeness gate and evidence ledger, not AGI or proof every requested
feature works. Request semantics, topic matches, quoted-history context, omissions,
and evidence authenticity require review. No unreviewed span gets an automatic
implementation credit. Zero UNMAPPED was not achieved in the private owner-history
trial. DB observations start at enrollment and may miss items; a full conversation
from before enrollment cannot be certified. A non-request exclusion can be wrong
and requires review. Evidence references are not independently executed by B1.
A SQLite snapshot is not a live cloud-DB connector. The HTTP adapter is not mounted
or live-smoke-tested. No external ChatGPT/DeepSeek/Claude/Perplexity verdict exists
for this patch yet. No sending, spending, posting, scraping, application submitting,
keys, network access, or pushes are implemented or performed.
