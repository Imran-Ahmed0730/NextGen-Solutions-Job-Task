'use client';

import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

import {
  ApiError,
  apiRequest,
  clearSession,
  getApiUrl,
  type Profile,
} from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

const navigation = [
  {
    label: 'Workspace',
    items: [
      { href: '/', label: 'Dashboard', icon: 'grid', permissions: ['auth.profile.read'] },
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
      {
        href: '/expense-categories',
        label: 'Expense Categories',
        icon: 'expense',
        permissions: ['master_data.expense_categories.read'],
      },
      {
        href: '/income-categories',
        label: 'Income Categories',
        icon: 'income',
        permissions: ['master_data.income_categories.read'],
      },
      {
        href: '/payment-methods',
        label: 'Payment Methods',
        icon: 'payment',
        permissions: ['master_data.payment_methods.read'],
      },
      {
        href: '/money-accounts',
        label: 'Money Accounts',
        icon: 'account',
        permissions: ['master_data.money_accounts.read'],
      },
      {
        href: '/price-lists',
        label: 'Price Lists',
        icon: 'pricelist',
        permissions: ['master_data.price_lists.read'],
      },
      {
        href: '/company-settings',
        label: 'Company Settings',
        icon: 'settings',
        permissions: ['master_data.company_settings.read'],
      },
      {
        href: '/document-numbering',
        label: 'Document Numbering',
        icon: 'number',
        permissions: ['master_data.document_numbering.read'],
      },
      {
        href: '/approval-rules',
        label: 'Approval Rules',
        icon: 'settings',
        permissions: ['approvals.rules.read'],
      },
    ],
  },
  {
    label: 'Operations',
    items: [
      {
        href: '/assets',
        label: 'Assets',
        icon: 'box',
        permissions: ['assets.read'],
      },
      {
        href: '/employees',
        label: 'Employees',
        icon: 'users',
        permissions: ['employees.read'],
      },
      {
        href: '/attendance',
        label: 'Attendance',
        icon: 'users',
        permissions: ['employees.attendance.read'],
      },
      {
        href: '/payroll',
        label: 'Payroll',
        icon: 'account',
        permissions: ['employees.payroll.read'],
      },
    ],
  },
  {
    label: 'Parties',
    items: [
      {
        href: '/customers',
        label: 'Customers',
        icon: 'customer',
        permissions: ['master_data.customers.read'],
      },
      {
        href: '/suppliers',
        label: 'Suppliers',
        icon: 'supplier',
        permissions: ['master_data.suppliers.read'],
      },
    ],
  },
  {
    label: 'Inventory',
    items: [
      {
        href: '/warehouse-stock',
        label: 'Warehouse Stock',
        icon: 'warehouse',
        permissions: ['inventory.stock.read'],
      },
      {
        href: '/stock-ledger',
        label: 'Product Stock Ledger',
        icon: 'warehouse',
        permissions: ['inventory.stock.read'],
      },
      {
        href: '/stock-transfers',
        label: 'Stock Transfers',
        icon: 'warehouse',
        permissions: ['inventory.transfers.read'],
      },
      {
        href: '/stock-adjustments',
        label: 'Stock Adjustments',
        icon: 'warehouse',
        permissions: ['inventory.adjustments.read'],
      },
      {
        href: '/physical-counts',
        label: 'Physical Count',
        icon: 'warehouse',
        permissions: ['inventory.physical_counts.read'],
      },
    ],
  },
  {
    label: 'Purchase',
    items: [
      {
        href: '/purchase-orders',
        label: 'Purchase Orders',
        icon: 'supplier',
        permissions: ['purchase.orders.read'],
      },
      {
        href: '/goods-receipts',
        label: 'Goods Receipts',
        icon: 'supplier',
        permissions: ['purchase.receipts.read'],
      },
      {
        href: '/direct-purchases',
        label: 'Direct Purchases',
        icon: 'supplier',
        permissions: ['purchase.direct_purchases.read'],
      },
      {
        href: '/purchase-returns',
        label: 'Purchase Returns',
        icon: 'supplier',
        permissions: ['purchase.returns.read'],
      },
    ],
  },
  {
    label: 'Sales',
    items: [
      {
        href: '/quotations',
        label: 'Quotations',
        icon: 'customer',
        permissions: ['sales.quotations.read'],
      },
      {
        href: '/sales-orders',
        label: 'Sales Orders',
        icon: 'customer',
        permissions: ['sales.orders.read'],
      },
      {
        href: '/sales-invoices',
        label: 'Sales Invoices',
        icon: 'customer',
        permissions: ['sales.invoices.read'],
      },
      {
        href: '/sales-returns',
        label: 'Sales Returns',
        icon: 'customer',
        permissions: ['sales.returns.read'],
      },
    ],
  },
  {
    label: 'Production',
    items: [
      {
        href: '/production-orders',
        label: 'Production Orders',
        icon: 'warehouse',
        permissions: ['production.orders.read'],
      },
      {
        href: '/boms',
        label: 'Bills of Materials',
        icon: 'warehouse',
        permissions: ['production.boms.read'],
      },
    ],
  },
  {
    label: 'Money',
    items: [
      {
        href: '/customer-collections',
        label: 'Customer Collections',
        icon: 'customer',
        permissions: ['money.collections.read'],
      },
      {
        href: '/supplier-payments',
        label: 'Supplier Payments',
        icon: 'supplier',
        permissions: ['money.supplier_payments.read'],
      },
      {
        href: '/expenses',
        label: 'Expenses',
        icon: 'expense',
        permissions: ['money.expenses.read'],
      },
      {
        href: '/incomes',
        label: 'Incomes',
        icon: 'income',
        permissions: ['money.incomes.read'],
      },
      {
        href: '/fund-transfers',
        label: 'Fund Transfers',
        icon: 'account',
        permissions: ['money.transfers.read'],
      },
      {
        href: '/account-ledger',
        label: 'Account Balances & Ledger',
        icon: 'account',
        permissions: ['money.transactions.read'],
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
  expense: <path d="m5 12 7-7 7 7M12 5v14" />,
  income: <path d="m5 12 7 7 7-7M12 19V5" />,
  payment: <path d="M2.5 8.5h19M2.5 6.5h19v11h-19zM6 14.5h4" />,
  account: (
    <>
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M3 10h18M7 15h3" />
    </>
  ),
  pricelist: (
    <>
      <path d="M4 7h16v13H4z" />
      <path d="M8 11h8M8 15h5" />
    </>
  ),
  settings: <path d="M12 15.5A3.5 3.5 0 1 0 12 8.5a3.5 3.5 0 0 0 0 7Zm7.4-2.1 1.3 1-1.4 2.4-1.6-.6a6.7 6.7 0 0 1-1.3.75l-.2 1.7h-2.4l-.2-1.7a6.7 6.7 0 0 1-1.3-.75l-1.6.6L4.7 14.4l1.3-1a6.6 6.6 0 0 1 0-1.5l-1.3-1 1.4-2.4 1.6.6a6.7 6.7 0 0 1 1.3-.75l.2-1.7h2.4l.2 1.7a6.7 6.7 0 0 1 1.3.75l1.6-.6 1.4 2.4-1.3 1a6.6 6.6 0 0 1 0 1.5Z" />,
  number: <path d="M7 4v16M17 4v16M4 8h16M4 16h16" />,
  customer: <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />,
  supplier: <path d="M3 7h18M5 7V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v2M4 7v13h16V7M9 11h6" />,
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

type WorkspaceBranding = {
  company_name: string;
  company_logo_path: string;
  company_favicon_path: string;
};

const defaultBranding: WorkspaceBranding = {
  company_name: 'Sabuj Pran',
  company_logo_path: '/brand/company-logo.svg',
  company_favicon_path: '/brand/favicon.svg',
};

function getBrandAssetUrl(path: string): string {
  return path.startsWith('/media/') ? getApiUrl(path) : path;
}

export function useSessionProfile(): Profile | null {
  return useContext(SessionContext);
}

export function SessionShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [branding, setBranding] = useState(defaultBranding);
  const [error, setError] = useState('');
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (!profile) return;
    apiRequest<WorkspaceBranding>('/api/v1/company-settings/branding')
      .then(setBranding)
      .catch((cause: unknown) =>
        showErrorToast(
          cause instanceof Error ? cause.message : 'Could not load company branding',
        ),
      );
  }, [profile]);

  useEffect(() => {
    let icon = document.querySelector<HTMLLinkElement>('link[rel~="icon"]');
    if (!icon) {
      icon = document.createElement('link');
      icon.rel = 'icon';
      document.head.append(icon);
    }
    icon.href = getBrandAssetUrl(branding.company_favicon_path);
  }, [branding.company_favicon_path]);

  useEffect(() => {
    if (!accountMenuOpen) return;
    function handlePointerDown(event: MouseEvent) {
      if (
        accountMenuRef.current &&
        !accountMenuRef.current.contains(event.target as Node)
      ) {
        setAccountMenuOpen(false);
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setAccountMenuOpen(false);
    }
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [accountMenuOpen]);

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
            <span className="flex h-12 min-w-0 items-center">
              <Image
                src={getBrandAssetUrl(branding.company_logo_path)}
                alt={`${branding.company_name} logo`}
                width={176}
                height={44}
                unoptimized
                className="max-h-11 max-w-44 object-contain"
              />
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
          <div ref={accountMenuRef} className="relative">
            <button
              type="button"
              onClick={() => setAccountMenuOpen((open) => !open)}
              className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
              aria-expanded={accountMenuOpen}
              aria-haspopup="menu"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-sm font-semibold text-emerald-800">
                {profile.full_name.slice(0, 1).toUpperCase()}
              </span>
              <span className="hidden max-w-40 truncate sm:block">{profile.full_name}</span>
            </button>
            {accountMenuOpen && (
              <div
                role="menu"
                className="absolute right-0 top-full z-50 mt-2 w-52 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
              >
                {profile.permissions.includes('auth.profile.read') && (
                  <Link
                    href="/profile"
                    role="menuitem"
                    onClick={() => setAccountMenuOpen(false)}
                    className="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                  >
                    <AppIcon name="user" className="h-4 w-4" />
                    My Profile
                  </Link>
                )}
                {profile.permissions.includes('auth.password.change') && (
                  <Link
                    href="/change-password"
                    role="menuitem"
                    onClick={() => setAccountMenuOpen(false)}
                    className="flex items-center gap-3 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                  >
                    <AppIcon name="key" className="h-4 w-4" />
                    Change Password
                  </Link>
                )}
                {profile.permissions.includes('auth.session.logout') && (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setAccountMenuOpen(false);
                      signOut();
                    }}
                    className="flex w-full items-center gap-3 px-4 py-2 text-sm text-rose-700 hover:bg-rose-50"
                  >
                    <AppIcon name="logout" className="h-4 w-4" />
                    Sign Out
                  </button>
                )}
              </div>
            )}
          </div>
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
