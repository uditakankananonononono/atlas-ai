# M23 derived public-source registry and robots audit

New-files-only additive module on live fetched base 2acdcd3301a988bb8298308389c0b1e307c27e70. Work began October 11, 2026, 18:03:41 IST. Existing admitted_cases.json already indexes twenty publishers; admitted_cases_bounded.py already implements single-source bounded live title/description checks. This module does not replace them or their routes. It adds a versioned derived registry, JSON Schema, batch robots audit, aggregate report and real dated receipts. No production wiring changed.

## Actual collected output

Twenty existing source leads are normalized into publisher/URL/evidence-type/outcome-basis/example-school records. Titles, applicant names, essay text and profile text are not copied as fields. URLs can contain a name because they are publisher addresses. An unstated example school stays null. Admission outcomes remain source-reported, not independently verified, and are not inferred afresh from the robots request.

The checked-in dated JSON is real execution output, not a simulated successful corpus. Twenty robots endpoints were checked at a polite pace, one request per distinct host per run, no retries or redirects. Final run: seventeen returned interpretable rules allowing the indexed path; three remain unverified (CollegeVine, AdmitRaven, AdmitSee). AdmitRaven returned 307 and AdmitSee 403. The remaining 200 response lacked interpretable robots rules under the strengthened check. The earlier run counted eighteen as allowed before that check; only the final receipt is current. Final execution repeated the twenty-request audit after malformed-robots handling was strengthened. This is twenty checked source records, zero collected application cases and zero essay bodies. No page body was fetched by this collector. Robots allowance is not proof of page reachability, free unrestricted text access, an admission outcome or rights.

## Rights and terms gate

All twenty sources retain license_status=not_granted, terms_status=unreviewed, body_collection_allowed=false and training_rights_granted=false. These values mean no grant has been established for this module, not a finding that a publisher prohibits all use. The collector has no body-fetch path and never treats robots allowance as terms or copyright clearance. Source-only publisher-page reading remains the existing boundary. A site-specific terms review and an applicable license or permission are needed before any future content collection or reuse; this module cannot grant them. No wholesale copying, rehosting, training corpus, scraping of logged-in profiles or sign-ups.

## Execution and limits

From the repository root:

```sh
python -m unittest discover -s tests/modules -p test_m23_public_source_audit.py -v
python backend/app/modules/m23_study_abroad/public_source_audit.py --output /tmp/m23-live-audit.json
```

Executed using Python 3.10.12 and the standard library only. Eight pure schema/rules/report tests are not live-network proof; the separately included raw audit outputs are. The initial RED is a missing-module import error. A later assertion RED refused malformed robots text before the fix. The null-school fixture issue was discovered during registry generation, fixed, and then given a regression test; that particular fix was not tests-first.

Fixed registry only, twenty distinct hosts, HTTPS/no credentials/no fragments/no IP-literal targets, no redirects, ten-second request timeout, 500000-byte retained robots-body cap. Oversized, malformed, undecodable or failed robots responses remain unverified. A public-address DNS preflight reduces obvious private-address requests, but does not pin DNS or guarantee protection against rebinding. The byte cap is on retained body reads, not a universal transport/decompression memory guarantee. Do not use this helper as a general untrusted-URL fetch service.

Robots decisions record the greater of two seconds or declared crawl-delay. Only robots is fetched once per host; no second page request follows. The batch spaces distinct-host requests by two seconds. A future multi-request per-host collector would need to apply the recorded delay and other site-specific rules before proceeding.

No full repository suite, integration/tenant test, independent outcome verification, broad licensing clearance or accepted/landed status is claimed. The linked registry gives the twenty observed publisher URLs; they are inherited source leads rather than newly discovered rights-cleared cases.

## Canonical index and execution boundary

admitted_cases.json remains CANONICAL. public_source_registry_v1.json is a derived projection, not a second source of truth. The drift test compares it exactly with normalize_sources applied to the canonical twenty entries, including order and null school values. If that index changes, the derived snapshot must be regenerated and reviewed; this child adds no automatic rewrite of either catalog. The explicit runner currently reads the derived snapshot, so run the drift test before running it.

The dated audit output is builder-executed live evidence, not peer-reverified. Its historical observations do not become current merely by importing the module. The twenty robots requests occur only when audit_registry is explicitly called or the guarded command-line runner is invoked. No network runs on import; no route imports or route wiring were added. The import-safety test forbids DNS, opener network access and sleep during import. It is a pure safety test, not another live audit. DNS preflight is not rebinding proof, as noted above.

This child reruns pure tests only and preserves the original live receipt without making twenty fresh requests. The original null-school handling change remains the disclosed fix that was not tests-first.
