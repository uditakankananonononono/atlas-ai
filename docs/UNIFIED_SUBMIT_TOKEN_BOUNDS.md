# Unified v3 submit token: what is and is not proven (WIP-UNREVIEWED)

Proven by tests in this branch: v3 canonical-JSON claims (approval, capture, selector, values digest, reviewed
preview digest, device, session, expiry, action, version 3). Real M18 (pipe format) and postclick (v2 JSON) tokens
are refused. Order: verify, durable ledger reserve, consumed store, pace, re-verify, M18 click. Real SIGKILL of a
separate process after the reserve, and during the atomic store write, leaves a restart refusing (fails closed).

Bounds, not claimed away:
- URL redaction (`redact_urls`) is PATTERN and HEURISTIC based. It strips query/fragment/userinfo/matrix params for
  http(s), ws(s), ftp(s), handles encoded and escaped URLs, bare secret-named key=value and Bearer/Basic, and path
  segments after reset/verify/confirm/... or long mixed/hex segments. A secret in an ordinary-looking path
  segment survives (an xfail test documents it). It is not a general token-removal guarantee.
- SIGKILL tests do not prove power-loss or filesystem fsync behaviour.
- Daemon ordering tests use a counted fake click (labeled); the real M18 click is proven on real Chromium in the
  postclick_status and paired websocket tests.
