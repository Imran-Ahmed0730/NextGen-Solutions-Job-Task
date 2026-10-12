'use client';

import Link from 'next/link';

import { ProtectedPage } from '@/components/auth/protected-page';

export default function Home() {
  return (
    <ProtectedPage>
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700">
        Sabuj Pran
      </p>
      <h1 className="mt-2 text-3xl font-semibold">Business Management Suite</h1>
      <p className="mt-2 text-slate-600">
        Authentication and access control are active for this workspace.
      </p>
      <section className="mt-8 grid gap-4 sm:grid-cols-2">
        <article className="rounded-xl border border-slate-200 p-5">
          <h2 className="font-medium">Phase 1 security</h2>
          <p className="mt-2 text-sm text-slate-600">
            Access tokens, rotating refresh sessions, role permissions, and audit logging.
          </p>
        </article>
        <article className="rounded-xl border border-slate-200 p-5">
          <h2 className="font-medium">Administrator tools</h2>
          <p className="mt-2 text-sm text-slate-600">
            Manage user access and role permissions from the administration pages.
          </p>
          <Link href="/users" className="mt-3 inline-block text-sm text-emerald-800 underline">
            Manage users
          </Link>
        </article>
      </section>
    </ProtectedPage>
  );
}
