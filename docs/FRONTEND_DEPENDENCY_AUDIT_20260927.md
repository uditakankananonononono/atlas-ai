# Frontend dependency update (2026-09-27)

The prior lock pinned Next.js 14.2.32. A local `npm audit --omit=dev` showed one critical and one high production dependency finding. The update pins Next.js 16.3.6 and refreshes the frontend lockfile and generated Next TypeScript configuration. On Node 22.23.2, a clean `npm ci`, `npm run typecheck`, and `npm run build` passed. The resulting `npm audit --omit=dev` had zero reported vulnerabilities at the time of the check. This is a point-in-time advisory result, not a security certification.

Remaining limits: browser E2E was not rerun, no production environment was deployed or penetration-tested, the test runner's generated changes to next-env.d.ts and tsconfig.json were inspected and retained, and Next's workspace-root warning reflects two lockfiles (repo root and frontend). The application must still respect its same-origin API proxy security boundaries. Upgrading Next does not prove the full Atlas product is ready.
