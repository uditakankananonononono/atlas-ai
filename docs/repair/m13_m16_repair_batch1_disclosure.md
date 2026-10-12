# m13-m16 repair batch 1: disclosures and claim scope

Not pushed. Local patch series only.

## ATLAS-m13.A01 classifier scope
`NavigationLoop._submit_like` is a heuristic that fails closed. It is NOT a blanket submit gate.
- A click skips approval only when a DOM probe succeeds and the element is positively inert: an `<a>` with a relative or http(s) href, a select, a textarea, or a text-like input. It must also be outside any form, have no onclick/onsubmit/formaction/data-action attribute, and carry no submit words.
- Probe missing, probe exception, non-dict result, javascript:/data:/vbscript:/blob: or any other non-http(s) scheme, form membership, custom handler attribute, or any other tag all route to approval.
- Not detected: handlers attached with addEventListener, framework-bound handlers, and links whose http(s) target performs a state-changing GET. A click that looks inert can still cause a submit. The real submit gate is ApplicationFlow.

## ATLAS-m16.A01 delivery semantics
`execute` calls `mark_command` BEFORE filing the approval. This is at-most-once, NOT exactly-once.
Failure window: if the store or approval write fails after the mark, the approval for that command is lost, and a retry will not file one. No reconciliation or recovery path exists. Do not claim exactly-once.

## ATLAS-m13.A03 / A05, m15.A03, m16.A02
No extra disclosures beyond the row text. m15.A03 escapes only values passed through the legacy `Service.render_latex`. It is not a TeX sandbox.
