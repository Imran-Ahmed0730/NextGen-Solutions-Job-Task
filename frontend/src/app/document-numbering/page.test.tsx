import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  showErrorToast: vi.fn(),
  showSuccessToast: vi.fn(),
}));

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/auth/session-shell', () => ({
  useSessionProfile: () => ({
    permissions: [
      'master_data.document_numbering.read',
      'master_data.document_numbering.create',
    ],
  }),
}));

vi.mock('@/lib/auth-api', () => ({ apiRequest: mocks.apiRequest }));
vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
  showSuccessToast: mocks.showSuccessToast,
}));

import DocumentNumberingPage from './page';

describe('DocumentNumberingPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();
    mocks.apiRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (path === '/api/v1/document-numbering' && init?.method === 'POST') {
        return Promise.resolve({
          id: 1,
          doc_type: 'PAYROLL',
          prefix: 'PAY-',
          year: new Date().getFullYear(),
          last_number: 0,
          padding: 4,
        });
      }
      return Promise.resolve([]);
    });
  });

  it('shows document types by name and submits the matching internal type', async () => {
    render(<DocumentNumberingPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Add sequence' }));

    fireEvent.change(screen.getByRole('combobox', { name: /Document type/ }), {
      target: { value: 'PAYROLL' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: /Prefix/ }), {
      target: { value: 'PAY-' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Create sequence/ }));

    await waitFor(() => {
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/document-numbering',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            doc_type: 'PAYROLL',
            prefix: 'PAY-',
            year: new Date().getFullYear(),
            last_number: 0,
            padding: 4,
          }),
        }),
      );
    });
  });
});
