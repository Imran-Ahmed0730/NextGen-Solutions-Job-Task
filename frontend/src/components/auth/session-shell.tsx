'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

import { ApiError, apiRequest, clearSession, type Profile } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

const navigation = [
  {
    label: 'Workspace',
    items: [
      { href: '/', label: 'Overview', icon: 'grid', permissions: ['auth.profile.read'] },
      { href: '/profile', label: 'My Profile', icon: 'user', permissions: ['auth.profile.read'] },
      {
        href: '/change-password',
        label: 'Change Password',
        icon: 'key',
        permissions: ['auth.password.change'],
      },
    ],
  },
  {
    label: 'Administration',
    items: [
      { href: '/users', label: 'Users', icon: 'users', permissions: ['auth.users.read'] },
      {
        href: '/roles',
        label: 'Roles',
        icon: 'shield',
        permissions: ['auth.roles.read', 'auth.permissions.read'],
      },
      {
        href: '/permissions',
        label: 'Permissions',
        icon: 'list',
        permissions: ['auth.permissions.read'],
      },
    ],
  },
  {
    label: 'Master data',
    items: [
      { href: '/units', label: 'Units', icon: 'box', permissions: ['master_data.units.read'] },
      {
        href: '/categories',
        label: 'Product Categories',
        icon: 'folder',
        permissions: ['master_data.product_categories.read'],
      },
      {
        href: '/products',
        label: 'Products',
        icon: 'tag',
        permissions: ['master_data.products.read'],
      },
      {
        href: '/warehouses',
        label: 'Warehouses',
        icon: 'warehouse',
        permissions: ['master_data.warehouses.read'],
      },
    ],
  },
] as const;

const iconPaths = {
  grid: (
    <>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c.7-3.2 3.1-5 7-5s6.3 1.8 7 5" />
    </>
  ),
  key: <path d="M15.5 8a4.5 4.5 0 1 1-1.2-3L22 12.7V16h-3v3h-3v-3h-2.3l-2.2-2.2A4.5 4.5 0 0 1 15.5 8Zm-4 0h.01" />,
  users: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 20c.5-3.1 2.3-4.7 5.5-4.7s5 1.6 5.5 4.7M16 5.5a3 3 0 0 1 0 5.8m1 4c2.1.5 3.3 2 3.6 4.7" />
    </>
  ),
  box: <path d="m12 3 8.5 4.5v9L12 21l-8.5-4.5v-9L12 3Zm-8.5 4.5L12 12l8.5-4.5M12 12v9" />,
  folder: <path d="M3.5 6.5h7l2 2h8v9a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2v-11Z" />,
  tag: <path d="M12 2H2v10l9.29 9.29c.94.94 2.48.94 3.42 0l6.58-6.58c.94-.94.94-2.48 0-3.42L12 2Zm-5 7a2 2 0 1 1 0-4 2 2 0 0 1 0 4Z" />,
  warehouse: <path d="M3 21V9l9-6 9 6v12M3 21h18M9.5 21v-6h5v6" />,
  shield: <path d="M12 3 20 6v5.5c0 4.6-3.1 7.8-8 9.5-4.9-1.7-8-4.9-8-9.5V6l8-3Zm-3.5 9 2.3 2.3 4.8-5" />,
  list: <path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" />,
  logout: <path d="M10 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5m5-4 4-4-4-4m4 4H9" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
} as const;

function AppIcon({ name, className = 'h-5 w-5' }: { name: keyof typeof iconPaths; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.7"
      viewBox="0 0 24 24"
    >
      {iconPaths[name]}
    </svg>
  );
}

function isNavigationItemActive(href: string, pathname: string): boolean {
  return href === pathname || (href !== '/' && pathname.startsWith(`${href}/`));
}

function getNavigationLabel(pathname: string): string {
  for (const group of navigation) {
    const item = group.items.find((entry) => isNavigationItemActive(entry.href, pathname));
    if (item) return item.label;
  }
  return 'Workspace';
}

const SessionContext = createContext<Profile | null>(null);

export function useSessionProfile(): Profile | null {
  return useContext(SessionContext);
}

export function SessionShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState('');
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);

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
    return (
      <main
        aria-live="polite"
        className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-emerald-50 via-white to-amber-50 px-5 py-12"
      >
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-emerald-200/40 blur-3xl" />
          <div className="absolute -bottom-32 -right-20 h-96 w-96 rounded-full bg-amber-200/40 blur-3xl" />
        </div>

        <section
          role="status"
          className="relative w-full max-w-lg rounded-2xl border border-white/80 bg-white/90 p-7 shadow-xl shadow-emerald-950/5 backdrop-blur sm:p-10"
        >
          <div className="mb-10 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-700 text-sm font-bold tracking-wide text-white shadow-md shadow-emerald-900/15">
              SP
            </div>
            <div>
              <p className="text-sm font-bold tracking-[0.14em] text-emerald-900">SABUJ PRAN</p>
              <p className="text-xs text-slate-500">Business Suite</p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div
              aria-hidden="true"
              className="mt-1 h-6 w-6 shrink-0 animate-spin rounded-full border-[3px] border-emerald-100 border-t-emerald-700 motion-reduce:animate-none"
            />
            <div>
              <h1 className="text-lg font-semibold text-slate-900">Preparing your workspace</h1>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                We’re securely loading your profile and the tools available to you.
              </p>
            </div>
          </div>

          <div aria-hidden="true" className="mt-9 space-y-3">
            <div className="h-2.5 w-2/5 animate-pulse rounded-full bg-slate-100 motion-reduce:animate-none" />
            <div className="h-2.5 w-full animate-pulse rounded-full bg-slate-100 motion-reduce:animate-none" />
            <div className="h-2.5 w-4/5 animate-pulse rounded-full bg-slate-100 motion-reduce:animate-none" />
          </div>
        </section>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      {mobileNavigationOpen && (
        <button
          type="button"
          aria-label="Close navigation menu"
          onClick={() => setMobileNavigationOpen(false)}
          className="fixed inset-0 z-40 bg-slate-950/40 lg:hidden"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-200 bg-white transition-transform duration-200 lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0 ${
          mobileNavigationOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-20 items-center justify-between border-b border-slate-100 px-6">
          <Link
            href="/"
            onClick={() => setMobileNavigationOpen(false)}
            className="flex items-center gap-3"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-700 text-xs font-bold tracking-wide text-white">
              SP
            </span>
            <span>
              <span className="block text-sm font-bold tracking-[0.12em] text-emerald-950">
                SABUJ PRAN
              </span>
              <span className="block text-xs text-slate-500">Business Suite</span>
            </span>
          </Link>
          <button
            type="button"
            aria-label="Close navigation menu"
            onClick={() => setMobileNavigationOpen(false)}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
          >
            <AppIcon name="close" />
          </button>
        </div>

        <nav aria-label="Main navigation" className="flex-1 space-y-7 overflow-y-auto px-4 py-6">
          {navigation.map((group) => {
            const items = group.items.filter((item) =>
              item.permissions.every((permission) => profile.permissions.includes(permission)),
            );
            if (!items.length) return null;
            return (
              <section key={group.label}>
                <h2 className="px-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                  {group.label}
                </h2>
                <div className="mt-2 space-y-1">
                  {items.map((item) => {
                    const current = isNavigationItemActive(item.href, pathname);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        aria-current={current ? 'page' : undefined}
                        onClick={() => setMobileNavigationOpen(false)}
                        className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                          current
                            ? 'bg-emerald-50 font-semibold text-emerald-800'
                            : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                        }`}
                      >
                        <AppIcon
                          name={item.icon}
                          className="h-[18px] w-[18px] shrink-0"
                        />
                        {item.label}
                        {current && (
                          <span className="ml-auto h-1.5 w-1.5 rounded-full bg-emerald-600" />
                        )}
                      </Link>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </nav>

        <div className="border-t border-slate-100 p-4">
          <div className="flex items-center gap-3 rounded-lg bg-slate-50 p-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-sm font-semibold text-emerald-800">
              {profile.full_name.slice(0, 1).toUpperCase()}
            </span>
            <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">
              {profile.full_name}
            </span>
            {profile.permissions.includes('auth.session.logout') && (
              <button
                type="button"
                title="Sign out"
                aria-label="Sign out"
                onClick={signOut}
                className="rounded-md p-2 text-slate-500 hover:bg-white hover:text-rose-700"
              >
                <AppIcon name="logout" className="h-[18px] w-[18px]" />
              </button>
            )}
          </div>
        </div>
      </aside>

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="Open navigation menu"
              aria-expanded={mobileNavigationOpen}
              onClick={() => setMobileNavigationOpen(true)}
              className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            >
              <AppIcon name="menu" />
            </button>
            <div>
              <p className="text-sm font-semibold text-slate-900">
                {getNavigationLabel(pathname)}
              </p>
              <p className="hidden text-xs text-slate-500 sm:block">
                Sabuj Pran Business Suite
              </p>
            </div>
          </div>
          <span className="hidden text-sm text-slate-600 sm:block">{profile.full_name}</span>
        </header>
        <SessionContext.Provider value={profile}>
          <main className="mx-auto w-full max-w-[1600px] flex-1 p-4 sm:p-6 lg:p-8">
            {children}
          </main>
        </SessionContext.Provider>
      </div>
    </div>
  );
}
