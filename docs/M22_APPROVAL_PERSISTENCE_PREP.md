# ATLAS-3 M22 approval persistence strengthening

Builder AUTHORED-NOT-RUN; prior submission rejected, repaired head awaiting
peer recheck. Base `94fba3f76ae55d02163577921b4fd85f82a548c5`.
Test-only exception: strengthen the existing
`tests/modules/test_m22_tools_hub.py` node
`test_discovery_filters_and_install_is_approval_gated`; no product changes.
All existing assertions and synthetic secret-redaction input remain verbatim.

## Source-grounded fixture and exact scope

The assignment mentioned `tests/conftest.py isolated_m22_approvals`; that file
has no such fixture at this base. The actual fixture is
`tests/modules/conftest.py:146`, delegating to `isolated_m00_approvals` at line
131. Coordinator approved using this actual location at the same pinned base.
It creates `sqlite:///{tmp_path / "m00-approvals.sqlite3"}`, creates the real
M00 request/event tables, supplies a sessionmaker with expire_on_commit=False,
and monkeypatches M00's default service. No production database is involved.

The strengthened node takes the SAME pytest tmp_path used by this fixture,
asserts its disk DB exists, opens a separate engine at that exact path, and
uses an ORM Session, not a Connection, for ORM entity selects. It selects the
request by the proposal's exact approval ID, never counts unrelated requests.
The event query is restricted to that exact persisted request's ID and must
return exactly one event: created, actor None, timestamp equal to created_at.

For the existing Collector's SafeTool and the unchanged proposal arguments,
assert request ID, integrate_tool action, module 22, user default, pending status,
no decision/approver/expiry, and complete payload equality. Payload fixes the
candidate name/URL, api adapter, region-only preview, read scope, exact rollback
plan and score 0.7833 (0.8*0.30 + 0.9*0.25 + 0.9*0.20 + 0.7*0.15 + (1/3)*0.10
= 0.78333..., rounded to four decimals). Candidate ID comes from this exact discovered item.
No broad claim that discovery can never create approvals is made.
The proposed install remains absent from installed/portfolio before review.
This checks pre-review state, not behavior after an approval or actual installer
execution. It tests the legacy Service.propose_install/facade path, not every
pipeline route, policy branch, tenant context, failure recovery or backend.

## Peer audit attribution and current status

The peer coordinator reported independent execution on prior submission
`7221bfbc8304af97b506637b5a4ae54b6d4f11da`, tree
`0ec7da1c496fbc8e8921b28233131751ec9843d0`: REJECTED AS SUBMITTED for the
wrong fixed score 0.7817, not an environment failure. With 0.7833 substituted
in its diagnostic tree, the peer reported whole M22 111 PASS / 1 SKIP / zero
regression; exact ORM request/payload and created event/timestamp/actor held.
Created-event suppression killed the strengthened node while the original node
at the pinned base PASSED against that mutation.
Request-write suppression failed FACADE-FIRST at the preserved `list()[0]`
with IndexError, not at the new ORM guard. This is not evidence that the added
ORM request assertion killed that mutation.

These are attributed peer diagnostic-substitution results, not executions by
the builder and not a PASS for this repaired head. This delta corrects both
score literals and records that provenance. Repaired head awaits peer recheck.

## Planned commands, NOT executed by builder

Run only on the integrating side in clean, disposable worktrees with the
repository's prepared Python dependencies and `PYTHONPATH=backend`. Do not
mutate product files in a shared/production checkout. Example exact isolated
workflow from a checkout containing this prep branch and base:

```sh
git worktree add --detach /tmp/atlas3-m22-healthy prep/atlas-3-m22-approval-persistence
cd /tmp/atlas3-m22-healthy
PYTHONPATH=backend python3 -m pytest -q tests/modules/test_m22*.py
PYTHONPATH=backend python3 -m pytest -q tests/modules/test_m22_tools_hub.py::test_discovery_filters_and_install_is_approval_gated
```

Both must pass on the repaired head. Only the peer diagnostic-substitution
results above are available; builder executed neither command.
For event mutation create a separate disposable worktree and suppress ONLY
M00 submit's exact created-event add line. At the pinned source this is line
218, not the other policy/idempotency branch's event write. The mutation script
below is a planned operation, not something executed in this prep:

```sh
git worktree add --detach /tmp/atlas3-m22-no-event prep/atlas-3-m22-approval-persistence
cd /tmp/atlas3-m22-no-event
python3 - <<'PY'
from pathlib import Path
p = Path('backend/app/modules/m00_approval_center/service.py')
s = p.read_text()
needle = '            db.add(ApprovalEventRow(approval_id=row.id, event="created", actor=None, at=now))\n'
assert s.count(needle) == 1
p.write_text(s.replace(needle, '            # audit mutation: created event intentionally suppressed\n'))
PY
PYTHONPATH=backend python3 -m pytest -q tests/modules/test_m22_tools_hub.py::test_discovery_filters_and_install_is_approval_gated
# EXPECT FAIL at exact event cardinality. Now test original node against SAME mutation:
git show 94fba3f76ae55d02163577921b4fd85f82a548c5:tests/modules/test_m22_tools_hub.py > tests/modules/test_m22_tools_hub.py
PYTHONPATH=backend python3 -m pytest -q tests/modules/test_m22_tools_hub.py::test_discovery_filters_and_install_is_approval_gated
# EXPECT PASS. Do not count an unrelated failure as evidence.
```

For independent request-write mutation:

```sh
git worktree add --detach /tmp/atlas3-m22-no-request prep/atlas-3-m22-approval-persistence
cd /tmp/atlas3-m22-no-request
python3 - <<'PY'
from pathlib import Path
p = Path('backend/app/modules/m00_approval_center/service.py')
s = p.read_text()
needle = '            db.add(row)\n'
assert s.count(needle) == 1
p.write_text(s.replace(needle, '            # audit mutation: request write intentionally suppressed\n'))
PY
PYTHONPATH=backend python3 -m pytest -q tests/modules/test_m22_tools_hub.py::test_discovery_filters_and_install_is_approval_gated
# EXPECT FAIL FACADE-FIRST at preserved list()[0] IndexError, as peer diagnosed.
# This mutation does not establish failure at the newly added ORM guard.
```

Inspect tracebacks and record healthy results, mutation failure sites and old-node
pass before independent acceptance. Preserve all original assertions throughout
strengthening; the old-node comparison is only in the disposable mutation tree.
No product mutation, pytest, collection, runtime import or database call was
executed by the author. Static AST parsing and git diff checks are separate from
execution evidence. One strengthened async test function, one case; no parameters
or new test functions. Incremental delivery bundle requires the exact pinned
base above. No other branch source is overlaid. Builder remains NOT RUN; the
prior submitted tree was rejected; repaired head 935a6d4cf9e8b7d03d10cb4b265e86b112b08c40 was independently verified by the peer's auditor on 2026-10-10: whole M22 111 PASS / 1 SKIP; created-event suppression killed the NEW node while the old node passed, and request-write suppression failed FACADE-FIRST at list()[0]. Builder remains NOT RUN; landed at af96c787 per the peer's coordinator's confirmation (short ID supplied by peer, full SHA/URL not available to builder). Earlier awaiting-recheck wording records the pre-audit status, superseded by this receipt.
