'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

import { ApiError, apiRequest, clearSession, type Profile } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

const navigation = [
  { href: '/', label: 'Overview', permissions: ['auth.profile.read'] },
  { href: '/profile', label: 'My Profile', permissions: ['auth.profile.read'] },
  { href: '/change-password', label: 'Change Password', permissions: ['auth.password.change'] },
  { href: '/users', label: 'Users', permissions: ['auth.users.read'] },
  {
    href: '/roles',
    label: 'Roles',
    permissions: ['auth.roles.read', 'auth.permissions.read'],
  },
  { href: '/permissions', label: 'Permissions', permissions: ['auth.permissions.read'] },
];

const SessionContext = createContext<Profile | null>(null);

export function useSessionProfile(): Profile | null {
  return useContext(SessionContext);
}

export function SessionShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!sessionStorage.getItem('access_token')) {
      router.replace('/login');
      return;
    }
    apiRequest<Profile>('/api/v1/auth/me')
      .then(setProfile)
      .catch((cause: unknown) => {
        if (cause instanceof ApiError && cause.status === 401) {
          clearSession();
          router.replace('/login');
        } else {
          setError(cause instanceof Error ? cause.message : 'Could not load your profile');
        }
      });
  }, [router]);

  async function signOut() {
    try {
      await apiRequest<void>('/api/v1/auth/logout', { method: 'POST' });
      clearSession();
      router.replace('/login');
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not end this session');
    }
  }

  if (error) {
    return <main className="mx-auto max-w-3xl p-8 text-rose-700">{error}</main>;
  }
  if (!profile) {
    return <main className="p-8 text-slate-600">Loading your workspace…</main>;
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-4">
          <Link href="/" className="font-semibold tracking-wide text-emerald-800">
            SABUJ PRAN <span className="font-normal text-slate-500">Business Suite</span>
          </Link>
          <div className="flex items-center gap-4 text-sm">
            <span>{profile.full_name}</span>
            {profile.permissions.includes('auth.session.logout') && (
              <button
                type="button"
                onClick={signOut}
                className="rounded-md border border-slate-300 px-3 py-2 hover:bg-slate-50"
              >
                Sign out
              </button>
            )}
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-7xl gap-6 px-5 py-6 md:grid-cols-[220px_1fr]">
        <nav
          aria-label="Main navigation"
          className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-3 md:flex-col md:self-start"
        >
          {navigation
            .filter((item) =>
              item.permissions.every((permission) => profile.permissions.includes(permission)),
            )
            .map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={pathname === item.href ? 'page' : undefined}
                className={`rounded-lg px-3 py-2 text-sm ${
                  pathname === item.href
                    ? 'bg-emerald-50 font-medium text-emerald-800'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                {item.label}
              </Link>
            ))}
        </nav>
        <SessionContext.Provider value={profile}>
          <main className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:p-8">
            {children}
          </main>
        </SessionContext.Provider>
      </div>
    </div>
  );
}
