# U37: curated high-school competition registry

Excerpt from owner request: "All top competitions for high schoolers".
This is a bounded registry of16 selected competitions, not exhaustive coverage
or a claim that "top" has been objectively established.

Module: backend/app/modules/m01_opportunity_discovery/high_school_competitions_u37.py
Tests: tests/modules/test_m01_high_school_competitions_u37.py
Curation evidence: docs/M01_HS_COMPETITIONS_U37_CURATION_EVIDENCE.md

Existing m01 service.py normalizes supplied feed items with keyword tags and
a deadline regex; collectors/community.py provides public discovery adapters.
This unit adds a fixed declared registry, category/level filtering, exact-key
lookup, summary counts and a registry consistency checker. No registration,
autofill, submission, account creation or outreach happens. Application effects
still require a separate approval path.

## Input and checker contract

- Key/category/level require exact built-in str, not subclasses, and at most128
  raw characters. Unknown valid-sized keys keep the U37-prefixed lookup error.
- Supplied entries must be an exact list or tuple, at most256 rows. Each row is
  an exact dict, at most32 fields. Field names are exact strings at most128
  characters; values are exact strings at most2048 characters. Malformed types,
  subclasses and oversize containers/strings raise ValueError with U37 prefix,
  not AttributeError or TypeError. Length checks precede iteration/echoing.
- Missing required fields, duplicate keys, blank required values, invalid
  category/level/deadline-kind taxonomy, non-HTTPS URLs and invalid dates are
  issues in the returned report. The missing-key fallback marker is '?'.
- checked_at must match exactly10 ASCII YYYY-MM-DD characters and a valid
  calendar date; compact ISO dates are not accepted. A non-string checked_at
  is a typed refusal. URL checks are a bounded HTTPS-prefix consistency check,
  not URL normalization, reachability or registration safety certification.
- list_competitions and get_competition return independent dict copies. Registry
  values are strings, so shallow copies isolate returned records. Direct edits
  to the exported COMPETITIONS constant are outside this API isolation promise.

## Curation and limits

Original labels/eligibility/selection prose are attributed to candidate
curation. The repair fetched all16 official source URLs and extra date pages
on October12,2026, recording the date/cycle checks in the evidence file.
It does not claim independent verification of every eligibility condition.
checked_at remains the original October11 curation stamp. Dates can go stale.

ISEF2027 dates conflict across official pages: grand-award and affiliated-fair
pages say May8-14, college-fair says May9-14, homepage names no2027 dates.
The registry uses source-specific wording, not an unqualified date.
AMC national_us means U.S. progression, not U.S.-only participation; AMC
International exists outside USA/Canada. STS URL is correct and unchanged;
November5,2026 at8pm ET/March11-17,2027 confirmed. USACO2025-26 schedule is
confirmed; no2026-27 schedule appears in fetched homepage, caveat retained.

Tests freeze every field of all16 declared envelopes and fallback marker;
they are contract oracles, not proof that outside sources never change.
Real Python3.12 with repository conftest used for focused floor testing.
Repository-wide and mounted route/application flows are not claimed verified.
