# Group 97 deterministic wire preview and reconciliation identifier

Attachment-free immediate pitch descriptor now has pure wire_preview: exact MIME content, wire hash, deterministic RFC Message-ID derived from full descriptor hash and sending domain. Gmail sender uses these exact bytes only after existing durable exact M00 gate/claim. Successful provider receipt retains RFC Message-ID and wire hash. Preview is explicitly not authority and never sends, consumes approval or creates receipt. Repeated preview yields same bytes, actual HTTP fixture inspected MIME fields. 187 pitch/M00 tests pass.

No live send or production destination verification reproduced. RFC Message-ID is not idempotency or evidence of delivery; ambiguity retains blocked started/dispatching claim, never retry automatically. Provider lookup/reconciliation remains host responsibility. No manuscript attachment support, external destination verification or production submission. Broad group remains PARTIAL.
