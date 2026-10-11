# M23 university-fit filter contract (Unit 14)

Source line (peer-enumerated, from the instinct doc): [P293|L237|bullet]

Module: `backend/app/modules/m23_study_abroad/university_fit.py`
Schema: `backend/app/modules/m23_study_abroad/university_fit_schema.json` (enums, field names and limits are read from it)
Tests: `tests/modules/test_m23_university_fit.py`

## What exists

A bounded mechanism: `evaluate(rows, profile, now, max_age_days=180)` filters a USER-SUPPLIED table of universities against declared criteria and returns, per row, `fits`, `does_not_fit` or `unverified` with reason codes. Pure, stdlib only. It fetches nothing, stores nothing and holds no admissions or aid data.

This is not a claim that the doc line is fulfilled.

## Gaps, word for word (from the unit)

- Needs current verified admissions and aid data; none held.
- "100 countries" and "5000+ pages masterplan" are not credible as bounded units: UNVERIFIED.

## Rows (one per university and country, max 2000)

Fields: `university`, `country`, `source_url` (https, per row), `checked_at` (ISO-8601 with offset, per row), `intl_ug_aid` (full|partial|none), `additional_written_test` (yes|no), `sat` (required|optional|not_considered), `ielts_accepted` (yes|no). No other fields. Duplicate (university, country) is an error.

## Profile

`has_sat` (required bool), `require_full_aid` (default true), `forbid_additional_written_test` (default true), `ielts` (yes|no|maybe, default maybe). No other fields: marks, scores, income and nationality are refused, not used.

## Verdicts

- `unverified`: any unsupported, missing or invalid field; missing, non-https, malformed or credentialed source URL; missing, malformed or timezone-less date; date in the future; date older than `max_age_days` (1..3650, default 180; exactly the limit is still fresh). All reasons are listed. An unverified row is never judged for fit.
- `does_not_fit`, with reasons in this order: `aid_not_full`, `additional_written_test_required`, `sat_required_profile_has_none`, `ielts_not_accepted` (only when profile ielts is not `no`).
- `fits`: fresh, well-formed, and none of the reasons above. It means only that the supplied row satisfies the criteria. It does not mean the source is official or correct, or that admission or funding follows.

Output is sorted by (university, country) and does not depend on input order. Outputs echo `data_provenance`: "caller-supplied table; not verified by this module".

## Not done

No data collection, no admissions-chance estimate, no marks or CBSE matching, no country or college list, no document generation. Wiring into the API is a separate unapplied patch (`unit14-wiring.patch`) for the integrator.
