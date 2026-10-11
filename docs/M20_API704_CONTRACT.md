# API704-SCHEMA-01: bounded OpenAPI 3.1 subset generator

Targets row704 "API Documentation" (extra-doc category 5, "Describes interfaces";
ledger status PARTIAL) for SCOPED acceptance only. Not full title closure.
The existing `software_practice_685_709._api` only echoes operations and lists
missing fields; this unit adds a typed, validated, machine-readable document.

Function: `openapi704.generate_openapi(data) -> dict` (pure stdlib, raises
ValueError -> 422 when wired). No route is mounted by this unit; wiring is a
separate patch owned by the integrator.

## Input
`info{title,version,description?}`, `schemas{Name:{source_ref,schema}}`,
`operations[{operation_id,method,path,summary,source_ref,parameters?,request_body?,responses}]`.
Unknown keys refuse. `source_ref` is required (non-blank) on every operation and
named schema.

Schema subset: `string|integer|number|boolean|array|object`, `nullable`, `enum`
(scalars), `minLength/maxLength`, `minimum/maximum`, `items`, `properties`,
`required`, boolean `additionalProperties` (default false), `description`, and
standalone `$ref: #/components/schemas/Name`. Everything else (oneOf/anyOf/allOf/
not, patternProperties, format, `$defs`, discriminator, schema-valued
additionalProperties, type lists, `null` type) refuses. Recursive or mutually
recursive refs refuse.

## Output
`openapi` (OpenAPI 3.1.0 doc; nullable becomes `type:[t,"null"]`, `required`
stays separate and sorted), `canonical_json` (sorted keys, compact, ASCII,
no NaN), `sha256` of it, `source_trace` (sorted by source_ref/kind/name),
`client_examples` (each parameter/request/response example with `valid:true`),
`implementation_verified:false`, `limits`. Operations and schemas carry
`x-source-ref`. Output ordering does not depend on input ordering.

## Gates enforced
- path placeholders == declared path parameters (required:true, no duplicates, no empty braces)
- duplicate method+path (placeholder names normalized), equivalent templates with different placeholder names, duplicate operationId, duplicate parameter
- dangling or non-local `$ref`, ref-with-siblings, recursive refs
- required must name known properties without duplicates; nullable is independent of required
- examples validated by an explicit bounded validator (bool is not integer, integer is a number, finite only, enum, lengths, bounds, no unknown properties); example without schema refuses
- GET/DELETE with a body refuse; request bodies must be object schemas
- roundtrip `json.loads(canonical_json) == openapi`

## Bounds (N accepted, N+1 refused)
operations 64, schemas 64, properties/object 64, container depth 8, parameters/op 16,
responses/op 8, enum 32, text 500 chars, path 200 chars, example nodes 1000,
example string 2000, input 262144 bytes / 50000 nodes / depth 48 (iterative
prescan, so hostile nesting cannot hit the recursion limit), integers 64-bit,
output 1,000,000 bytes. Non-finite numbers and boolean-as-number refuse.

## Limits (residual)
Documents only what the caller supplies. It does not read, import or execute the
implementation, so it cannot show the doc matches live routes; a passing result
is not evidence of live conformance. No security schemes, servers, non-JSON
media types, format validation, or recursive/complex schemas. Examples are
caller-supplied, not observed traffic. No persistence, model, network, spend or
deployment. Ledger, STATUS and row857/858/859 paths untouched.

## Mounted integrator boundary
An additive authenticated `/api-documentation/openapi` endpoint binds tenant and
actor, checks up to64 declared resource-reference metadata objects and retrieves
no resources. Owner/actor IDs are returned alongside the unchanged core receipt.
The raw JSON guard reused from the landed LEGACY694 boundary checks all parsed
string keys/values for UTF-8 surrogates and refuses nodes deeper than64. Mounted
pins cover401, two authenticated owners200, mismatched tenant/actor/reference403,
invalid generator input422, surrogate type-error/data/key shapes422. No live API
conformance or external source verification is added. Core is byte-frozen at R3.
The supplied unauthenticated wiring patch is not applied unchanged; this owner
boundary is a separate integration requiring independent review.
