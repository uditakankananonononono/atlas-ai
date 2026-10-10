# Claire M21 event-persistence test assertions (prep-only, NOT RUN)

Status: tests and contract only, no product code, no wiring, no push. The
strengthened tests were authored without execution (no pytest, no runner,
no application import); the integrating side runs them.

Base: atlas-ai main at 33e6510a19a685d29d7e3aa266f245f0c21491d9.

Change: `tests/modules/test_m21_claire.py` gains persistence assertions in
three existing tests, plus one test-local helper `_persisted_m00_rows` that
reads `ApprovalRequestRow`/`ApprovalEventRow` directly from the per-test
SQLite file the `isolated_m00_approvals` fixture writes
(`tmp_path/"m00-approvals.sqlite3"`). All pre-existing assertions are kept
verbatim; the change only adds assertions. Because the assertions count rows
in the real tables, each test now fails if Module 0 stops writing `created`
audit events (or stops persisting request rows), not merely if the returned
status object looks pending.

Grounding (read from this base, not run):
- `Service.request_environment_change` (m21_claire/service.py) funnels through
  `app.core.approvals.ApprovalStore.put` into `m00_approval_center.Service.submit`,
  which in one transaction writes one `ApprovalRequestRow` (status "pending",
  module_id 21, action_type `claire:<operation>`) and one
  `ApprovalEventRow(approval_id=row.id, event="created", actor=None, at=now)`.
- For these three tests' inputs the fake `Model` plans a single read-risk
  step, so `realize` submits no approvals and the exact totals are the peer's
  probe counts: 1 request/event in
  `test_claire_is_sandboxed_bounded_and_transparent`, 2 in
  `test_claire_sends_and_spend_are_per_action_approval`, 11 in
  `test_claire_optional_pc_endpoint_has_full_owner_machine_capability_parity`.

Assertions added per test: exact request/event row totals; request row id,
module_id==21, action_type, status=="pending"; every event has event=="created"
and its approval_id matches a persisted request row created by the test
(and the first test also asserts the event timestamp is present).

Unresolved / deliberate non-assertions:
- Exact 1/2/11 totals are scoped ONLY to these isolated read-only test
  inputs. M20's `DeliberativeLoop` (legacy_service.py) can submit
  `cognitive:step` approvals for risk-gated steps in general, so the totals
  are not a general "no other writer" property of realize/intake; unverified
  by execution.
- The helper couples to the fixture's database filename
  "m00-approvals.sqlite3"; a conftest rename would fail these tests loudly.
- `ApprovalEventRow.actor` is None for `created` rows in current M00 code but
  is deliberately not asserted, so a future populated actor does not break
  the contract; `user_id` ("default" via the facade) is likewise unasserted.
- Behavior on PostgreSQL or any non-SQLite backend is out of scope; the
  fixture is SQLite-only.
