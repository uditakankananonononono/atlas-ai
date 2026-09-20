const modules = ["Approvals", "Opportunities", "Research", "Outreach", "Projects", "Documents", "Calendar", "Knowledge"];
export default function Home() {
  return <main className="min-h-screen bg-slate-950 p-10 text-white">
    <p className="text-cyan-400">ATLAS AI / PHASE 1</p><h1 className="mt-2 text-4xl font-semibold">Human-controlled work, module by module.</h1>
    <section className="mt-10 grid gap-4 md:grid-cols-4">{modules.map((m) => <article key={m} className="rounded-xl border border-slate-700 bg-slate-900 p-5">{m}<p className="mt-2 text-sm text-slate-400">Foundation shell</p></article>)}</section>
  </main>;
}
