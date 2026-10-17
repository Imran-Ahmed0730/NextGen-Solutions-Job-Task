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

const dashboardLink = {
  href: '/',
  label: 'Dashboard',
  icon: 'grid',
  permissions: ['reports.dashboard.read'],
} as const;

const navigation = [
  {
    label: 'Sales',
    icon: 'salesGroup',
    items: [
      { href: '/quotations', label: 'Quotations', icon: 'quote', permissions: ['sales.quotations.read'] },
      { href: '/sales-orders', label: 'Sales Orders', icon: 'cart', permissions: ['sales.orders.read'] },
      { href: '/sales-invoices', label: 'Sales Invoices', icon: 'invoice', permissions: ['sales.invoices.read'] },
      { href: '/sales-returns', label: 'Sales Returns', icon: 'salesReturn', permissions: ['sales.returns.read'] },
      { href: '/customers', label: 'Customers', icon: 'customer', permissions: ['master_data.customers.read'] },
    ],
  },
  {
    label: 'Purchasing',
    icon: 'purchaseGroup',
    items: [
      { href: '/purchase-orders', label: 'Purchase Orders', icon: 'purchaseOrder', permissions: ['purchase.orders.read'] },
      { href: '/goods-receipts', label: 'Goods Receipts', icon: 'goodsReceipt', permissions: ['purchase.receipts.read'] },
      { href: '/direct-purchases', label: 'Direct Purchases', icon: 'directPurchase', permissions: ['purchase.direct_purchases.read'] },
      { href: '/purchase-returns', label: 'Purchase Returns', icon: 'purchaseReturn', permissions: ['purchase.returns.read'] },
      { href: '/suppliers', label: 'Suppliers', icon: 'supplier', permissions: ['master_data.suppliers.read'] },
    ],
  },
  {
    label: 'Money',
    icon: 'moneyGroup',
    items: [
      { href: '/customer-collections', label: 'Customer Collections', icon: 'collection', permissions: ['money.collections.read'] },
      { href: '/supplier-payments', label: 'Supplier Payments', icon: 'supplierPayment', permissions: ['money.supplier_payments.read'] },
      { href: '/expenses', label: 'Expenses', icon: 'expense', permissions: ['money.expenses.read'] },
      { href: '/incomes', label: 'Incomes', icon: 'income', permissions: ['money.incomes.read'] },
      { href: '/fund-transfers', label: 'Fund Transfers', icon: 'fundTransfer', permissions: ['money.transfers.read'] },
      { href: '/account-ledger', label: 'Account Balances & Ledger', icon: 'accountLedger', permissions: ['money.transactions.read'] },
    ],
  },
  {
    label: 'Inventory',
    icon: 'inventoryGroup',
    items: [
      { href: '/warehouse-stock', label: 'Warehouse Stock', icon: 'warehouseStock', permissions: ['inventory.stock.read'] },
      { href: '/stock-ledger', label: 'Product Stock Ledger', icon: 'stockLedger', permissions: ['inventory.stock.read'] },
      { href: '/stock-transfers', label: 'Stock Transfers', icon: 'stockTransfer', permissions: ['inventory.transfers.read'] },
      { href: '/stock-adjustments', label: 'Stock Adjustments', icon: 'stockAdjustment', permissions: ['inventory.adjustments.read'] },
      { href: '/physical-counts', label: 'Physical Count', icon: 'physicalCount', permissions: ['inventory.physical_counts.read'] },
    ],
  },
  {
    label: 'Production',
    icon: 'productionGroup',
    items: [
      { href: '/production-orders', label: 'Production Orders', icon: 'productionOrder', permissions: ['production.orders.read'] },
      { href: '/boms', label: 'Bills of Materials', icon: 'billOfMaterials', permissions: ['production.boms.read'] },
    ],
  },
  {
    label: 'Approvals',
    icon: 'approvalsGroup',
    items: [
      { href: '/pending-approvals', label: 'Pending Approvals', icon: 'pendingApproval', permissions: ['approvals.requests.read'] },
      { href: '/approval-rules', label: 'Approval Rules', icon: 'approvalRules', permissions: ['approvals.rules.read'] },
    ],
  },
  {
    label: 'Reports',
    icon: 'reportsGroup',
    items: [
      { href: '/reports', label: 'Report Center', icon: 'reportCenter', permissions: ['reports.read'] },
    ],
  },
  {
    label: 'People & Assets',
    icon: 'peopleGroup',
    items: [
      { href: '/employees', label: 'Employees', icon: 'employee', permissions: ['employees.read'] },
      { href: '/attendance', label: 'Attendance', icon: 'attendance', permissions: ['employees.attendance.read'] },
      { href: '/payroll', label: 'Payroll', icon: 'payroll', permissions: ['employees.payroll.read'] },
      { href: '/assets', label: 'Assets', icon: 'asset', permissions: ['assets.read'] },
    ],
  },
  {
    label: 'Setup',
    icon: 'setupGroup',
    items: [
      { href: '/products', label: 'Products', icon: 'product', permissions: ['master_data.products.read'] },
      { href: '/categories', label: 'Product Categories', icon: 'productCategory', permissions: ['master_data.product_categories.read'] },
      { href: '/units', label: 'Units', icon: 'unit', permissions: ['master_data.units.read'] },
      { href: '/warehouses', label: 'Warehouses', icon: 'warehouseSetup', permissions: ['master_data.warehouses.read'] },
      { href: '/price-lists', label: 'Price Lists', icon: 'priceList', permissions: ['master_data.price_lists.read'] },
      { href: '/expense-categories', label: 'Expense Categories', icon: 'expenseCategory', permissions: ['master_data.expense_categories.read'] },
      { href: '/income-categories', label: 'Income Categories', icon: 'incomeCategory', permissions: ['master_data.income_categories.read'] },
      { href: '/payment-methods', label: 'Payment Methods', icon: 'paymentMethod', permissions: ['master_data.payment_methods.read'] },
      { href: '/money-accounts', label: 'Money Accounts', icon: 'moneyAccount', permissions: ['master_data.money_accounts.read'] },
      { href: '/company-settings', label: 'Company Settings', icon: 'companySettings', permissions: ['master_data.company_settings.read'] },
      { href: '/document-numbering', label: 'Document Numbering', icon: 'documentNumbering', permissions: ['master_data.document_numbering.read'] },
    ],
  },
  {
    label: 'Administration',
    icon: 'adminGroup',
    items: [
      { href: '/users', label: 'Users', icon: 'users', permissions: ['auth.users.read'] },
      { href: '/roles', label: 'Roles', icon: 'role', permissions: ['auth.roles.read', 'auth.permissions.read'] },
      { href: '/permissions', label: 'Permissions', icon: 'permission', permissions: ['auth.permissions.read'] },
      { href: '/audit-logs', label: 'Audit Log', icon: 'auditLog', permissions: ['auth.audit_logs.read'] },
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
  salesGroup: <path d="M3 7h18M5 7l1.5 13h11L19 7M9 11v5m6-5v5M8 4h8" />,
  purchaseGroup: <path d="M4 8h16l-1 12H5L4 8Zm4 0a4 4 0 0 1 8 0M8 12h8" />,
  moneyGroup: <path d="M3 6h18v12H3zM7 10h.01M17 14h.01M10 12a2 2 0 1 0 4 0 2 2 0 0 0-4 0Z" />,
  approvalsGroup: <path d="M9 12.5 11 14.5 16 9.5M12 3l8 3v5.5c0 4.3-3.3 7.3-8 9-4.7-1.7-8-4.7-8-9V6l8-3Z" />,
  inventoryGroup: <path d="m3 7 9-4 9 4-9 4-9-4Zm0 0v10l9 4 9-4V7M12 11v10" />,
  productionGroup: <path d="M3 21V9l6 3V9l6 3V5h6v16H3Zm12-12h2m-2 4h2m-2 4h2" />,
  reportsGroup: <path d="M4 19V5m0 14h17M7 15l4-4 3 2 5-6M16 7h3v3" />,
  peopleGroup: <path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2m6-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm8-7.5a3 3 0 0 1 0 5.8m1 4c2 .5 3 1.9 3 4.2" />,
  setupGroup: <path d="M12 8v8m-4-4h8M4 4h16v16H4zM2 8h2m16 0h2M2 16h2m16 0h2" />,
  adminGroup: <path d="M12 3 20 7v5c0 4-3 7-8 9-5-2-8-5-8-9V7l8-4Zm-3 8h6m-3-3v6" />,
  quote: <path d="M7 17H4v-5c0-4 2-6 6-6v3c-2 0-3 1-3 3h3v5H7Zm10 0h-3v-5c0-4 2-6 6-6v3c-2 0-3 1-3 3h3v5h-3Z" />,
  cart: <path d="M3 4h2l2.2 11.2a2 2 0 0 0 2 1.6h7.6a2 2 0 0 0 1.9-1.4L21 8H6m4 12h.01M17 20h.01" />,
  invoice: <path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Zm3 5h6m-6 4h6m-6 4h3" />,
  salesReturn: <path d="M9 14 4 9l5-5M4 9h10a6 6 0 0 1 0 12h-2" />,
  purchaseOrder: <path d="M5 3h14v18l-3-2-4 2-4-2-3 2V3Zm3 5h8m-8 4h8m-8 4h4" />,
  goodsReceipt: <path d="M3 12h12m-5-5 5 5-5 5m6-13h4v16h-4" />,
  directPurchase: <path d="m13 2-9 12h7l-1 8 10-13h-7l1-7Z" />,
  purchaseReturn: <path d="M15 14 20 9l-5-5m5 5H10a6 6 0 0 0 0 12h2" />,
  collection: <path d="M3 12h13m-5-5 5 5-5 5M17 5h4v14h-4" />,
  supplierPayment: <path d="M12 2v20m5-16H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />,
  fundTransfer: <path d="M7 7h13l-3-3m3 3-3 3M17 17H4l3 3m-3-3 3-3" />,
  accountLedger: <path d="M5 3h14v18H5zM8 7h8m-8 4h8m-8 4h5m-5 3h8" />,
  warehouseStock: <path d="m3 9 9-6 9 6v12H3V9Zm0 0h18M8 21v-7h8v7" />,
  stockLedger: <path d="M5 4h14v16H5zM8 8h8m-8 4h8m-8 4h5" />,
  stockTransfer: <path d="M4 7h14l-3-3m3 3-3 3M20 17H6l3 3m-3-3 3-3" />,
  stockAdjustment: <path d="M4 6h16M4 12h16M4 18h16M8 3v6m8 0V3m-4 6v6m4 0v6" />,
  physicalCount: <path d="M8 4h8l2 3h3v14H3V7h3l2-3Zm1 10 2 2 5-5" />,
  productionOrder: <path d="M3 20V9l5 3V9l5 3V5h8v15H3Zm12-10h2m-2 4h2" />,
  billOfMaterials: <path d="M12 3v6m0 0-6 4m6-4 6 4M6 13v6m12-6v6M4 19h4m8 0h4M10 3h4" />,
  reportCenter: <path d="M4 19V5m0 14h17M7 15l4-4 3 2 5-6" />,
  employee: <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 9a7 7 0 0 1 14 0H5Zm14-13h3m-1.5-1.5v3" />,
  attendance: <path d="M4 5h16v16H4zM8 3v4m8-4v4M4 9h16m3 5h-6v6" />,
  payroll: <path d="M4 4h16v16H4zM8 8h8m-8 4h8m-8 4h4m7-2 2 2 3-4" />,
  asset: <path d="M4 8 12 3l8 5v9l-8 4-8-4V8Zm0 0 8 5 8-5m-8 5v8m-4-12 8-5" />,
  product: <path d="m3 7 9-4 9 4-9 4-9-4Zm0 0v10l9 4 9-4V7m-9 4v10m-5-8 10-5" />,
  productCategory: <path d="M3 5h7l2 2h9v12H3V5Zm3 7h12m-12 4h8" />,
  unit: <path d="M3 17 17 3l4 4L7 21H3v-4Zm4-4 4 4m-1-9 4 4m-1-9 4 4" />,
  warehouseSetup: <path d="m3 10 9-7 9 7v11H3V10Zm5 11v-7h8v7m-8-11h8" />,
  priceList: <path d="M4 4h16v16H4zM8 8h8m-8 4h8m-8 4h4m8-9-8 9" />,
  expenseCategory: <path d="M4 4h16v16H4zM8 8h8m-8 4h5m-5 4h3m6-4 2 2-2 2" />,
  incomeCategory: <path d="M4 20V4m0 16h16M7 16l4-4 3 2 5-7m-4 0h4v4" />,
  paymentMethod: <path d="M3 6h18v12H3zM3 10h18m-13 4h4m5 2h.01" />,
  moneyAccount: <path d="M3 7h18v12H3zM7 7V5h10v2m-7 5h4m-7 3h10" />,
  companySettings: <path d="M4 21V4h16v17M8 8h2m4 0h2m-8 4h2m4 0h2m-8 9v-5h8v5M2 21h20" />,
  documentNumbering: <path d="M7 3h10v18H7zM4 7H2m2 5H2m2 5H2m7-9h4m-4 4h4m-4 4h4" />,
  pendingApproval: <path d="M12 3v9l6 3m2-3a8 8 0 1 1-2.3-5.7M12 3a9 9 0 0 1 8.7 6.5" />,
  approvalRules: <path d="M4 6h16M4 12h16M4 18h16M8 4v4m8 2v4m-5 2v4" />,
  role: <path d="M12 3 20 7v5c0 4-3 7-8 9-5-2-8-5-8-9V7l8-4Zm-3 8h6m-3-3v6" />,
  permission: <path d="M5 4h14v16H5zM8 8h8m-8 4h8m-8 4h3m4-1 1.5 1.5L19 13" />,
  auditLog: <path d="M4 5h16v15H4zM8 3v4m8-4v4M4 9h16m-12 4h8m-8 3h5" />,
  chevron: <path d="m9 18 6-6-6-6" />,
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
  if (isNavigationItemActive(dashboardLink.href, pathname)) return dashboardLink.label;
  for (const group of navigation) {
    const item = group.items.find((entry) => isNavigationItemActive(entry.href, pathname));
    if (item) return item.label;
  }
  return 'Sabuj Pran';
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
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const activeGroup = navigation.find((group) =>
      group.items.some((item) => isNavigationItemActive(item.href, pathname)),
    );
    if (activeGroup) {
      setExpandedGroups((current) => ({ ...current, [activeGroup.label]: true }));
    }
  }, [pathname]);

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
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-200 bg-white transition-transform duration-200 print:hidden lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0 ${
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

        <nav aria-label="Main navigation" className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {dashboardLink.permissions.every((permission) =>
            profile.permissions.includes(permission),
          ) && (
            <Link
              href={dashboardLink.href}
              aria-current={isNavigationItemActive(dashboardLink.href, pathname) ? 'page' : undefined}
              onClick={() => setMobileNavigationOpen(false)}
              className={`mb-2 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                isNavigationItemActive(dashboardLink.href, pathname)
                  ? 'bg-emerald-50 font-semibold text-emerald-800'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              <AppIcon name={dashboardLink.icon} className="h-[18px] w-[18px] shrink-0" />
              {dashboardLink.label}
            </Link>
          )}
          {navigation.map((group) => {
            const items = group.items.filter((item) =>
              item.permissions.every((permission) => profile.permissions.includes(permission)),
            );
            if (!items.length) return null;
            const expanded = expandedGroups[group.label] ?? false;
            const active = items.some((item) => isNavigationItemActive(item.href, pathname));
            const groupId = `navigation-${group.label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
            return (
              <section key={group.label}>
                <button
                  type="button"
                  aria-expanded={expanded}
                  aria-controls={groupId}
                  onClick={() =>
                    setExpandedGroups((current) => ({
                      ...current,
                      [group.label]: !expanded,
                    }))
                  }
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                    active
                      ? 'font-semibold text-emerald-800'
                      : 'font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  <AppIcon name={group.icon} className="h-[18px] w-[18px] shrink-0" />
                  <span className="flex-1 text-left">{group.label}</span>
                  <AppIcon
                    name="chevron"
                    className={`h-4 w-4 shrink-0 transition-transform ${
                      expanded ? 'rotate-90' : ''
                    }`}
                  />
                </button>
                <div
                  id={groupId}
                  hidden={!expanded}
                  className="ml-4 mt-1 space-y-1 border-l border-slate-200 pl-3"
                >
                  {items.map((item) => {
                    const current = isNavigationItemActive(item.href, pathname);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        aria-current={current ? 'page' : undefined}
                        onClick={() => setMobileNavigationOpen(false)}
                        className={`flex items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-colors ${
                          current
                            ? 'bg-emerald-50 font-semibold text-emerald-800'
                            : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                        }`}
                      >
                        <AppIcon name={item.icon} className="h-4 w-4 shrink-0" />
                        <span className="flex-1">{item.label}</span>
                        {current && (
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />
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
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur print:hidden sm:px-6">
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
          <main className="mx-auto w-full max-w-[1600px] flex-1 p-4 print:max-w-none print:p-0 sm:p-6 lg:p-8">
            {children}
          </main>
        </SessionContext.Provider>
      </div>
    </div>
  );
}
