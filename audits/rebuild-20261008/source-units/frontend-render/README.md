# A02-A06 render verification and chart/graph fix

A02 React 18 mount/hydration, A03 compiled Tailwind styling, A05 actual React
Flow SVG nodes/edge/filter/minimap and A06 actual Recharts bars rendered in
Chromium against controlled mocked API responses. A04 is local shadcn-style
Card code only; installed Radix dependencies are unused. No full shadcn-system
or live backend/provider/deployment acceptance is claimed. A01 Next14 is an
unresolved version decision, not fixed by this unit.

Corrected a misleading "Live KPI trend": current values of different KPIs
were joined as a time series. They now render as categorical bars grouped by
unit, with honest current-value framing. No time history invented. Component
pin verifies unlike units never share a chart. Graph uses ReactFlow dark mode
and explicit minimap colors so controls are legible against its dark canvas.

26 component tests in 6 files pass; focused Chromium render test passes;
6 architecture tests pass; typecheck and E2E production build pass. Network
responses are mocked; retained unrelated API DNS errors are not hidden.
Actual chart and graph screenshot pixels were inspected before handoff.
