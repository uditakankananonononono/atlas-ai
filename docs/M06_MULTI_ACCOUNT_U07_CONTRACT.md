# M06 U07 multi-account manager (oneofficial variant) - contract

Oneofficial variant: exactly one official account per platform, hard
enforced in code. Accounts must be the owner's own. There is no
automation-labeled account kind in this variant.

## What this unit does

- Validates and normalizes owner account records: platform allowlist
  (instagram, tiktok, twitter, linkedin), handle grammar, persona with a
  required display name, and a source reference.
- Keeps a fleet of accounts as plain dict data (`new_fleet`,
  `add_account`), enforcing one account per platform and unique ids.
- Plans a per-account content calendar whose entries stay drafts.
- Records supplied per-day metrics and summarizes them with an exact
  rational engagement rate.
- Plans the free sign-up steps for a platform, with hard stops at
  CAPTCHA, phone, ID, and payment gates. It executes nothing.
- Turns a publish intent into an m00-style approval request
  (`status: awaiting_human_approval`, `executes: false`). Content must be
  original or carry a credit source; altered reposts of other people's
  content refuse.

## What this unit never does

It never creates accounts, signs up, autofills portals, sends, submits,
or posts. Every publish intent waits for human approval. It holds no
keys and fetches nothing; analytics summarize only metrics supplied to
it.

## INTERPRETATION

"one official account per platform, owned by the owner; every publish is
an approval request, never an execution"

## LIMITS

Embedded verbatim in every returned account record under `limits`.

## Variant

This variant has no automation-labeled ownership kind: `OWNERSHIP_KINDS`
is `("owner",)` and any other ownership value refuses. The fleet enforces
one official account per platform and unique ids. Persona rules, calendar,
metrics, sign-up plan and approval-request publish are as described above.

## Checks that run (all refusals are `ValueError` prefixed `ACCTU07:`)

- Text patterns are matched whole-string (`fullmatch`), so a trailing
  newline after a handle, account id or date is refused.
- `account_id`: 1-40 characters of `[A-Za-z0-9_-]`. `handle`: first
  character `[A-Za-z0-9]`, then up to 29 of `[A-Za-z0-9._-]` (30 total).
  Dates: ASCII `YYYY-MM-DD` and a real calendar day.
- Persona `display_name` must be non-blank; `display_name`, `bio` and
  `voice` are at most 500 characters; a truthy `claims_real_person`
  refuses. `source_ref` is non-blank, at most 200 characters.
- Calendar: 1 to 92 entries, each with `date`, `title`, `theme`, `format`;
  the three text fields are non-blank and at most 200 characters.
- Metrics: `followers`, `impressions`, `engagements` are exact
  non-negative integers (booleans and floats refuse). `summarize_metrics`
  runs every supplied record through the same key, date, integer and
  account checks as `record_metrics`; a record that fails any of them
  refuses, so no raw `KeyError` or `TypeError` escapes. The engagement
  rate is an exact fraction string (`"2"` when the denominator reduces to
  one, `"1/20"` otherwise, `null` when impressions total zero).
- Fleet: `add_account` accepts a dict with only an `accounts` list of
  account records (each with a string `account_id` and a known platform);
  anything else refuses. The input fleet is never modified.
- Publish intent: text is non-blank and at most 5000 characters.
  INTERPRETATION CHOICE: origin `original` must not carry a
  `credit_source`; origin `credited` must carry a non-blank string
  `credit_source` of at most 200 characters (the same cap as
  `source_ref`); `altered_repost` and any other origin refuse. The text
  and `credit_source` are echoed unchanged.

## What is refused

- Anything that is not an exact record of the documented shape: unknown
  keys, wrong types, missing fields, and text that does not match its
  pattern as a whole string (a trailing newline after a handle, account id
  or date refuses).
- Metrics and summary records that are not exact non-negative integers,
  that carry a bad or impossible date, or that belong to another account.
  `summarize_metrics` applies the same checks to every record as
  `record_metrics`.
- A fleet that is not a dict holding only an `accounts` list, and a fleet
  entry that is not an account record with a string `account_id` and a
  known platform. The fleet passed in is never modified.
- Any ownership other than the owner, a second account on a platform, a
  duplicate account id, and a persona that claims to be a real person.
- Any content origin other than `original` or `credited`.

## Credit rule (interpretation choice)

Origin `original` must not carry a `credit_source`. Origin `credited` must
carry a non-blank string `credit_source` of at most 200 characters (the
same cap as `source_ref`). The text and the credit are echoed unchanged,
and the credit is a label, not a verified citation.

## Fleet-entry minimum shape (interpretation choice)

Entries already in a fleet are checked only for what `add_account` reads:
a string `account_id` and a platform from the allowlist. Their other
fields are not re-validated.

## Limits of this unit's checks

- Metrics, dates, handles and credits are checked for shape only. Nothing
  is fetched, so a handle may not exist and a credit source may not be
  real; the credit text is a label, not a verified citation.
- A fleet passed in is trusted only for the fields read here; its records
  are not re-validated beyond an account id and a known platform.
- Two summary records with the same latest date use the first one listed
  for `followers_latest`.
- Control and format characters are not scanned in text fields; the unit
  bounds length but does not sanitize content. Echoed fields are capped.
- Interpretation choices: the credit rule above, the 200-character credit
  cap, and the fleet-entry minimum shape.

## Errors

All refusals are `ValueError` prefixed `ACCTU07:`.
