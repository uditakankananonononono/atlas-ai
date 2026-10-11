# C3 multi-layer human-reasoning

Status: IMPLEMENTED-BOUNDED. Design source: attached AGI build program v2,
C3 section, provided as task design input. Its quoted owner-channel provenance
is not independently authenticated by this unit; this is not permission to send.

Pinned design excerpt:
"when I ask to write my application you should be able to think like oh so to
write I need to search for the best advice online, best tools to guide my writing,
to humanize, authenticity should come through let's clock in to the requirements
of the job and the qualities needed etc. multiple layer thinking".

## What runs

The stdlib-only `c3_layers.run(packet)` runs seven explicit logged layers:
1. Extract supplied requirement lines, deduplicate and assign r1..rN.
2. Rank supplied public/user-supplied HTTPS advice snippets by token overlap.
3. Select supplied zero-cost tools matching those requirement tokens. Never execute.
4. Link sections to supplied fact IDs and advice source IDs.
5. Produce an extractive draft made only from attributed supplied fact text.
6. Check any caller-proposed claim equals every fact it attributes. Refuse invention.
7. Report missing evidence, absent advice, unused facts and review questions.

Each layer has its output and source references. Coverage is computed from
sections containing an attributed fact, not semantic quality, relevance or truth.
Reports include implemented/not_implemented/data_source/as_of and input SHA256.
`as_of` is caller-supplied, null if omitted, never invented from the wall clock.

Inputs: goal, requirements_text (one requirement per line), advice_sources
(id/url/text/access/public-or-user_supplied/as_of), tools (id/capabilities/cost),
facts (id/text/source_id), evidence_map (rN -> fact IDs), optional draft_claims
(text/fact_ids), optional action=draft and as_of. Unknown top-level fields refuse.
Missing evidence creates placeholders and needs_facts, never fabricated claims.
Fact provenance is a caller assertion; no external truth verification is claimed.
Advice is marked untrusted, never interpreted as commands, copied into draft or run.

## Policy and API

The mandatory local `c3_policy` adapter allows draft preparation only. Send/submit,
spend, auto_post, fake_account, trade and scrape refuse with POLICY_REFUSED_*.
Other requested actions refuse. No approval token overrides this draft-only unit.
Adapter will be replaced with shared c30.policy when that interface is settled.

Optional authenticated router:
- POST /api/v1/c31/layers/run
- GET /api/v1/c31/layers/report

Integrator mounts `c3_layers_routes.router` and binds explicit tenants using
`bind_layers_tenant`. Unbound tenants get 503, missing report 404, no auth 401,
invalid packets 422 with refusal code. Latest reports are ephemeral, deep-copied,
per authenticated tenant. No main.py modification in this bundle.

## LIMITS

32 unique requirement lines, 128 rows per collection, 128 references per list,
20,000 characters per text, 1,000,000 characters per serialized input. The HTTP
host must still enforce its own pre-parse request-byte cap and rate limits.
At most 128 configured tenants. Stage output contains supplied private facts, so
retain the host's authentication and do not publicly publish reports.

No claim to human thinking, AGI, best advice, authentic human voice, novel prose,
real tool installation or execution, independent costs/source verification, live
search, network calls, training, applicant submission or a completed application.
The user must verify facts, relevance and wording. Lexical matches can be wrong.
No memory persistence, resume or history: optional HTTP storage is process-local.
This bounded extractive draft mechanism is not a generative writing model.

## Evidence and validation

Tests were written before implementation: first run failed on missing source.
Run `python -m unittest discover -s tests/c3_layers -v` in an environment with
FastAPI/httpx/cryptography for the optional HTTP tests. Core runs on stdlib alone:
`python -m unittest discover -s tests/c3_layers -p test_layers.py -v`.

Mutation suite: `python scripts/c3_layers/mutation_battery.py`. It flips 24 named
policy, attribution, source, limit, accounting and honesty guards. Kill means
behavior tests failed, not a syntax/import failure. It is a finite selected
battery, not proof of all possible mutations or a repository-wide mutation run.
Hand battery: `python scripts/c3_layers/hand_battery.py`.

External validation PENDING. No response from an external validator exists here.
Contract + code + tests form the review packet. Independent landing gate and
full Atlas regression suite are the integrator's work; not claimed completed.
