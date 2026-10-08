# A04 owned dialog increment

Adds local shadcn-style Radix dialog primitives with an actual product consumer:
Knowledge Workspace node notes open on double-click. Escape closes the dialog,
and a standalone trigger test verifies focus restoration, accessible title and
description. Card + dialog now exist; tabs and a full component catalog are not
implemented. This is a scoped increment, not full A04 system compliance.

27 component tests in 7 files pass, typecheck passes, one actual Chromium render
journey passes with controlled mocked API data. The real browser checks opening
node notes, displaying their body and closing on Escape. Dialog screenshot pixels
were inspected: centered readable content, dark background overlay and close
button. No accessibility certification or live backend acceptance claim.
