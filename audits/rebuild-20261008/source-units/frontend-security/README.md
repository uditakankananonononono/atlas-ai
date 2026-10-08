# Frontend security unit, base e763c4822

A01 literal Next.js 14 remains blocked on the owner's version decision. This
unit fixes current-runtime security findings, not A01 doc compliance.

Before: 16 npm audit dependency findings (2 critical, 9 high, 5 moderate).
After: 13 (2 critical, 6 high, 5 moderate). These count dependency findings,
not exploited vulnerabilities or distinct advisory IDs. Remaining dev-tool
and Tailwind findings require a separate migration review. No zero-risk claim.

Updated Next 16.3.6 to 16.3.8 (plus its env/SWC packages), sharp 0.35.4 to
0.35.5 (platform bindings and libvips patch updates), source-map-js 1.2.1 to
1.2.2. No major upgrades or overrides. React, Tailwind and Vitest unchanged.

Audit evidence retains advisory URLs/ranges. Next advisory ranges include
>=16.3.0 <16.3.8 and >=16.0.0 <16.3.8; sharp <0.35.5;
source-map-js >=1.0.0 <1.2.2. Observed URLs:
https://github.com/advisories/GHSA-cjq9-62q9-8jv4
https://github.com/advisories/GHSA-3w37-wq28-93x7
https://github.com/advisories/GHSA-4jqv-mc3x-m676
https://github.com/advisories/GHSA-39w2-rjm5-chcv
https://github.com/advisories/GHSA-f87g-xv8r-7p7x
https://github.com/advisories/GHSA-mcj8-r9mp-w47p
https://github.com/advisories/GHSA-wq5f-xc86-pv6w
https://github.com/advisories/GHSA-68fv-2mgg-jv7q

Typecheck and production build pass; 5 component test files / 25 tests pass;
8 Chromium E2E tests pass with mocked network routes and retained backend
DNS errors. This is not live full-stack, real provider, or deployment acceptance.
