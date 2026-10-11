# Row 90 - Credible Threat Construction (CREDIB90)

Ledger source pin: `audits/additional-2000-features.json`, row id 90.
Verbatim requirement: "Credible Threat Construction".
Verbatim description: "Makes threats believable".
Ledger status: PARTIAL.

## Delta against the existing mechanism
Existing: `backend/app/modules/m20_general_cognitive_worker/negotiation_behavior_0085_0109.py:203`
(`_credible_threat`): heuristic float `credibility_score` (mean of three
booleans) plus an arbitrary `confidence` number.

This unit's delta, and only this:
1. No score and no confidence number: the gate is the exact conjunction of
   the three declared conditions with per-condition echo and deterministically
   sorted `blocked_reasons`.
2. A declared `basis` list is validated exactly (entries non-blank unique
   strings, at most 32) and counted.
3. Harm-intent request keys (`harm`, `injure`, `coerce`, `punish`,
   `retaliate`, `violence`) are refused with `CREDIB90:HARM_REQUEST:<key>`,
   turning the landed unit's prose limit into an enforced guard.
4. The unit never drafts or improves threat wording: output carries
   `wording: human_authored_required`.

It does not edit, wrap, or replace the landed mechanism.

## Interface
`run(request: dict) -> dict` in
`backend/app/modules/m20_general_cognitive_worker/credible_threat_construction90.py`.
Stdlib only; pure, offline, deterministic (blocked reasons sorted;
byte-stable JSON with sort_keys).

Input keys: `consequence` (required string) and `basis` (optional list of
unique strings, <= 32), each string raw-length-capped at 500 chars FIRST,
never stripped, normalized or sanitized, and refused if it is blank under
the existing whitespace policy or carries any control, separator or format
character - no Unicode Cc, Cf, Zl or Zp characters (DEL is inside Cc);
Zs (NBSP, U+2000-200A, U+3000) accepted. The earlier
description of the echo as merely "non-blank string <= 500 chars" is
removed; echoed strings are exactly what the caller supplied or the request
is refused. `lawful` / `proportionate` / `authorized` are required booleans.

Output keys exactly: `declared_consequence`, `conditions`, `gate`
(`pass` | `blocked`), `blocked_reasons`, `basis_count`, `wording`, `limits`.

## Refusal codes (ValueError, prefix CREDIB90:)
- `BAD_TYPE:request`, `UNKNOWN_KEY:'<key>'`, `HARM_REQUEST:<key>`
- `MISSING:consequence`, `BAD_TYPE:consequence`, `EMPTY:consequence`,
  `OVERSIZE:consequence`
- `BAD_TYPE:lawful` / `BAD_TYPE:proportionate` / `BAD_TYPE:authorized`
- `BAD_TYPE:basis`, `BAD_TYPE:basis_entry`, `DUPLICATE:basis`, `OVERSIZE:basis`
- `UNCLEAN:consequence`, `UNCLEAN:basis_entry`, `OVERSIZE:basis_entry`
  (codes name the field only; no value or character is echoed)

## Limits
- Conditions are self-attested; legality, proportionality and authority are
  not verified against any law or contract.
- The gate records a declared conjunction only; it is not a judgement that
  any consequence is credible, effective or advisable.
- No threat text is drafted, improved, routed or delivered; wording remains
  human-authored and human-reviewed.
- Harm-intent requests are refused.
- Caller-echoed strings are refused, never repaired, when they carry
  control, separator or format characters (no Unicode Cc, Cf, Zl or Zp
  characters); the audit produces no sanitized copy.
