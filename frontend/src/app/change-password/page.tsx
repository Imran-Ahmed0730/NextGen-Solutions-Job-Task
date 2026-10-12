'use client';

import { useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { apiRequest, storeSession, type SessionTokens } from '@/lib/auth-api';
import { changePasswordSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

export default function ChangePasswordPage() {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const parsed = changePasswordSchema.safeParse(
      Object.fromEntries(new FormData(event.currentTarget)),
    );
    if (!parsed.success) {
      showErrorToast(parsed.error.issues[0]?.message ?? 'Check your password details');
      return;
    }
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
      <form className="mt-6 max-w-xl space-y-4" onSubmit={submit}>
        <label className="block text-sm font-medium">
          Current password
          <input name="current_password" type="password" autoComplete="current-password" required className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          New password
          <input name="new_password" type="password" autoComplete="new-password" required className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          Confirm new password
          <input name="confirm_password" type="password" autoComplete="new-password" required className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        <button className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white">Update password</button>
      </form>
    </ProtectedPage>
  );
}
