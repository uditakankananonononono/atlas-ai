# META-MODEL: explicit finite Bayesian hypotheses

Row 21 candidate for independent SCOPED acceptance, not complete mental modeling.
This parallel opt-in registry does not rewrite the legacy supplied-weight world
model registry or convert its scores into probabilities.

An explicitly bound tenant registry compares 2..32 declared, mutually exclusive,
exhaustive hypotheses. Each has a finite prior in [0,1], and priors sum to 1
within absolute 1e-12. Assumptions are bounded text maps. A caller supplies the
partition provenance and explicitly accepts conditional independence. These
are assumptions, not verified properties of the world.

Evidence has an identity, source, observation and per-hypothesis likelihoods
in [0,1]. Missing likelihoods may be recorded but cause comparison to abstain.
Unknown hypothesis keys and invalid probabilities refuse atomically. Repeated
identical evidence IDs are idempotent and do not advance the CAS revision;
changed identities refuse. Distinct IDs with repeated observations are still
assumed independent: callers must not encode dependent evidence as independent.

Posterior is normalized prior times the product of supplied conditional
likelihoods, evaluated with sorted log-space summation. Zero likelihoods remove
a hypothesis; zero joint probability for every hypothesis abstains. No evidence
or unconfigured state also abstains, rather than claiming that priors establish
a best world. Results expose posterior probabilities, Shannon entropy in bits,
provenance and assumptions. Equal maxima within 1e-12 return no current best.
Tiny posterior masses can underflow to zero in the final float conversion.

Reconfiguration advances a model-set version, archives the previous complete
hypotheses/evidence state, and clears active evidence so likelihoods cannot
silently transfer to changed assumptions. At most 20 previous versions and
1000 active evidence records per version are accepted. META-DUR supplies one
atomic tenant/kind CAS snapshot. SQL commits before memory publishes; stale
writes and commit failures leave memory unchanged. SQLite restart/isolation is
tested, not deployment or PostgreSQL.

Authenticated mounted `/api/v1/api/modules/20/bayesian-models` configure,
evidence and compare routes require an explicit tenant binding. Unbound tenants
get 503; invalid inputs get 422; stale persistence gets 409. No automatic model
host, retrieval, tool execution or external side effect is performed.

Synthetic acceptance exhaustively enumerates 32 known two-hypothesis cases,
checks exact rational posterior values, reversed evidence ordering,
contradiction, zero/missing likelihoods, uncertainty, version history,
idempotency, numeric stability, rollback, restart and tenant authentication.
Residual: only explicitly registered hypotheses and supplied likelihood models
are compared. Evidence is not independently proven true; priors, closed-world
partition and independence are caller assumptions. This neither discovers all
possible worlds nor verifies real-world truth.
