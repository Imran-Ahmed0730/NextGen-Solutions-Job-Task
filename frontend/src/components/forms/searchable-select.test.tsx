import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SearchableSelect } from './searchable-select';

const options = [
  { value: '1', label: 'North Warehouse (NORTH)' },
  { value: '2', label: 'South Warehouse (SOUTH)' },
];

describe('SearchableSelect', () => {
  it('filters options by searchable label and selects the matching item', () => {
    const onChange = vi.fn();
    render(
      <SearchableSelect
        aria-label="Warehouse"
        options={options}
        value=""
        onChange={onChange}
      />,
    );

    const combo = screen.getByRole('combobox', { name: 'Warehouse' });
    fireEvent.change(combo, { target: { value: 'south' } });
    fireEvent.click(screen.getByRole('option', { name: 'South Warehouse (SOUTH)' }));

    expect(onChange).toHaveBeenCalledWith('2');
  });

  it('supports selecting the active option with the keyboard', () => {
    const onChange = vi.fn();
    render(
      <SearchableSelect
        aria-label="Warehouse"
        options={options}
        value=""
        onChange={onChange}
      />,
    );

    const combo = screen.getByRole('combobox', { name: 'Warehouse' });
    fireEvent.focus(combo);
    fireEvent.keyDown(combo, { key: 'ArrowDown' });
    fireEvent.keyDown(combo, { key: 'Enter' });

    expect(onChange).toHaveBeenCalledWith('1');
  });

  it('keeps the selected identifier in native form data', () => {
    render(
      <form data-testid="form">
        <SearchableSelect
          aria-label="Warehouse"
          name="warehouse_id"
          options={options}
          value="2"
          onChange={vi.fn()}
          required
        />
      </form>,
    );

    const form = screen.getByTestId('form') as HTMLFormElement;
    expect(new FormData(form).get('warehouse_id')).toBe('2');
  });

  it('allows optional selections to be cleared', () => {
    const onChange = vi.fn();
    render(
      <SearchableSelect
        aria-label="Warehouse"
        options={options}
        value="2"
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Clear Warehouse' }));

    expect(onChange).toHaveBeenCalledWith('');
  });
});
