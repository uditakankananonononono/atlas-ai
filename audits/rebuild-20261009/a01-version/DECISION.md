# A01 version decision, 2026-10-09

Decision: retain the currently pinned Next.js 16.3.8 App Router runtime. Do not downgrade to Next.js 14 and do not create a second compatibility target merely to satisfy the historic version text. Adopt an explicit version exception/amendment for the working architecture, while preserving the original source requirement verbatim. This is a design decision, not independent acceptance or a claim that literal A01 passed.

Recovered question: project decision question recorded October8 21:33:10:
"One decision needed on the atlas source-unit queue: A01 says Next 14 literally, but main is already on Next 16.3.6 (package, lock, and renamed test all assert 16.3.6). Building A01 as written would mean downgrading the runtime, which is a security/regression move I won't make silently. Options: (a) keep 16.3.6 and amend the A01 spec line, or (b) build an isolated Next 14 compatibility target alongside. A02-A06 are running meanwhile, so nothing else waits on this."

Correction to the recovered question's runtime version: exact source base a1fbe5970471e50dad1df2bb511e47a15506723a now declares16.3.8, not16.3.6, in frontend/package.json; lock and tests/test_technical_architecture_real_frontend.py match16.3.8. Earlier16.3.6 wording is historical, not current.

Original A01 source excerpt preserved from audits/technical-spec-line-by-line.json:
"Frontend: Next.js 14 (App Router), React 18, Tailwind CSS, shadcn/ui components, React Flow for graph visualisations, Recharts for dashboards."
The row's requirement is "Next.js 14 App Router frontend." No silent rewriting of that original. The source Google Doc itself is not changed by this decision.

Rationale: existing runtime/lock/test target is16.3.8, with an already audited point update from16.3.6. audits/rebuild-20261008/source-units/frontend-security/README.md describes that update and retained findings; it does not establish current zero vulnerabilities. Downgrade would undo that accepted runtime path and require new security/build/compatibility acceptance. A parallel Next14 target would add maintenance without demonstrated product need. App Router intent is kept, version deviation is explicit. The version decision alone does not close all frontend architecture rows or deployment readiness.

Honesty corrections to prepare for separate audit:
- technical-spec-line-by-line.json currently marks literal A01 verified-pushed and names obsolete test_a01_next14_is_installed_and_app_router_build_source_exists. Actual test is test_a01_declared_next_version_matches_lock_and_app_router_source_exists. Correct the status/evidence to version-amended scope, not literal Next14 acceptance, and recalculate affected counts.
- README.md's "pinned Next.js16.3.6" is historical and must be labeled as such or updated with current16.3.8 provenance. Historical zero-production-advisory result must not become a current clean-security claim.
- docs/SPEC_GAP_ACCEPTANCE_STATUS.md's Next15/React19 statement is stale against current source16.3.8/React18.3.1. Quote/correct it with exact source references.

Independent gate update, October9 14:55:24IST: independent review returned SCOPED PASS on consistency for retaining16.3.8 and the explicit version exception. A01 counts only as version-amended, SCOPED, never literal-Next-14 verified. Resulting documentation/count corrections are to return to the gate after landing; no completion declaration until that review. No runtime downgrade, source-document edit, main commit, landing or new security-acceptance claim has occurred at this preparation step. The memo1+2 reviewed candidate remains byte-identical584b985de27c13f9085f2cd96d128c894b87aea3.
