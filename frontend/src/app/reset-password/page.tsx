'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';

import { FieldError, getFieldErrors, RequiredMark, type FieldErrors } from '@/components/forms/field-error';
import { apiRequest } from '@/lib/auth-api';
import { resetPasswordSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

export default function ResetPasswordPage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get('token') ?? '');
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = resetPasswordSchema.safeParse(
      Object.fromEntries(new FormData(event.currentTarget)),
    );
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});
    setBusy(true);
    try {
      await apiRequest<void>(
        '/api/v1/auth/reset-password',
        {
          method: 'POST',
          body: JSON.stringify({
            token: parsed.data.token,
            new_password: parsed.data.new_password,
          }),
        },
        { authenticated: false },
      );
      showSuccessToast('Password updated. You can now sign in.');
      window.setTimeout(() => router.replace('/login'), 1200);
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Password reset failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-lg">
        <h1 className="text-2xl font-semibold">Set a new password</h1>
        <form noValidate className="mt-6 space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            One-time token from your email<RequiredMark />
            <input
              name="token"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              required
              aria-invalid={Boolean(errors.token)}
              aria-describedby={errors.token ? 'reset-token-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="reset-token-error" message={errors.token} />
          </label>
          <label className="block text-sm font-medium">
            New password<RequiredMark />
            <input
              name="new_password"
              type="password"
              autoComplete="new-password"
              required
              aria-invalid={Boolean(errors.new_password)}
              aria-describedby={errors.new_password ? 'reset-password-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="reset-password-error" message={errors.new_password} />
          </label>
          <label className="block text-sm font-medium">
            Confirm password<RequiredMark />
            <input
              name="confirm_password"
              type="password"
              autoComplete="new-password"
              required
              aria-invalid={Boolean(errors.confirm_password)}
              aria-describedby={errors.confirm_password ? 'reset-confirm-password-error' : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id="reset-confirm-password-error" message={errors.confirm_password} />
          </label>
          <button
            disabled={busy}
            className="w-full rounded-md bg-emerald-700 px-4 py-2.5 font-medium text-white disabled:opacity-60"
          >
            {busy ? 'Updating…' : 'Update password'}
          </button>
        </form>
        <Link href="/login" className="mt-4 inline-block text-sm text-slate-600 underline">
          Back to sign in
        </Link>
      </section>
    </main>
  );
}
