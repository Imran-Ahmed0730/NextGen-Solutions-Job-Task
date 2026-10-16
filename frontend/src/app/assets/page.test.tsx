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
      'assets.read',
      'assets.create',
      'assets.update',
      'assets.delete',
      'assets.assign',
      'assets.maintain',
    ],
  }),
}));

vi.mock('@/lib/auth-api', () => ({
  apiRequest: mocks.apiRequest,
}));

vi.mock('@/lib/notifications', () => ({
  showErrorToast: mocks.showErrorToast,
  showSuccessToast: mocks.showSuccessToast,
}));

import AssetsPage from './page';

describe('AssetsPage', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.showErrorToast.mockReset();
    mocks.showSuccessToast.mockReset();
    mocks.apiRequest.mockResolvedValue([]);
  });

  it('creates an asset and reloads the asset register', async () => {
    render(<AssetsPage />);

    await screen.findByRole('heading', { name: 'Assets' });
    fireEvent.change(screen.getByRole('textbox', { name: 'Asset code' }), {
      target: { value: 'AST-001' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Asset name' }), {
      target: { value: 'Office printer' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Category' }), {
      target: { value: 'Office equipment' },
    });
    fireEvent.change(screen.getByLabelText(/Purchase date/), {
      target: { value: '2025-01-10' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Purchase cost' }), {
      target: { value: '25000.00' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Current location' }), {
      target: { value: 'Main office' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add asset' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenCalledWith(
        '/api/v1/assets',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"status":"IN_STORE"'),
        }),
      ),
    );
    expect(mocks.showSuccessToast).toHaveBeenCalledWith('Asset created.');
  });
});
