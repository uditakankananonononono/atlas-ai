# Graph notes keyboard and focus follow-up

The actual node card now includes a native Open notes button. Enter and Space
open the same dialog; Escape or Close returns focus to that initiating node's
button. Double-click still opens notes and records the matching button as focus
return target. No dependence on a standalone DialogTrigger test for this claim.

Actual Chromium journey verifies focused node button -> Enter -> named dialog
with correct body -> Escape -> same button focused -> Space -> Close -> same
button focused. Controlled mocked API only. 27 component tests and typecheck
pass. Current graph screenshot inspected for readable node trigger placement.
This does not certify all assistive technologies, disappearing nodes or a full
accessibility audit. Card and dialog remain a scoped component-system increment.
