# M13 browser agent: artifact containment contract

All screenshot / HAR / bridged-page artifact writes go through
`artifact_directory.ArtifactRoot`. This document states exactly what that
does and does not guarantee. It exists so no report overclaims.

## Closed (deterministic, pre-write attacks only)

- Traversal and dot-only ids (`..`) are rejected before any filesystem use.
- Preexisting symlink components and planted symlink filenames are refused
  (O_NOFOLLOW | O_DIRECTORY walk, O_EXCL create).
- A directory swap or rename that has **already happened** when the walk or
  the pre/post-write kernel-path check runs is refused (the deterministic
  pre-creation rename attack).
- A component renamed away before the walk is recreated inside the root, so
  bytes never follow the moved inode.

## NOT closed (the checks are check-then-act, non-atomic)

- A rename or bind mount that lands **after** the final post-write check
  still escapes. The window is small; it is real.
- The post-write unlink cannot undo bytes another process already read from
  the escaped file before the check ran.
- HAR (`audit.har`) is written by the Playwright driver process from a path
  string at context close. It cannot be contained at all; the close-time
  check **detects** a violation after the driver write - escaped HAR bytes
  are found, not prevented.

Against a hostile same-UID actor there is no "zero escaped bytes"
guarantee in this module. Full confinement needs mount namespaces, not
path checks.

## Historical combined M13 failure: UNRESOLVED

The peer-attributed original run (b944215, combined M11+M13: 159 passed,
1 failed, the real-Chromium source-reconciliation test) is **not
explained**. The traceback and execution order were never retained, and no
reproduction since (default order, seeds 17/83, standalone, 10 repeats) has
failed. A load-induced browser/driver process kill (e.g. OOM) surfacing as
a Playwright transport error at the generic re-raise site is a **hypothesis
only**. Because the trace and order are missing, a product-code defect
**cannot be ruled out**. See
`audits/rebuild-20261007/m13-order-reproduction/status.md`.
