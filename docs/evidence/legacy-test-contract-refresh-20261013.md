# Legacy test contract refresh

Cutover: dec4c06db343b71a2dd8a58b213c48ed4aadc8f2, documented in
`docs/evidence/nine-scoped-refusals-20261012.md`. Public pairing, local manager
fill/click and legacy Stripe primitives refuse before effects. No production
refusal is removed by this test update.

- Ten previous pairing token/401/403 cases now pin public refusal with zero
  HTTP and no key/config writes. There is no bound-client pairing replacement.
  Token flag/env precedence, blank flag fallback and 401/403 CLI transport
  behavior are currently untested. Registry CAS tests do not cover that gap.
- `test_second_invoice_step_reports_accepted_item[http,json]` maps to durable
  `test_m24_invoice_dispatcher.py::test_step_accepted_timeout_stays_unknown_no_repeat`
  and `test_final_total_or_incomplete_binding_holds_without_compensation`.
- `test_invoice_request_keys_are_separate_stable_and_approval_bound` maps to
  durable `test_draft_first_item_attachment_final_total_and_replay` and
  `test_item_snapshot_binds_committed_draft_id_not_pending_customer_item`.
- `test_old_omitted_pending_item_mock_contract_is_excluded_not_attached` has
  no authorized legacy replacement: durable dispatch deliberately uses a
  draft-first attachment. The omitted-default Stripe behavior remains untested.
- Real browser fixture uses its own raw context to intercept transport, set
  fixture readback values and issue an adversarial subresource request. The
  public wrapper exposes no raw context/evaluate and its fill refuses without
  changing the DOM. There is no authorized local-manager fill replacement.
  Capture-bound submit tests cover the separate signed-token submit path,
  not local fill. No bound fill coverage is claimed.

The old assertions describe unavailable paths, not a successful authorized
replacement. The new tests are fail-closed contract pins; no tests are skipped.
