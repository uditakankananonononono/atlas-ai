# Row 704 API Documentation: mounted runtime repair

Source: https://docs.google.com/document/d/1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY/edit

Existing openapi704.py validates supplied descriptions and intentionally does not
inspect runtime endpoints. This additive path uses FastAPI's actual mounted
route objects and its native OpenAPI generator, preserving nested prefixes,
parameters, request/response model schemas and security declarations. It builds a
fresh schema instead of trusting the app's stale schema cache. Duplicate mounted
HTTP method/path pairs, duplicate operation IDs and operation-set mismatches fail
closed. Hidden routes, mounts and websockets are named as undocumented or unsupported.

Authenticated endpoints under the existing M20 /api-documentation router:
GET /mounted returns document, canonical bytes hash, endpoint trace and limits.
GET /mounted/download returns an attachment-ready JSON response with private,
no-store caching. No handlers are called and no external network is used.

SCOPED: fixture apps reproduce mounted-schema export, freshness, duplicate refusal,
hidden route accounting and 401 authentication. This does not prove endpoint
behavior, security enforcement beyond tested auth gates, response conformance,
live deployment, complete subapplication coverage or documentation quality.
Production full-app export and independent review remain required. Newer FastAPI
versions use iter_route_contexts for effective included-router prefixes; older
versions use flattened APIRoutes. No custom app.openapi modifications are applied,
because those are not part of the actual native mounted route declarations.
