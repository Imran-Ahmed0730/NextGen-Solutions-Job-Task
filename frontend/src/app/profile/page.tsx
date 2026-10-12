'use client';

import { useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { ApiError, apiRequest, type Profile } from '@/lib/auth-api';
import { profileSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    apiRequest<Profile>('/api/v1/auth/me')
      .then(setProfile)
      .catch((cause: unknown) =>
        showErrorToast(cause instanceof Error ? cause.message : 'Could not load profile'),
      );
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = profileSchema.safeParse(Object.fromEntries(new FormData(event.currentTarget)));
    if (!parsed.success) {
      showErrorToast(parsed.error.issues[0]?.message ?? 'Check your profile details');
      return;
    }
    try {
      const updated = await apiRequest<Profile>('/api/v1/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({
          full_name: parsed.data.full_name,
          email: parsed.data.email || null,
          mobile: parsed.data.mobile || null,
        }),
      });
      setProfile(updated);
      showSuccessToast('Profile updated.');
    } catch (cause) {
      showErrorToast(cause instanceof ApiError ? cause.message : 'Could not update profile');
    }
  }

  return (
    <ProtectedPage>
      <h1 className="text-2xl font-semibold">My Profile</h1>
      <p className="mt-2 text-sm text-slate-600">Update your contact information.</p>
      {!profile ? (
        <p className="mt-6 text-sm text-slate-500">Loading profile…</p>
      ) : (
        <form className="mt-6 max-w-xl space-y-4" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Username
            <input value={profile.username} readOnly className="mt-1 w-full rounded-md border bg-slate-50 px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            Full name
            <input name="full_name" defaultValue={profile.full_name} required className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            Email
            <input name="email" type="email" defaultValue={profile.email ?? ''} className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <label className="block text-sm font-medium">
            Mobile
            <input name="mobile" defaultValue={profile.mobile ?? ''} className="mt-1 w-full rounded-md border px-3 py-2" />
          </label>
          <p className="text-sm text-slate-600">Roles: {profile.roles.join(', ') || 'None'}</p>
          <button className="rounded-md bg-emerald-700 px-4 py-2 font-medium text-white">Save profile</button>
        </form>
      )}
    </ProtectedPage>
  );
}
