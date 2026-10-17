import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  pathname: '/sales-orders',
  replace: vi.fn(),
}));

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock('next/image', () => ({
  default: ({ alt, src }: { alt?: string; src: string }) => (
    <span aria-label={alt}>{src}</span>
  ),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({ replace: mocks.replace }),
}));

vi.mock('@/lib/auth-api', () => ({
  ApiError: class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  apiRequest: mocks.apiRequest,
  clearSession: vi.fn(),
  getApiUrl: (path: string) => `http://localhost:8000${path}`,
}));

vi.mock('@/lib/notifications', () => ({ showErrorToast: vi.fn() }));

import { SessionShell } from './session-shell';

describe('SessionShell navigation', () => {
  beforeEach(() => {
    mocks.pathname = '/sales-orders';
    mocks.replace.mockReset();
    mocks.apiRequest.mockReset();
    sessionStorage.setItem('access_token', 'test-access-token');
    mocks.apiRequest.mockImplementation((path: string) => {
      if (path === '/api/v1/auth/me') {
        return Promise.resolve({
          id: 1,
          username: 'admin',
          email: null,
          mobile: null,
          full_name: 'Administrator',
          roles: ['Administrator'],
          permissions: [
            'reports.dashboard.read',
            'sales.quotations.read',
            'sales.orders.read',
            'sales.invoices.read',
            'sales.returns.read',
            'master_data.customers.read',
            'purchase.orders.read',
            'purchase.receipts.read',
            'purchase.direct_purchases.read',
            'purchase.returns.read',
            'master_data.suppliers.read',
            'money.collections.read',
            'money.supplier_payments.read',
            'money.expenses.read',
            'money.incomes.read',
            'money.transfers.read',
            'money.transactions.read',
            'approvals.requests.read',
            'approvals.rules.read',
            'inventory.stock.read',
            'inventory.transfers.read',
            'inventory.adjustments.read',
            'inventory.physical_counts.read',
            'production.orders.read',
            'production.boms.read',
            'reports.read',
            'employees.read',
            'employees.attendance.read',
            'employees.payroll.read',
            'assets.read',
            'master_data.products.read',
            'master_data.product_categories.read',
            'master_data.units.read',
            'master_data.warehouses.read',
            'master_data.price_lists.read',
            'master_data.expense_categories.read',
            'master_data.income_categories.read',
            'master_data.payment_methods.read',
            'master_data.money_accounts.read',
            'master_data.company_settings.read',
            'master_data.document_numbering.read',
            'auth.users.read',
            'auth.roles.read',
            'auth.permissions.read',
            'auth.audit_logs.read',
          ],
        });
      }
      return Promise.resolve({
        company_name: 'Sabuj Pran',
        company_logo_path: '/brand/company-logo.svg',
        company_favicon_path: '/brand/favicon.svg',
      });
    });
  });

  it('orders menus by daily workflow and expands the current group', async () => {
    render(
      <SessionShell>
        <div>Page content</div>
      </SessionShell>,
    );

    const nav = await screen.findByRole('navigation', { name: 'Main navigation' });
    const menuLabels = within(nav)
      .getAllByRole('button')
      .map((button) => button.textContent?.trim());

    expect(menuLabels.slice(0, 3)).toEqual(['Sales', 'Purchasing', 'Money']);
    expect(within(nav).getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/');
    expect(within(nav).getByRole('link', { name: 'Sales Orders' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(nav).getByRole('button', { name: /Sales/ })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('uses distinct group icons and toggles submenu items with the chevron control', async () => {
    render(
      <SessionShell>
        <div>Page content</div>
      </SessionShell>,
    );

    const nav = await screen.findByRole('navigation', { name: 'Main navigation' });
    const groupButtons = within(nav).getAllByRole('button');
    const groupIconMarkup = groupButtons.map((button) =>
      button.querySelector('svg')?.innerHTML,
    );
    expect(new Set(groupIconMarkup).size).toBe(groupIconMarkup.length);

    const purchasing = within(nav).getByRole('button', { name: /Purchasing/ });
    expect(
      document.getElementById(purchasing.getAttribute('aria-controls') ?? ''),
    ).toBeInTheDocument();
    expect(purchasing).toHaveAttribute('aria-expanded', 'false');
    expect(within(nav).queryByRole('link', { name: 'Purchase Orders' })).not.toBeInTheDocument();

    fireEvent.click(purchasing);
    expect(within(nav).getByRole('button', { name: /Purchasing/ })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    expect(within(nav).getByRole('link', { name: 'Purchase Orders' })).toBeInTheDocument();
    const linkIcons = within(nav)
      .getAllByRole('link')
      .map((link) => link.querySelector('svg')?.innerHTML);
    expect(new Set(linkIcons).size).toBe(linkIcons.length);

    fireEvent.click(within(nav).getByRole('button', { name: /Purchasing/ }));
    expect(within(nav).getByRole('button', { name: /Purchasing/ })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    expect(within(nav).queryByRole('link', { name: 'Purchase Orders' })).not.toBeInTheDocument();
  });
});
