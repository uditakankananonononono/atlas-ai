"""Buildable Next.js landing archives. User text is data, never TSX source."""
import json
from .schemas import LandingPageIn


def landing_files(data: LandingPageIn) -> dict[str, str]:
    content = {"product_name": data.product_name, "hero": data.hero, "features": data.features}
    package = {
        "name": "review-first-landing", "version": "1.0.0", "private": True,
        "scripts": {"dev": "next dev", "build": "next build --webpack", "start": "next start", "typecheck": "tsc --noEmit"},
        "engines": {"node": ">=20.9.0"},
        "dependencies": {"next": "16.4.0", "react": "19.3.0", "react-dom": "19.3.0", "@supabase/supabase-js": "2.117.3"},
        "devDependencies": {"typescript": "5.9.3", "@types/node": "22.19.15", "@types/react": "19.3.0", "@types/react-dom": "19.3.0", "tailwindcss": "3.4.19", "postcss": "8.5.29", "autoprefixer": "10.6.1"},
    }
    return {
        "package.json": json.dumps(package, indent=2) + "\n",
        "tsconfig.json": json.dumps({"compilerOptions": {"target": "ES2017", "lib": ["dom", "dom.iterable", "esnext"], "allowJs": True, "skipLibCheck": True, "strict": True, "noEmit": True, "esModuleInterop": True, "module": "esnext", "moduleResolution": "bundler", "resolveJsonModule": True, "isolatedModules": True, "jsx": "react-jsx", "incremental": True, "plugins": [{"name": "next"}]}, "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"], "exclude": ["node_modules"]}, indent=2) + "\n",
        "next.config.mjs": "export default { experimental: { cpus: 2 } };\n",
        "postcss.config.mjs": "export default { plugins: { tailwindcss: {}, autoprefixer: {} } };\n",
        "tailwind.config.ts": 'import type { Config } from "tailwindcss";\nexport default {content: ["./app/**/*.{ts,tsx}"], theme: {extend: {}}, plugins: []} satisfies Config;\n',
        "next-env.d.ts": '/// <reference types="next" />\n/// <reference types="next/image-types/global" />\n',
        "app/content.json": json.dumps(content, ensure_ascii=True, indent=2) + "\n",
        "app/layout.tsx": '''import type { ReactNode } from "react";
import content from "./content.json";
import "./globals.css";
export const metadata = {title: content.product_name, description: content.hero};
export default function Layout({children}: {children: ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
''',
        "app/page.tsx": '''import content from "./content.json";
export default function Page() {
  return <main className="mx-auto max-w-5xl p-6 sm:p-10">
    <section className="py-16"><h1 className="break-words text-4xl font-bold sm:text-6xl">{content.product_name}</h1>
    <p className="mt-6 break-words text-xl leading-relaxed">{content.hero}</p></section>
    <ul aria-label="Features" className="grid gap-6 md:grid-cols-3">
      {content.features.map((feature, index) => <li key={index} className="break-words rounded-xl border border-slate-300 p-5">{feature}</li>)}
    </ul>
    <form action="/api/waitlist" method="post" className="mt-16 flex flex-col gap-3 sm:flex-row">
      <label className="flex flex-col gap-2">Email<input required type="email" name="email" maxLength={254} autoComplete="email" className="rounded border border-slate-400 p-3" /></label>
      <button className="self-start rounded bg-slate-900 p-3 text-white sm:self-end">Join waitlist</button>
    </form>
  </main>;
}
''',
        "app/api/waitlist/route.ts": _route(data.waitlist_table),
        "app/globals.css": '@tailwind base;\n@tailwind components;\n@tailwind utilities;\nbody { color: #0f172a; background: #fff; }\n',
        ".env.example": "NEXT_PUBLIC_SUPABASE_URL=\nSUPABASE_SERVICE_ROLE_KEY=\n",
        "supabase/waitlist.sql": 'CREATE TABLE IF NOT EXISTS public."' + data.waitlist_table + '" (email text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now());\nALTER TABLE public."' + data.waitlist_table + '" ENABLE ROW LEVEL SECURITY;\n',
        "README.md": """# Review-first landing site

Requires Node >=20.9. Run `npm install`, `npm run build`, then `npm start`.
Dependency versions are pinned; npm install produces a lockfile for review.
Review this generated archive before any push, deploy, or sharing.

Run supabase/waitlist.sql in your own Supabase project. Existing tables must
already have a UNIQUE/PRIMARY KEY constraint on email; IF NOT EXISTS does not
migrate an existing table. Supply the URL and server-only service role key
through your deployment's secret store. Never put the key in browser config.
RLS has no public insert policy: only the server's service-role client writes.

POST /api/waitlist accepts form data with email. Invalid input returns 400;
unconfigured or unavailable storage returns 503; successful upsert returns
200 JSON. Duplicate email is idempotent. No deploy or live database write
is performed by archive generation. Rate limiting, email verification,
anti-spam, privacy/consent policy and production monitoring are not included.
""",
    }


def _route(table: str) -> str:
    # LandingPageIn validates the SQL identifier before this function is used.
    return '''import { createClient } from "@supabase/supabase-js";
export async function POST(request: Request) {
  let form: FormData;
  try { form = await request.formData(); }
  catch { return Response.json({error: "invalid form"}, {status: 400}); }
  const raw = form.get("email");
  if (typeof raw !== "string") return Response.json({error: "invalid email"}, {status: 400});
  const email = raw.trim().toLowerCase();
  if (email.length > 254 || !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email))
    return Response.json({error: "invalid email"}, {status: 400});
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return Response.json({error: "waitlist unavailable"}, {status: 503});
  try {
    const client = createClient(url, key);
    const { error } = await client.from(TABLE).upsert({email}, {onConflict: "email", ignoreDuplicates: true});
    if (error) return Response.json({error: "waitlist unavailable"}, {status: 503});
    return Response.json({ok: true});
  } catch { return Response.json({error: "waitlist unavailable"}, {status: 503}); }
}
'''.replace("TABLE", json.dumps(table))
