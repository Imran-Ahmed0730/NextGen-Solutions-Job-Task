'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';

import { apiRequest, storeSession, type SessionTokens } from '@/lib/auth-api';
import { loginSchema } from '@/lib/auth-validation';
import { showErrorToast } from '@/lib/notifications';

export default function LoginPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const parsed = loginSchema.safeParse(values);
    if (!parsed.success) {
      showErrorToast(parsed.error.issues[0]?.message ?? 'Check your login details');
      return;
    }
    setBusy(true);
    try {
      const tokens = await apiRequest<SessionTokens>(
        '/api/v1/auth/login',
        { method: 'POST', body: JSON.stringify(parsed.data) },
        { authenticated: false },
      );
      storeSession(tokens);
      router.replace('/');
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Sign in failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-lg">
        <p className="text-sm font-semibold tracking-[0.18em] text-emerald-700">SABUJ PRAN</p>
        <h1 className="mt-2 text-2xl font-semibold">Sign in</h1>
        <p className="mt-2 text-sm text-slate-500">Use your username, email, or mobile number.</p>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Username, email, or mobile
            <input
              name="username"
              autoComplete="username"
              autoFocus
              minLength={1}
              required
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="block text-sm font-medium">
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              minLength={1}
              required
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-md bg-emerald-700 px-4 py-2.5 font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <Link href="/forgot-password" className="mt-5 inline-block text-sm text-emerald-800 underline">
          Forgot password?
        </Link>
      </section>
    </main>
  );
}
