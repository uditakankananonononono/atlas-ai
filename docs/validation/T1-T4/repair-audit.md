# T1-T4 repair audit

Original 26/26 result was a narrow hand-selected campaign, NOT representative guard coverage. Superseded by this repair. No complete mutation-coverage claim.

## Gate
Python 3.12.14, pytest 8.4.2 with real tests/conftest.py: 55 passed, one Starlette deprecation warning. Saved red receipt: six failing repair tests then fixed. Authentication fixture explicitly removes ATLAS_DEV_NO_AUTH. Runtime policy ValueError becomes HTTP 422. Action must be flat dict; only policy None/True/{allowed: True} returns pass. T2 now carries paywall/piracy/credentials/login flags into source validation.

## Fresh AST campaign
471 generated and executed mutants, 425 killed, 46 survived. Each constant/operator/if/raise/return/continue/call-delete site in training_data_units.py is enumerated by the committed campaign; this is still only a particular mutation operator set, not proof of correctness. Campaign executes full unittest suite in-process with fresh imports per mutant for speed; real-conftest pytest gate ran separately. Originals restored after campaign. No runtime/import/collection failure distinguished from assertion kill in the count.

## All surviving sites
Line numbers refer to the repaired file. The JSON contains exact mutant ids and source text. String mutations at refusal codes remain real exact-code pin gaps: tests check exception/category/substrings, not every complete refusal code. Do not claim every refusal string pinned.

- Mutant 0, L1, string +X: Docstring-only mutation, no runtime effect.
- Mutant 19, L48, delete call: Redundant public_url check deletion survives because another check on the same URL/origin enforces refusal; do not claim direct call-site pin.
- Mutant 24, L60, string +X: Docstring-only mutation, no runtime effect.
- Mutant 26, L69, delete call: Redundant public_url check deletion survives because another check on the same URL/origin enforces refusal; do not claim direct call-site pin.
- Mutant 136, L21, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 138, L26, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 141, L29, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 143, L31, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 150, L80, integer +1: Default crawl delay 0 -> 1 does not change behavior under enforced minimum interval 60; equivalent within current configuration.
- Mutant 187, L175, string +X: Prefix string mutation is not exact-pinned; source, rights, security flags and date validation remain pinned by negative tests.
- Mutant 204, L24, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 211, L34, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 213, L50, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 214, L51, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 216, L66, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 217, L71, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 218, L74, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 221, L77, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 222, L79, string +X: User-agent substring matching by stdlib robotparser may treat AtlasPublicCorpusX as the same agent; exact identity not proven. Refusal and >60 delay cases are tested.
- Mutant 223, L79, string +X: User-agent substring matching by stdlib robotparser may treat AtlasPublicCorpusX as the same agent; exact identity not proven. Refusal and >60 delay cases are tested.
- Mutant 224, L80, string +X: User-agent substring matching by stdlib robotparser may treat AtlasPublicCorpusX as the same agent; exact identity not proven. Refusal and >60 delay cases are tested.
- Mutant 225, L80, string +X: User-agent substring matching by stdlib robotparser may treat AtlasPublicCorpusX as the same agent; exact identity not proven. Refusal and >60 delay cases are tested.
- Mutant 226, L81, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 227, L83, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 228, L84, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 242, L110, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 243, L118, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 247, L122, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 254, L146, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 273, L174, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 277, L178, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 300, L76, string +X: rstrip character-set expansion / -> /X remains unpinned for origins ending X; configured normalized roots do not end X, but server-installed arbitrary permits can.
- Mutant 301, L92, integer +1: HTML hidden-depth decrement mutation survives existing valid tag fixtures; malformed/nested tag balancing not fully pinned.
- Mutant 308, L125, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 309, L130, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 326, L152, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 356, L198, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 368, L128, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 369, L129, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 370, L131, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 371, L133, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 373, L137, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 375, L138, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 390, L184, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 404, L135, string +X: Exact string-value pin gap; refusal still occurs but full error string is not asserted.
- Mutant 468, L206, string +X: Changing title-summary separator space to spaceX cannot change current whitespace-token containment query semantics; no exact joined-text output is exposed.

## Original 129-survivor report sites
Added pins cover: URL types/length4096, invalid port, private suffixes, public IPv4, URL return; frozen source/response dataclasses; permit origin/terms validation and all five allowed license strings; fetch interval=60/limit1/max100000, exactly60 scheduling, trailing slash robots URL, exact body limits, specific-agent and wildcard crawl-delay, non200 replies; script/style and block line breaks; computed registry verified count and ingested_records key; shared policy called with raising stub and missing module; exact record boundaries500/100000; provenance fields; unit refusal prefixes; advice/source/summary500 and action forwarding per T1-T4; scope and output keys/values; essay summary500/outcome_verified false; concept keys/candidate cap500; T4 policy log/task; T2 source rights/date/security flags; query1000; XML entity/doctype; Atom namespaced entry/href/summary and nonentry exclusion; invalid transcript URLs; T2 output scope. Remaining exact strings and redundant call sites above are disclosed, not marked killed.

## Still narrower than aspiration
No live source licensing, model training, network transport, global pre-action hook, durable report store or external S9 verdict. Source as_of remains regex-only, not calendar validation. checked_at remains nonempty, not format/calendar validation. Source rights are server-admin installed, not independently verified by runtime. Newline/trailing-dot/127.1 URL ambiguity fixed, but host-name checks do not prove DNS/IP safety; transport still must pin public resolved addresses. Advice summaries remain extractive.
