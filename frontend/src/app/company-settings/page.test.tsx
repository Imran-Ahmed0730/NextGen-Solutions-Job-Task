import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const fetchMock = vi.fn<typeof fetch>();

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/auth/session-shell', () => ({
  useSessionProfile: () => ({
    permissions: ['master_data.company_settings.update'],
  }),
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

import CompanySettingsPage from './page';

describe('CompanySettingsPage', () => {
  beforeEach(() => {
    sessionStorage.setItem('access_token', 'test-access-token');
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      const payload = url.endsWith('/api/v1/company-settings')
        ? [
            { key: 'company_name', value: 'Sabuj Pran' },
            { key: 'company_email', value: 'info@example.com' },
            { key: 'company_phone', value: '+8801726621896' },
            { key: 'company_address', value: 'Dhaka' },
            { key: 'currency_code', value: 'BDT' },
            { key: 'timezone', value: 'Asia/Dhaka' },
            { key: 'invoice_footer', value: 'Thank you' },
            { key: 'credit_limit_mode', value: 'WARN' },
            { key: 'receipt_tolerance_pct', value: '0' },
          ]
        : url.includes('/api/v1/company-settings/assets/')
          ? {
              key: 'company_logo_path',
              value: '/media/company/logo-test.png',
            }
          : JSON.parse(String(init?.body ?? '{}'));
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it('submits named company profile values instead of empty form data', async () => {
    render(<CompanySettingsPage />);

    const companyName = await screen.findByRole('textbox', { name: /company name/i });
    fireEvent.change(companyName, { target: { value: 'Updated Sabuj Pran' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Company profile' }));

    await waitFor(() => {
      const saveCall = fetchMock.mock.calls.find(([input]) =>
        String(input).endsWith('/api/v1/company-settings/company_name'),
      );
      expect(saveCall).toBeDefined();
      expect(JSON.parse(String(saveCall?.[1]?.body))).toEqual({
        key: 'company_name',
        value: 'Updated Sabuj Pran',
      });
    });
  });

  it('submits invoice footer and credit-limit settings', async () => {
    render(<CompanySettingsPage />);

    fireEvent.change(await screen.findByRole('textbox', { name: /invoice footer/i }), {
      target: { value: 'Payment due within 30 days.' },
    });
    fireEvent.change(await screen.findByRole('combobox', { name: /credit limit mode/i }), {
      target: { value: 'BLOCK' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Invoice settings' }));

    await waitFor(() => {
      const footerCall = fetchMock.mock.calls.find(([input]) =>
        String(input).endsWith('/api/v1/company-settings/invoice_footer'),
      );
      const creditLimitCall = fetchMock.mock.calls.find(([input]) =>
        String(input).endsWith('/api/v1/company-settings/credit_limit_mode'),
      );
      expect(JSON.parse(String(footerCall?.[1]?.body)).value).toBe(
        'Payment due within 30 days.',
      );
      expect(JSON.parse(String(creditLimitCall?.[1]?.body)).value).toBe('BLOCK');
    });
  });

  it('blocks invalid settings and reports field errors before making requests', async () => {
    render(<CompanySettingsPage />);

    fireEvent.change(await screen.findByRole('textbox', { name: /company name/i }), {
      target: { value: '   ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Company profile' }));

    expect(await screen.findByText('Company name is required')).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith('/api/v1/company-settings/company_name'),
      ),
    ).toBe(false);
  });

  it('uploads the selected logo file and updates its setting', async () => {
    render(<CompanySettingsPage />);

    const logoInput = await screen.findByLabelText(/company logo/i);
    const logo = new File([new Uint8Array([137, 80, 78, 71])], 'company.png', {
      type: 'image/png',
    });
    fireEvent.change(logoInput, { target: { files: [logo] } });

    await waitFor(() => {
      const uploadCall = fetchMock.mock.calls.find(([input]) =>
        String(input).endsWith('/api/v1/company-settings/assets/logo'),
      );
      expect(uploadCall?.[1]?.method).toBe('PUT');
      expect(new Headers(uploadCall?.[1]?.headers).get('Content-Type')).toBe('image/png');
      expect(uploadCall?.[1]?.body).toBe(logo);
    });
  });
});
