'use client';

import Link from 'next/link';
import { useState, type FormEvent } from 'react';

import { apiRequest } from '@/lib/auth-api';
import { forgotPasswordSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast, showToast } from '@/lib/notifications';

export default function ForgotPasswordPage() {
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = forgotPasswordSchema.safeParse(
      Object.fromEntries(new FormData(event.currentTarget)),
    );
    if (!parsed.success) {
      showErrorToast(parsed.error.issues[0]?.message ?? 'Enter your email address');
      return;
    }
    setBusy(true);
    try {
      const result = await apiRequest<{ message: string }>(
        '/api/v1/auth/forgot-password',
        { method: 'POST', body: JSON.stringify(parsed.data) },
        { authenticated: false },
      );
      showSuccessToast(result.message);
    } catch (cause) {
      showToast(
        'error',
        'Password reset email could not be delivered',
        cause instanceof Error ? cause.message : 'Could not submit the request',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-lg">
        <h1 className="text-2xl font-semibold">Forgot password</h1>
        <p className="mt-2 text-sm text-slate-600">
          Enter the email address on your account. If it matches, we’ll email you a one-time
          password reset link.
        </p>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Email address
            <input
              name="email"
              type="email"
              autoComplete="email"
              required
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
          </label>
          <button
            disabled={busy}
            className="w-full rounded-md bg-emerald-700 px-4 py-2.5 font-medium text-white disabled:opacity-60"
          >
            {busy ? 'Sending…' : 'Submit request'}
          </button>
        </form>
        <div>
          <Link href="/login" className="mt-3 inline-block text-sm text-slate-600 underline">
            Back to sign in
          </Link>
        </div>
      </section>
    </main>
  );
}
