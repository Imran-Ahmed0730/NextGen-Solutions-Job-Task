import { Button } from '@/components/ui/button';

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex max-w-6xl flex-col gap-10 px-6 py-20">
        <header className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-2xl shadow-slate-950/30">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-cyan-400">Sabuj Pran</p>
            <h1 className="mt-2 text-3xl font-semibold">Business Management Suite</h1>
          </div>
          <Button variant="secondary">Open Overview</Button>
        </header>

        <section className="grid gap-6 md:grid-cols-3">
          <article className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Core Modules</p>
            <p className="mt-3 text-3xl font-semibold">15</p>
          </article>
          <article className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Frontend Screens</p>
            <p className="mt-3 text-3xl font-semibold">38</p>
          </article>
          <article className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Foundation Status</p>
            <p className="mt-3 text-3xl font-semibold text-emerald-400">Ready</p>
          </article>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-slate-900 p-8">
          <h2 className="text-xl font-medium">Phase 0 foundation checklist</h2>
          <ul className="mt-4 space-y-3 text-slate-300">
            <li>? Monorepo structure established</li>
            <li>? FastAPI backend skeleton initialized</li>
            <li>? Next.js dashboard shell prepared</li>
            <li>? Docker Compose and environment templates created</li>
            <li>? CI and quality gates configured</li>
          </ul>
        </section>
      </div>
    </main>
  );
}
