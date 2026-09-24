# M10 trusted timestamps for reviewer attestations

## Problem
Retiring a reviewer key must stop it from verifying new signatures. But a
decision the reviewer really signed while the key was valid should keep
verifying afterwards. An Ed25519 signature carries no trustworthy time, so
Atlas needs an outside party to vouch for when each attestation existed.

## How it works
1. `POST /api/v1/email-assistant/promise-state-reconciliation/evidence/verify`
   verifies each attestation against the reviewer's active registry key. Each
   attestation that verifies is then sent (as a SHA-256 digest only, nothing
   else leaves Atlas) to an RFC 3161 time-stamp authority. The signed token is
   checked before it is stored in `m10_attestation_timestamps`. The response
   lists the result under `timestamps`. If the TSA is down, verification still
   succeeds and the entry says `timestamped: false`.
2. Retiring or rotating a key sets `signatures_valid_before` on the key row:
   - rotation or ordinary retirement: the retirement time;
   - `compromised: true` with `compromised_since`: that time (never earlier
     than key enrollment, never later than now);
   - `compromised: true` with no time: the enrollment time, so no earlier
     signature is trusted. Declaring compromise later can only move the
     cutoff earlier.
3. Later verification of an attestation made with a retired key passes only if
   a stored token re-verifies cryptographically and its genTime is strictly
   before the cutoff. The reviewer entry then shows
   `verified_via: timestamp-before-retirement`, the proven `timestamp`, the
   `timestamp_authority` and `key_valid_before`. Otherwise the request fails
   with 422. Signatures from a retired key are never newly timestamped.

Stored tokens are never trusted as rows. Each check re-runs: message imprint
equals the attestation digest, CMS signed attributes (content type, message
digest, ESS signing-certificate hash), the TSA signature, TSA certificate
chains to the pinned CA, critical timeStamping EKU, genTime inside the
certificate's validity. The live client also checks the request nonce, so a
replayed old response is refused.

## Default authority: FreeTSA (free)
- Endpoint `https://freetsa.org/tsr`, documented at https://www.freetsa.org/index_en.php.
  No account, no key, no cost.
- Pinned files in `tsa/`: `freetsa_cacert.pem` SHA-256
  `2151b61137ffa86bf664691ba67e7da0b19f98c758e3d228d5d8ebf27e044438` and
  `freetsa_tsa.crt` SHA-256
  `8bfb0305bb64e2571ca507552ef3245cb1c2fee8728e0ff8689225081ea13467`
  (both match the hashes FreeTSA publishes; a test pins them).
- Verification is fully offline once the token is stored.

## Trust model
What a passing check proves: the holder of FreeTSA's TSA key (chained to the
pinned FreeTSA root) signed a statement that this exact attestation digest
existed at genTime.

You are trusting:
- FreeTSA's key custody and clock. FreeTSA is a free service run by an
  individual operator, not an audited qualified TSA. If its key leaked, an
  attacker could backdate tokens. For stronger assurance, point Atlas at any
  other RFC 3161 TSA (for example a commercial or eIDAS-qualified one, which
  may cost money) with `ATLAS_M10_TSA_URL` and `ATLAS_M10_TSA_CA_FILE`. That is
  optional config, never the default.
- The pinned CA file in the repo. Changing it changes whom you trust, so it is
  hash-pinned in a test.
- The key registry's `signatures_valid_before`. An atlas-admin who can edit the
  database can move a cutoff; the key event log records governed changes.

You are not trusting: the Atlas database row for a timestamp, the Atlas server
clock (for rfc3161), or anything the caller submits.

Not covered: FreeTSA certificate revocation is not checked online (no CRL/OCSP
fetch), and the TSA certificate expires in 2040, after which new tokens need a
new pinned certificate. Tokens made before then keep verifying because the
check uses genTime against the certificate validity.

## Local fallback (`atlas-local`), off by default for trust
`ATLAS_M10_TIMESTAMP_SCHEME=atlas-local` with `ATLAS_M10_LOCAL_TSA_SEED`
(base64 32-byte Ed25519 seed) signs timestamp records with a per-deployment
key. This works with no network, but it only proves what the Atlas server
said, and anyone who controls that server can backdate. So these records are
ignored for retired-key verification unless `ATLAS_M10_TRUST_LOCAL_TIMESTAMPS=1`.
`ATLAS_M10_TIMESTAMP_SCHEME=off` disables stamping (the test suite uses this so
it never reaches a public TSA).

## Rejected: OpenTimestamps
Its public calendars are free (https://opentimestamps.org/), but a proof stays
"pending" until a Bitcoin block confirms it, which takes hours. Verifying a
completed proof needs a local Bitcoin Core node
(https://github.com/opentimestamps/opentimestamps-client). A free deployment
does not have one, so the proof could not be checked without trusting a
third-party block explorer, which is weaker than RFC 3161's direct signature.
