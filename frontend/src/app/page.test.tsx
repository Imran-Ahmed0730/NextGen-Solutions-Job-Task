import { render, screen } from '@testing-library/react';
import Home from './page';

describe('Home page', () => {
  it('renders the app title', () => {
    render(<Home />);

    expect(screen.getByRole('heading', { name: /business management suite/i })).toBeInTheDocument();
  });
});
