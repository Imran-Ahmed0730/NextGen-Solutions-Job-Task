import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { vi } from 'vitest';

vi.mock('@/components/auth/protected-page', () => ({
  ProtectedPage: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
import Home from './page';

describe('Home page', () => {
  it('renders the app title', () => {
    render(<Home />);

    expect(screen.getByRole('heading', { name: /business management suite/i })).toBeInTheDocument();
  });
});
