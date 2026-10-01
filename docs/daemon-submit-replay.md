# Paired-PC submit replay repair

Status: candidate, independently unaudited. No real submits exercised.

## Behavior and identity

The effect key is `(device_id, approval_id)`, not the transport command ID,
selector or token. Re-minting an approval with a different expiry, changing
command IDs or reconnecting cannot reserve that same approval again.

Tokens use canonical JSON HMAC-SHA256 and include the device, exact local
session, `click_submit` action, approval, capture hash, selector, values digest
and absolute Unix expiry. Atlas mints a 120-second expiry. Verification runs
before reservation, after pacing and immediately before the locator click.
Legacy unbound tokens are rejected. Upgrade server and daemon together.

SQLite uses a primary key and `BEGIN IMMEDIATE`, with synchronous FULL commits.
The insert commits before pacing, page lookup or browser effect. Independent
connections/processes compete for the same persistent database. Any reserved
approval is denied forever, including after cancellation, an exception, an
uncertain click or a process restart. A completed state is diagnostic only;
reserved and completed both prohibit replay. Storage failure denies the click.

The database defaults to `submit-effects.sqlite3` next to the device key.
An explicit `effect_ledger_path` is supported. All processes using one device
must use the same local persistent path. Preserve it with the device key.
Deleting it, restoring an old backup or configuring different paths loses
replay protection. A crash between commit and click can prevent a click that
never happened. Do not retry uncertain approvals: reconcile the website state
with the owner. There is no claim of exactly-once delivery, distributed storage
safety or protection against a compromised device/command-secret holder.
Reservations are not garbage-collected.

CLICK_NAV retains its distinct, separately granted capability. It is not given
submit reservation or token semantics by this change. Existing classification
of navigation versus submit is a separate trust boundary, not newly proven by
these tests.

## Reproduction

Python 3.12; `PYTHONPATH=backend python scripts/verification/daemon_replay_probe.py`
uses only a fake browser. At main 313309be2a960a84b909d1834c3046f884e21a7e,
serial, concurrent, reconstructed daemon and changed-command-ID each return
`[True, True]` with two fake clicks. On the candidate each returns
`[True, False]` with one fake click.

`python -m pytest tests/modules/test_m13* -q` exercises the relevant full M13
suite, including existing capture-bound happy paths and adversarial replay,
tampering, expiry, cancellation, unknown outcomes, storage failure and
cross-process atomic reservation tests. Tests are bounded local proof only,
not a live website or production/scale claim.
