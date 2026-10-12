# Instinct-doc groups 77-87: bounded implementations and open acceptance

Base: `4163f497f38420a7f755501034549fc9e2e4a4b0`.
Source read live on 2026-10-12:
https://docs.google.com/document/d/1VRD84FClUlTk5pX8kcW6ZFxGfbAR6MwH8EoWdkCzlss/edit

This patch does not change literal group verdicts to LANDED. Working components
are not proof of the source's universal, million-fold, or best-in-world claims.
Science work remains out of scope. Nothing here claims sentience, AGI, or
superintelligence. No external messages, purchases, installations, patent filings,
web retrievals, public model publication, or remote deployments occur.

## Delivered mechanisms

| Group | Source requirement | New tested mechanism | Literal verdict and remaining gap |
|---|---|---|---|
| 77 | See new ideas/ventures and develop patent applications | `patent_preparation.prepare`: sectioned drafting packet, literal source-corpus comparison, claimed feature-to-description quote checks, explicit missing items | PARTIAL: no live prior-art retrieval, semantic/legal novelty, verified inventorship, jurisdiction-specific filing-ready review or filing |
| 78 | Grow with the user | Actor-isolated durable decision outcomes and growth report; actor leak in inherited read/write fixed; signed-identity owner routes | PARTIAL: owner ratings measure feedback, not independent learned or causal owner-growth results |
| 79 | Prototype new device concepts | Parametric open-top enclosure OBJ mesh and editable OpenSCAD; paired edge/winding checks and signed-volume comparison | PARTIAL: one bounded CAD family, no physical manufacture, material/fit/safety or premium-product assessment |
| 80 | Crack maths problems or dilemmas in any field | Exact rational polynomial evaluation, derivative, antiderivative, definite integrals, candidate-root checks and full certificate replay | PARTIAL: bounded polynomials, not unrestricted cross-field solving |
| 81 | Come up with killer strategies for anything | Finite scenario minimax-regret optimization under budget, feasible-set ranking and per-scenario regret | PARTIAL: supplied utility assumptions, no general or deployment effectiveness |
| 82 | Sugarcode x1,000,000/unrecognizable quality | Executes baseline and candidate callables on immutable task suites; per-module regressions and undefined zero-baseline ratios retained | PARTIAL: no Sugarcode code changed, independent benchmark execution, defined million-fold metric or whole-product improvement |
| 83 | Additional 1000 concepts for AGI-like intelligence | Source/test-digest-bound functional acceptance-manifest checker; detects duplicate implementation aliases, stale/skipped/error receipts, and concept deficit | PARTIAL: checker is not 1000 new functional concepts; no padded inventory added |
| 84 | Try to make it into AGI-like capability | Existing AGI-runtime regression retained; private computation runtime integrates actual bounded work and durable results | PARTIAL: no actual-model E2E, learned/general intelligence or independent transfer result |
| 85 | Merge Meemee to Claire if extra capabilities | Cross-instance SQLite private-computation jobs, authenticated-principal ownership, transactional claim, CAS settlement, restart retention, expired worker unknown holds, executed worker computation | PARTIAL: additive durable computation runtime, not full Meemee deployed parity; existing inventory/deferred capabilities unchanged |
| 86 | 20 more new features and capabilities to each module | Acceptance checker takes explicit expected module list and per-module target; retains deficits instead of counting aliases/file presence | PARTIAL: no claim that 20 new features have been implemented in every Atlas or Sugarcode module |
| 87 | Add info to train models from 10 websites like AdmitSee | Actually fitted multinomial naive-Bayes advice-topic model, token/class counts, serialized artifact checksums, held-out per-class coverage, training-domain count, rights receipts and owner-consent route | PARTIAL: executed on synthetic author-owned fixtures, not licensed content from ten admissions-provider sites; not LoRA/LLM training or admissions success prediction |

## Integration

`backend/app/mission_build/routes.py` is included inside the existing Claire
router. POST `/claire/mission-build/polynomial`, `/strategy`, `/enclosure`,
`/patent-prepare`, and `/admissions/train` run the named computations behind
`require_tenant`. Owner growth/history/outcome routes bind both tenant and actor
from authenticated identity. Tests disable development auth bypass and use
signed RS256 identities.

The legacy tenant-only personalization routes remain unchanged. This patch fixes
ScopedPersonalizationRepository and adds an actor-safe owner surface; it does not
claim every legacy route is actor-isolated.

`worker.execute_one` connects DurableJobs to private computations only. Expired
running jobs become unknown and cannot be automatically claimed or settled.
Unknown work has no exposed reconciliation mechanism yet. There is no automatic
retry, background daemon, HTTP job management, or external tool adapter.

The training route requires an authenticated actor's explicit consent and source
rights receipt assertions. Host verification of actual rights is still required.
The resulting model says `rights_verified=false`. A public source URL is never
sufficient permission. Domain diversity and class coverage do not establish
independent temporal/site held-out evaluation or prevent all paraphrase leakage.

The acceptance checker validates supplied host-runner receipt bindings, not
receipt authenticity, actual runner invocation, source semantics, or independent
review. It always keeps `literal_requirement_closed=false`.

## Evidence

`test-log.txt`: focused new tests plus pre-existing owner-personalization,
Meemee inventory/merge, c37 patent, S3.1 prototype, and AGI runtime regressions.
Run with Python 3.12 and the repository's declared dependencies. One
FastAPI/Starlette httpx deprecation warning is not an acceptance failure.

`synthetic-training-receipt.json`: actual fit and held-out classification on
10 synthetic .example source domains, explicitly not admissions-site evidence.
`polynomial-receipt.json`: computed exact rational results.
`enclosure.obj`, `enclosure.scad`, `enclosure-receipt.json`: generated CAD,
mesh and verified numeric properties. The generated mesh was rendered and
visually inspected as an open-top cavity with four walls and an internal bottom;
physical properties remain unverified.

These are local patch-series commits only. Nothing pushed or deployed.
