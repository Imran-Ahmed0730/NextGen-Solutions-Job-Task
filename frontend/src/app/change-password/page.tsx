'use client';

import { useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { FieldError, getFieldErrors, RequiredMark, type FieldErrors } from '@/components/forms/field-error';
import { apiRequest, storeSession, type SessionTokens } from '@/lib/auth-api';
import { changePasswordSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

export default function ChangePasswordPage() {
  const [errors, setErrors] = useState<FieldErrors>({});

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const parsed = changePasswordSchema.safeParse(
      Object.fromEntries(new FormData(event.currentTarget)),
    );
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});
    try {
      const tokens = await apiRequest<SessionTokens>('/api/v1/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: parsed.data.current_password,
          new_password: parsed.data.new_password,
        }),
      });
      storeSession(tokens);
      form.reset();
      showSuccessToast('Password changed. Your session remains active.');
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not change password');
    }
  }

  return (
    <ProtectedPage>
      <h1 className="text-2xl font-semibold">Change Password</h1>
      <form noValidate className="mt-6 max-w-xl space-y-4" onSubmit={submit}>
        <label className="block text-sm font-medium">
          Current password<RequiredMark />
          <input name="current_password" type="password" placeholder="Enter your current password" autoComplete="current-password" required aria-invalid={Boolean(errors.current_password)} aria-describedby={errors.current_password ? 'current-password-error' : undefined} className="mt-1 w-full rounded-md border px-3 py-2" />
          <FieldError id="current-password-error" message={errors.current_password} />
        </label>
        <label className="block text-sm font-medium">
          New password<RequiredMark />
          <input name="new_password" type="password" placeholder="At least 8 characters" autoComplete="new-password" required aria-invalid={Boolean(errors.new_password)} aria-describedby={errors.new_password ? 'new-password-error' : undefined} className="mt-1 w-full rounded-md border px-3 py-2" />
          <FieldError id="new-password-error" message={errors.new_password} />
        </label>
        <label className="block text-sm font-medium">
          Confirm new password<RequiredMark />
          <input name="confirm_password" type="password" placeholder="Re-enter your new password" autoComplete="new-password" required aria-invalid={Boolean(errors.confirm_password)} aria-describedby={errors.confirm_password ? 'confirm-password-error' : undefined} className="mt-1 w-full rounded-md border px-3 py-2" />
          <FieldError id="confirm-password-error" message={errors.confirm_password} />
        </label>
        <button className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white">Update password</button>
      </form>
    </ProtectedPage>
  );
}
