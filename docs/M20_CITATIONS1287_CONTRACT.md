# Row 1287: Legal Citations

## Source and exact delta

Live feature Doc, read 2026-10-11:
https://docs.google.com/document/d/1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY
The unique source entry says only "Legal Citations". The Doc does not print
row numbers; its neighbors match coverage-register row 1287, whose description
is empty. This title is not a complete jurisdiction/style specification.

At public base 4088674fcc3f9c7d96d25471575db6b0a9faa193, the existing mechanism
is legal_support_1260_1309.py:44 citation_validation_map. _authority at lines
78-93 requires nonempty citation/provenance strings. analyze_legal_feature at
129-139 builds a common supplied review template and echoes row_inputs, without
citation-format parsing. Existing routes.py:1592/1602 dispatch and
 tests/modules/test_m20_legal_1260_1309.py:13-24 remain untouched.

Exact delta: a separate local component-schema validator and deterministic
renderer, including closed shape/type checks and row-prefixed refusals. It does
not replace that provenance/review mechanism or claim the title is fulfilled.
No dispatcher, shared ledger, cluster or existing test file is changed.

## Local schemas

`normalize_citation(data)` accepts a dict with `format` and exactly the required
fields plus declared optional fields. No free-text citation parser is provided.

- reporter_case requires case_name, volume, reporter, page, court, year;
  optional pinpoint. Render: `Name, volume reporter page, pinpoint (court year)`.
- neutral_case requires case_name, year, court_code, number; optional paragraph.
  Render: `Name, year court_code number [paragraph]`.
- codified_section requires code_title, section; optional year.
  Render: `code_title § section (year)`.

Optional components are omitted when absent, not when supplied as null. Text
must have 1..500 supplied characters, with no ASCII controls or DEL. Trim and
collapse ordinary spaces; no transliteration, markup escaping or legal-language
rewriting. Integers must be exact Python int, not bool, in 1..9999999; year is
1..9999. Court codes match `[A-Z][A-Z0-9]{0,19}`. Section tokens use alphanumeric
segments separated by dot/hyphen and optional alphanumeric parenthesized suffixes.
These are local declared token grammars, not a claim about a court's syntax.

Output includes normalized text and independent components; callers can pass
those components back under the returned format for an idempotent round trip.
The code returns a new dict and never mutates inputs. All refusals are ValueError
messages prefixed exactly `CITE1287: `. Unknown/missing field names are sorted.
Text is data, not executable instructions. Consumers must escape it for HTML/UI.

## LIMITS

Local schemas, not Bluebook/OSCOLA or any jurisdiction's citation rules. Not legal
advice. No lookup, accounts, retrieval, real-law validity, court existence, case
existence, treatment, accuracy, jurisdiction fit, date currency, pinpoint truth,
external authority verification or filing. Licensed counsel must review before
use. `authority_verified=False`, `style_compliant=False`, and
`counsel_review_required=True` always. Synthetic examples demonstrate schemas,
not real authorities. Title-only bounded scope; no claim of row acceptance.

## Reproduction

Stdlib core and unittest:
`python tests/modules/test_m20_legal_citations1287.py`.
Actual run: isolated /home/sandbox/row702-venv/bin/python -> /usr/bin/python3.10,
Python 3.10.12. No external dependencies or network needed for tests. Python 3.12,
mounted auth/tenant, whole repo suite, Windows and rendered output not run.
Original RED is module-under-test missing; raw GREEN and hand-mutant logs supplied
separately. Routing/integration and independent acceptance are not part of this
package.
