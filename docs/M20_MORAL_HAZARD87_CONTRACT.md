# MORAL87: supplied deal-control declaration inventory

Source: feature Doc 1kCtzves_4OGVKUdFUPC0bkvY3jQGnfpeeEJWe1mQ3xY,
"Moral Hazard Prevention - Structures deals to prevent reckless behavior".
Repo row87 at public base 4088674fcc3f9c7d96d25471575db6b0a9faa193 agrees.
Doc text was read from the earlier live export in this working session, not
refetched immediately before implementation. This is title-only scope, not full
row closure or proof of reckless-behavior prevention.

Existing mechanism: negotiation_behavior_0085_0109.py::_moral_hazard L107,
dispatch moral_hazard_prevention L499; test_row87_moral_hazard_exposure_scoring_and_controls.
It computes declared observability/incentive exposure with named heuristic
weights and generic recommendations. This addition does not replace it.
Exact delta: per-action declared monitoring/bonding/deductible class presence,
with exact missing-class gaps, strict declarations and source-reference inventory.
No exposure heuristic, risk score, recommendations or causal inference added.

inventory(data) accepts exactly source_ref, actions and controls. Each action
has id, strict boolean observable and incentive in aligned/misaligned/unknown.
Each control has action_id, class and source_ref. Class is exactly monitoring,
bonding or deductible; action IDs must exist; duplicate action/class declarations
refuse. IDs/refs are stripped nonblank control-free text up to 200 characters.
Actions 1-100; controls 0-300. Unknown keys refuse with MORAL87: prefix.
Output deterministically sorts actions/controls, names each missing class per
action, counts declared classes, and names unobservable/misaligned/unknown IDs.
All classes present means supplied schema coverage only, not effective controls.

LIMITS: caller declarations only. No actual observability, incentive alignment,
bond enforceability, deductible adequacy or monitoring effectiveness verified.
Every missing class is an inventory gap, NOT a recommendation every deal must
use every class. No causal prevention, actual deal structuring, account, browser,
contact, application, outreach, spend or other external action. No routing,
cluster/ledger replacement or shared-file edits. Free offline stdlib only.

Executed seven unittest tests in /tmp/trunk-replacement/venv/bin/python,
CPython 3.12.14. Valid missing-core RED preceded creation; GREEN and restored
GREEN passed. Six handwritten mutants separately produced five assertion kills
and one error kill; no timeout/survivor. Synthetic caller declarations test real
inventory code, not real-world moral-hazard prevention. No broad repo suite,
existing cluster runtime test, mounted auth/tenant or external vendor verification.
