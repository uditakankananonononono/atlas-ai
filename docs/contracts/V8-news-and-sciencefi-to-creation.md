# V8 news-and-sciencefi-to-creation (module c37.news_create)

Module `backend/app/modules/c37/news_create.py`, entry point `run(request)`, refusal prefix `INTEL`. Tests: `tests/modules/test_c37_news_create_v8.py`. No HTTP handler, no catalog registration, no edit to the package init.

## What it does
Takes SUPPLIED news, paper and tech items plus SUPPLIED interest terms. It ranks the items with a transparent integer score and, for the first `top_n` ranked items that match at least one interest, emits a fixed-template research brief and a ticket. A ticket is data that proposes an idea or prototype for review: status `proposed`, `needs_her_review` true. Nothing is fetched, built, sent, published or written here. Items may be the output of another ingest stream passed in as plain data; this unit imports no ingest function and no other c37 module, and invents no ingest function.

## Nearest existing mechanism
`backend/app/modules/m20_general_cognitive_worker/venture_v2/engines.py:news_create` already exists and does return briefs and tickets, from RSS or Atom feed XML that the caller supplies. This unit is a bounded new surface, not a claim that nothing similar exists. The delta: this unit takes already-parsed generic news, paper and tech items (no XML or feed parsing), refuses with a fixed `INTEL_REFUSED_*` taxonomy and strict input fences, ranks with an integer overlap-plus-recency score with a caller-set `top_n` (1..20), emits fixed-template briefs and proposed tickets only for items that match at least one interest, and is self-contained under the `INTEL` contract. No code is shared with or imported from that module.

## Input (allowlists; any other key is `INTEL_REFUSED_UNKNOWN:<field>`)
Top level: `as_of` (ISO YYYY-MM-DD), `interests` (list of str), `top_n` (int 1..20), `items`. Item: `id`, `kind` (news, paper, tech), `title`, `summary`, `url`, `published` (YYYY-MM-DD), `tags` (list of str, may be empty). All item fields are required.

Caps: items 5000, interests 50 (each 64 characters), tags 20 per item (each 64), id 128, title 300, summary 4000, url 2000.

## Order of checks (the first failure raises)
0. Request is a dict, else `BAD_TYPE:request`.
1. Preflight fence, container counts only and no per-character work: exact dict and list types (subclasses are refused `BAD_TYPE` without being iterated or measured), at most 10010 containers, 32 keys per dict, 64 items per unlisted list (schema lists keep their own caps), 64 characters per key, 10000 characters per string, depth at most 8. Violations give `OVERSIZE:<schema field>` and win over every content error.
2. Forbidden-key scan, recursive through dict values and list items.
3. Non-str dict key: `BAD_TYPE:key`.
4. Unknown key: `UNKNOWN:request` (top) or `UNKNOWN:items` (an item).
5. Top-level types: `as_of` (exact `str`, raw cap 10 characters giving `OVERSIZE:as_of`, then the date grammar), `top_n`, then `interests` and `items` (type, then empty gives `EMPTY`).
6. Each field's own raw cap before any scan or grammar of that field: `OVERSIZE:<field>` for interests, tags, id, kind (5, the longest allowed literal), title, summary, url, published (10); this runs across all items before any item is validated.
7. Per-item validation in list order (id, kind, title, summary, url type, published, tags; duplicate ids).
8. Compute.

Forbidden keys: casefold, `-` becomes `_`, exact match, no substrings; values are never matched. Classes: SEND {send, approve, approved, approval, approval_token, smtp, token, email_send, sender, smtp_host, smtp_port, smtp_user}; SPEND {pay, purchase, spend, buy, checkout, card_number}; EFFECT {fetch, crawl, scrape, download, publish, post, build, deploy}; NOCREDS {login, password, username, credentials, otp, api_key, access_token, refresh_token, bearer, pass, passwd}. Precedence SEND, SPEND, EFFECT, NOCREDS; within a class the alphabetically first matching key. Reason suffixes are only schema field names or matched table constants, never ids, values or request-derived key text.

## Refusal table
`INTEL_REFUSED_EFFECT:<key>`, `INTEL_REFUSED_SEND:<key>`, `INTEL_REFUSED_SPEND:<key>`, `INTEL_REFUSED_NOCREDS:<key>`, `INTEL_REFUSED_UNKNOWN:<field>` (also `UNKNOWN:kind`), `INTEL_REFUSED_OVERSIZE:<field>`, `INTEL_REFUSED_BAD_TYPE:<field>`, `INTEL_REFUSED_EMPTY:<field>`, and from the shared text helper `INTEL_REFUSED_CONTROL_CHARS:<field>`. The helper's too-long code never surfaces because every cap is checked first.

Text hygiene uses the real shared `policy.clean_text` and `policy.scope`; no adapter, no fallback, and `policy.check` is not called (there is no action path). Characters in categories Cc, Cf, Zl and Zp are refused in every id, title, tag, interest and summary; only the summary keeps `\n`, `\r`, `\t`. Offending values are never echoed.

## Drops (not refusals)
A URL that fails the gate drops the item, counted `url_invalid`: https only (scheme casefolded, ASCII), a hostname, no userinfo, no whitespace and no Cc, Cf, Zl, Zp or Zs character. An item with `published` later than `as_of` is dropped, counted `future_date`. The URL gate runs first, so an item failing both counts once, as `url_invalid`. A surviving URL is kept unchanged. Dropped items are still fully validated and still count for duplicate ids.

## Score (integers only)
`overlap` = number of distinct interests (stripped and casefolded) that match an item. An interest matches when it equals a tag (stripped, casefolded) or appears as a whole-word phrase in the title or summary (casefolded). `recency` = max(0, 30 - age_days), age in days from `published` to `as_of`. `score = 10 * overlap + recency`. Ranking: score descending, then id ascending. Every ranked entry shows `overlap`, `matched_interests`, `age_days`, `recency` and `score`.

Briefs and tickets are emitted for the first `top_n` ranked items with `overlap >= 1`; fewer if fewer qualify, never padded. A brief has `item_id`, `title`, `kind`, `source_url`, `supplied_summary` (unchanged), five fixed template `questions` (what is new, what it enables, risks, what a first prototype would test, what is unknown) and status `TO_RESEARCH`. A ticket has `ticket_id` ("V8-" plus the item id), `title` ("Explore: " plus the item title), `source_item_id`, `source_url`, status `proposed`, `needs_her_review` true.

Output: `ranked`, `briefs`, `tickets`, `counts` {supplied, ranked, dropped_url_invalid, dropped_future_date}, `scope`. Invariant, pinned by a test: supplied = ranked + dropped_url_invalid + dropped_future_date. Deterministic, no clock, no float, no randomness.

## INTERPRETATION CHOICES (not pinned by the spec)
1. `top_n` below 1 (including 0 and bool) gives `BAD_TYPE:top_n`; above 20 gives `OVERSIZE:top_n`.
2. A missing top-level field or item field gives `BAD_TYPE:<field>`; `tags` is required but may be an empty list.
3. Whole-word matching splits text on any run of characters that are not letters or digits, so an underscore is a separator; a multi-word interest matches the same words in order with any separators between them.
4. Tag matching is exact equality after strip and casefold, not substring.
5. Interests are deduplicated after strip and casefold; `matched_interests` lists the casefolded forms, sorted.
6. Blanket fences where the schema declares none: 10010 containers, 32 keys per dict, 64 items per unlisted list, 64 characters per key, 10000 characters per string, depth 8. The field name on a container-budget refusal follows traversal order.
7. The URL gate does not validate port numbers.
8. A string raw cap of 10000 is a fence only; the declared field caps above apply first to the fields they name.

## LIMITS
The score is a toy keyword-overlap plus recency formula. It is not interestingness and not novelty detection. Summaries are not verified, items are supplied and unfetched, briefs are templates, and tickets propose work for review; they do not create or build anything. No claim is made about any item beyond its supplied summary.

## Test and mutation notes
- AST battery over every comparison, boolean operator and bool/int/string constant of the module, run on an isolated copy with the baseline checked first. Pass 1: 382 sites, 380 mutants, 38 survivors; the real ones (depth and container-budget boundaries on each admission path, the URL category names, the exact scope text, the tags and interests count fences) were pinned with new tests and two dead or redundant code paths were removed. Pass 2: 376 sites, 374 mutants, 7 survivors. After the date and kind cap round, the pass was re-run in full: 384 sites, 382 mutants, the same 7 survivors, each argued equivalent:
  1. Three role labels `"other"` -> `"other~"` (container role for unlisted containers): the label is only used as a dictionary lookup that falls back to the default cap, so any unknown label behaves the same.
  2. Two `" "` strings in the whole-word haystack line, exactly these two sites: the separator between title and summary inside the casefold argument (column 55) and the trailing pad (column 91), each -> `" ~"`. The tokenizer splits on non-word characters, so the extra `~` never reaches the joined text at the separator, and the trailing pad still ends with a space, so every phrase boundary is unchanged. The other two `" "` strings on that line (the leading pad and the join separator) are not equivalent: their mutants are killed by the floor. Removing the trailing pad outright would not be equivalent either; only this `" ~"` form is.
  3. `depth + 1 > MAX_DEPTH` -> `>=` and `1` -> `2` on the item-dict admission path: an item dict is always at depth 2 against a limit of 8, so the comparison is never near its boundary.
- A first pass of an earlier unit's battery had a stale `.pyc` problem (same-size mutants reused cached bytecode); the battery program now disables bytecode writing. A battery run whose isolated copy lacks a file read by a doc test is void, because every mutant then dies at baseline; the baseline is checked first.
- Tests were fixed after the first green run where they were wrong, not the code: a helper that replaced a passed None with its default, a tag-count test that reused one size for two different caps, a spy-list test that built its own list through the helper, an oracle that matched the scheme case-sensitively, a ranking expectation that mis-ordered a zero-overlap item, and an underscore expectation that contradicted choice 3.
