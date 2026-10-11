# M20 QUALSYS840/856 scoped contract

## 840: finite signed landmark graph

`qualitative_variables` contains 1..6 unique IDs, 2..5 unique ordered landmarks each (nondecreasing signs -1/0/+1), and a known initial landmark. `qualitative_influences` contains 0..64 unique sourced signed edges between known variables. Nonzero edge signs multiply the current source landmark sign. No active effects means stay; a single effect sign means move one adjacent landmark, clamped at endpoints. Opposing signs preserve decrease, stay and increase as alternatives rather than averaging. All variables change synchronously. `qualitative_steps` is an integer 0..8.

The graph reports deduplicated sorted states at every completed step, sourced sorted influences and ambiguity. A 256-successor cap per step and 4096 generated-candidate cap per call return `state_budget_exhausted` with only fully completed steps. These are explicit supplied dynamics, not qualitative physics discovery, real-world validity or numeric prediction.

## 856: exact stock-flow simulation

`system_stocks` contains 1..16 sourced unique nonnegative stocks with explicit unit labels. `system_flows` contains 0..32 sourced unique flows with distinct known endpoints, permitting exactly one external endpoint. `rate_kind` is constant or proportional. Rates are exact bounded rationals in [0,1000]. Stock-unit labels must match both internal endpoints; `time_unit` must match `system_time_unit`. Labels are declarations, not unit conversion or dimensional truth checking.

A constant rate has no driver or delay. A proportional rate uses a known driver with matching stock units, so its declared coefficient is interpreted per declared time unit. Integer delays are 0..8 steps. Driver history uses the initial stock before the first step (constant prehistory). `system_dt` is an exact rational in (0,1000]; `system_steps` is an integer 0..64. Arithmetic uses integer or ASCII integer/fraction strings, each component at most 10^12. Intermediate amounts, stock values and cumulative external balance enforce the same bound.

Every step computes all amounts from the previous/history states, then applies them together. A negative resulting stock stops with `negative_stock_blocked`, preserving only previously completed trajectory, records and external balance. No clipping or invented allocation. Closed-system totals and open-system net external transfers are checked separately per unit. Feedback cycles are canonical simple directed stock cycles with structural sign products from positive proportional-rate flow effects. They are not stability or causal conclusions. Feedback traversal is capped at 4096 edges, refusing more complex graphs.

No external execution, persistence, learned dynamics, hidden initial conditions, real-world prediction or independent source verification. Minimal payloads refuse. Mounted routes retain authentication and tenant checks. These two rows are restricted computations, not general closure of qualitative or systems thinking.
