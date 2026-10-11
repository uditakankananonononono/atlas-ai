# INSTINCT P253|L200 - Repository Links/Paths Register

## Source

Verbatim source line (only pinned text for this unit):

```
Output: Repository links/paths,
```

Everything beyond that line is an interpretation choice; the invented shapes are
listed in the last section so a later pinned specification can diff against them.

## Position

Output-format unit, sibling of P252 (progress log), P255, P256, P262 (blockers
register). Pure stdlib, pure function, deterministic output artifact. It composes
with the shared report-schema conventions: same field names, create/append/render
triplet, `bad_type` on bools, `UNVERIFIED` marking.

## Boundary

The register RECORDS caller-supplied repository links/paths per project. It never
resolves a link, never fetches content, never reads a filesystem. Recording is not
proof that any repository exists, is hosted, or belongs to the project. Every
recorded row carries `verification: "UNVERIFIED"`, `resolved: False`,
`fetched: False`, and the report carries the same offline flags.

## API

- `create_register() -> RepoRegister` - empty register.
- `add_entry(register, entry) -> RepoRegister` - validate + dedup + cap, return a
  new immutable register. Raises `ValueError` with a `P253:` refusal code.
- `entries(register, project_id=None) -> list` - sorted row dicts, UNVERIFIED-
  marked. A query, never refuses; an unknown project yields `[]`.
- `render(register) -> str` - deterministic text section. Empty register renders
  `""`.
- `report(register) -> dict` - `{items, counts, status, open_verification,
  resolution_performed, fetch_performed, evidence_verified, boundary}`.
  `status` is always `"declared_input_register_only"`.

## Entry fields (all required, all nonblank text)

| field        | max length | meaning                                        |
|--------------|-----------|------------------------------------------------|
| `id`         | 64        | caller-supplied entry id, unique in the register |
| `project_id` | 64        | owning project id                              |
| `kind`       | -         | `"link"` or `"path"`                           |
| `value`      | 512       | the link URL or repository-relative path       |
| `source_ref` | 128       | where the value was declared                   |

## Validation

- A `link` value must be an `https` URL with a host, no credentials, no query,
  no fragment, no whitespace in the authority, and a valid numeric port if one
  is present (P77 `_valid_url` semantics).
- A `path` value must be a contained relative path: no leading `/`, no `\`,
  and no empty, `.` or `..` parts.

## Deduplication

- `id` must be unique across the register.
- `(project_id, kind, normalized_value)` must be unique. The same value under a
  different project or a different kind is allowed.
- Link normalization: scheme and host lowercased, trailing `/` stripped, a
  trailing `.git` suffix stripped. Path case stays significant: `/X/y` and
  `/x/y` are different repositories.
- `duplicate_entry` names the id of the existing entry.

## Refusal codes (ValueError, `P253:` prefix)

- `P253:bad_type:register` - add/entries/render/report given a non-register.
- `P253:bad_type:entry` - entry is not a dict (bool check first).
- `P253:bad_type:<name>` - a field is not a string; bools are not strings.
- `P253:unknown_fields:entry` - entry has a key outside FIELDS.
- `P253:empty_field:<name>` - a required field missing or blank (checked before
  kind membership and shape, so `kind=""` refuses `empty_field:kind`).
- `P253:text_too_long:<name>` - a field exceeds its limit; the limit itself passes.
- `P253:bad_kind:<value>` - kind not in `("link", "path")`.
- `P253:bad_link:<value>` - value fails link validation.
- `P253:bad_path:<value>` - value fails path validation.
- `P253:duplicate_id:<id>` - id already recorded.
- `P253:duplicate_entry:<existing_id>` - normalized (project, kind, value) already recorded.
- `P253:limit_exceeded:entries` - register already holds MAX_ENTRIES.

## Order of checks

1. register type
2. entry type (dict, non-bool)
3. unknown fields
4. field presence
5. field types (bool is not a string)
6. blank
7. length
8. kind membership
9. link/path shape
10. duplicate id
11. duplicate normalized entry
12. capacity

## Limits

- `MAX_ENTRIES = 4096` per register.
- Field length limits as tabulated above.

## Interpretation choices (invented shapes)

The pinned line names only the output ("Repository links/paths"). The following
were invented in the family STRANGLER/BDD/DEBT shape and are tagged here so a
later pin can supersede them:

- FIELDS = `(id, project_id, kind, value, source_ref)`; KINDS = `(link, path)`.
- Field length limits (64/64/512/128) and `MAX_ENTRIES = 4096`.
- Link = https-only, credential-free, no query/fragment, valid port (mirrors P77).
- Link normalization (lower scheme/host, strip trailing `/` and `.git`); path
  case significant.
- Dedup scope `(project_id, kind, normalized_value)`; `duplicate_entry` names
  the existing id.
- Render format `project <id> (<n> entries)` header rows then
  `<kind> <value> [<source_ref>]` rows, grouped by project, sorted
  (kind, normalized, id).
- `report()` keys: `status="declared_input_register_only"`, counts
  `{entries, projects, links, paths}`, offline flags, `open_verification`,
  boundary text.
- Exact refusal-code strings and the order of checks above.
