'use client';

import { useId, useMemo, useState, type KeyboardEvent } from 'react';

export type SearchableSelectOption = {
  value: string;
  label: string;
  searchText?: string;
};

type SearchableSelectProps = {
  options: SearchableSelectOption[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  'aria-label': string;
  'aria-invalid'?: boolean;
  'aria-describedby'?: string;
  name?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
};

export function SearchableSelect({
  options,
  value,
  defaultValue = '',
  onChange,
  'aria-label': ariaLabel,
  'aria-invalid': ariaInvalid,
  'aria-describedby': ariaDescribedBy,
  name,
  placeholder = 'Search or select...',
  required = false,
  disabled = false,
  className = '',
}: SearchableSelectProps) {
  const listboxId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(-1);
  const [internalValue, setInternalValue] = useState(defaultValue);
  const selectedValue = value ?? internalValue;
  const selected = options.find((option) => option.value === selectedValue);
  const filteredOptions = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return options;
    return options.filter((option) =>
      `${option.label} ${option.searchText ?? ''}`.toLowerCase().includes(normalizedQuery),
    );
  }, [options, query]);

  function closeList() {
    setOpen(false);
    setQuery('');
    setActiveIndex(-1);
  }

  function selectOption(option: SearchableSelectOption) {
    setInternalValue(option.value);
    onChange?.(option.value);
    closeList();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) =>
        current < 0 ? 0 : Math.min(current + 1, filteredOptions.length - 1),
      );
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) =>
        current < 0 ? filteredOptions.length - 1 : Math.max(current - 1, 0),
      );
    } else if (event.key === 'Enter' && open && filteredOptions[activeIndex]) {
      event.preventDefault();
      selectOption(filteredOptions[activeIndex]);
    } else if (event.key === 'Escape') {
      closeList();
    }
  }

  return (
    <div className="relative">
      <input
        type="text"
        role="combobox"
        aria-label={ariaLabel}
        aria-invalid={ariaInvalid}
        aria-describedby={ariaDescribedBy}
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-haspopup="listbox"
        aria-activedescendant={
          open && activeIndex >= 0 && filteredOptions[activeIndex]
            ? `${listboxId}-option-${activeIndex}`
            : undefined
        }
        aria-required={required}
        autoComplete="off"
        disabled={disabled}
        value={open ? query : selected?.label ?? ''}
        placeholder={placeholder}
        onFocus={() => {
          if (disabled) return;
          setOpen(true);
          setQuery('');
          setActiveIndex(-1);
        }}
        onBlur={() => {
          window.setTimeout(() => closeList(), 100);
        }}
        onChange={(event) => {
          const nextQuery = event.target.value;
          const exactValue = options.find((option) => option.value === nextQuery);
          if (exactValue) {
            selectOption(exactValue);
            return;
          }
          if (selected && nextQuery !== selected.label) {
            setInternalValue('');
            onChange?.('');
          }
          setQuery(nextQuery);
          setOpen(true);
          setActiveIndex(-1);
        }}
        onKeyDown={handleKeyDown}
        className={`min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-600/20 disabled:cursor-not-allowed disabled:bg-slate-100 ${selected && !required ? 'pr-8' : ''} ${className}`}
      />
      {selected && !required && (
        <button
          type="button"
          aria-label={`Clear ${ariaLabel}`}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            setInternalValue('');
            onChange?.('');
            closeList();
          }}
          className="absolute inset-y-0 right-2 flex items-center px-1 text-lg leading-none text-slate-500 hover:text-slate-900"
        >
          <span aria-hidden="true">×</span>
        </button>
      )}
      {open && !disabled && (
        <ul
          id={listboxId}
          role="listbox"
          aria-label={`${ariaLabel} options`}
          className="absolute z-30 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {filteredOptions.length > 0 ? (
            filteredOptions.map((option, index) => (
              <li
                key={option.value}
                id={`${listboxId}-option-${index}`}
                role="option"
                aria-selected={option.value === selectedValue}
                className={`cursor-pointer px-3 py-2 text-sm ${
                  index === activeIndex ? 'bg-emerald-50 text-emerald-900' : 'text-slate-700'
                }`}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => selectOption(option)}
              >
                {option.label}
              </li>
            ))
          ) : (
            <li className="px-3 py-2 text-sm text-slate-500">No matching options.</li>
          )}
        </ul>
      )}
      {(required || name) && (
        <select
          aria-hidden="true"
          tabIndex={-1}
          required={required}
          name={name}
          value={selectedValue}
          onChange={(event) => {
            setInternalValue(event.target.value);
            onChange?.(event.target.value);
          }}
          className="sr-only"
        >
          <option value="">{placeholder}</option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
