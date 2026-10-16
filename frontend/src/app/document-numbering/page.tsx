'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Swal from 'sweetalert2';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import {
  FieldError,
  getApiFieldErrors,
  getFieldErrors,
  RequiredMark,
  type FieldErrors,
} from '@/components/forms/field-error';
import { ActionIcon, IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';
import { documentNumberingSchema } from '@/lib/auth-validation';

type SequenceRecord = {
  id: number;
  doc_type: string;
  prefix: string;
  year: number;
  last_number: number;
  padding: number;
};

function DocumentNumberingContent() {
  const profile = useSessionProfile();
  const [sequences, setSequences] = useState<SequenceRecord[]>([]);
  const [selected, setSelected] = useState<SequenceRecord | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  async function reload() {
    setSequences(await apiRequest<SequenceRecord[]>('/api/v1/document-numbering'));
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load document numbering'),
    );
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = documentNumberingSchema.safeParse({
      doc_type: form.get('doc_type'),
      prefix: form.get('prefix'),
      year: form.get('year'),
      last_number: form.get('last_number'),
      padding: form.get('padding'),
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }
    setErrors({});

    try {
      await apiRequest<SequenceRecord>(
        selected ? `/api/v1/document-numbering/${selected.id}` : '/api/v1/document-numbering',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(parsed.data),
        },
      );
      showSuccessToast(selected ? 'Sequence updated.' : 'Sequence created.');
      setSelected(null);
      setIsFormOpen(false);
      await reload();
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save sequence');
    }
  }

  async function deleteSequence(sequence: SequenceRecord) {
    const confirmation = await Swal.fire({
      title: 'Delete sequence?',
      text: `Are you sure you want to delete "${sequence.doc_type} ${sequence.year}"?`,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonColor: '#b91c1c',
      cancelButtonColor: '#64748b',
      confirmButtonText: 'Yes, delete',
    });
    if (!confirmation.isConfirmed) return;
    try {
      await apiRequest<void>(`/api/v1/document-numbering/${sequence.id}`, { method: 'DELETE' });
      showSuccessToast('Sequence deleted.');
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not delete sequence');
    }
  }

  function preview(sequence: SequenceRecord): string {
    const next = sequence.last_number + 1;
    return `${sequence.prefix}${sequence.year}${String(next).padStart(sequence.padding, '0')}`;
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Document Numbering</h1>
          <p className="mt-1 text-sm text-slate-600">
            Set the format the system uses to number documents when they are posted.
          </p>
        </div>
        {profile?.permissions.includes('master_data.document_numbering.create') && !isFormOpen && (
          <button
            type="button"
            onClick={() => {
              setErrors({});
              setSelected(null);
              setIsFormOpen(true);
            }}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-emerald-800"
          >
            <ActionIcon name="add" />
            Add sequence
          </button>
        )}
      </div>

      {isFormOpen && (
        <form
          key={selected?.id ?? 'new-document-sequence'}
          noValidate
          className="mt-6 grid max-w-3xl gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2"
          onSubmit={submit}
        >
          <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950 sm:col-span-2">
            <p className="font-semibold">How document numbering works</p>
            <p className="mt-1">
              Create one sequence for each document type and year. The type must match the
              document being posted—for example, use <span className="font-semibold">PAYROLL</span>{' '}
              for payroll runs. The system combines the prefix, year, and next number. With prefix
              <span className="font-mono"> PAY-</span>, year <span className="font-mono">2026</span>,
              last number <span className="font-mono">0</span>, and padding{' '}
              <span className="font-mono">4</span>, the first number will be{' '}
              <span className="font-mono font-semibold">PAY-20260001</span>.
            </p>
            <p className="mt-1">
              Set last number to <span className="font-semibold">0</span> to start fresh, or to the
              last number already used if continuing an existing series.
            </p>
          </div>

          <label className="block text-sm font-medium">
            Document type<RequiredMark />
            <input type="text"
              name="doc_type"
              placeholder="e.g. INVOICE"
              defaultValue={selected?.doc_type ?? ''}
              maxLength={50}
              required
              readOnly={selected !== null}
              aria-invalid={Boolean(errors.doc_type)}
              aria-describedby={errors.doc_type ? 'doc-type-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              list="document-type-options"
            />
            <datalist id="document-type-options">
              <option value="CUSTOMER_COLLECTION" label="Customer collection" />
              <option value="DELIVERY" label="Sales delivery" />
              <option value="DIRECT_PURCHASE" label="Direct purchase" />
              <option value="EXPENSE" label="Expense" />
              <option value="FUND_TRANSFER" label="Fund transfer" />
              <option value="GOODS_RECEIPT" label="Goods receipt" />
              <option value="INCOME" label="Income" />
              <option value="INVOICE" label="Sales invoice" />
              <option value="PAYROLL" label="Payroll run" />
              <option value="PHYSICAL_COUNT" label="Physical stock count" />
              <option value="PRODUCTION_ORDER" label="Production order" />
              <option value="PURCHASE_ORDER" label="Purchase order" />
              <option value="PURCHASE_RETURN" label="Purchase return" />
              <option value="QUOTATION" label="Quotation" />
              <option value="SALES_ORDER" label="Sales order" />
              <option value="SALES_RETURN" label="Sales return" />
              <option value="STOCK_ADJUSTMENT" label="Stock adjustment" />
              <option value="STOCK_TRANSFER" label="Stock transfer" />
              <option value="SUPPLIER_PAYMENT" label="Supplier payment" />
            </datalist>
            <span className="mt-1 block text-xs font-normal text-slate-500">
              Start typing to see supported document types, then choose the matching type.
            </span>
            <FieldError id="doc-type-error" message={errors.doc_type} />
          </label>

          <label className="block text-sm font-medium">
            Prefix<RequiredMark />
            <input type="text"
              name="prefix"
              placeholder="e.g. INV-"
              defaultValue={selected?.prefix ?? ''}
              maxLength={30}
              required
              aria-invalid={Boolean(errors.prefix)}
              aria-describedby={errors.prefix ? 'prefix-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <span className="mt-1 block text-xs font-normal text-slate-500">
              Text placed before the year and number, e.g. PAY-.
            </span>
            <FieldError id="prefix-error" message={errors.prefix} />
          </label>

          <label className="block text-sm font-medium">
            Year<RequiredMark />
            <input
              name="year"
              type="number"
              min={1900}
              max={9999}
              defaultValue={selected?.year ?? new Date().getFullYear()}
              required
              placeholder="e.g. 2026"
              aria-invalid={Boolean(errors.year)}
              aria-describedby={errors.year ? 'year-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <span className="mt-1 block text-xs font-normal text-slate-500">
              The document year; each year has its own sequence.
            </span>
            <FieldError id="year-error" message={errors.year} />
          </label>

          <label className="block text-sm font-medium">
            Last number<RequiredMark />
            <input
              name="last_number"
              type="number"
              min={0}
              defaultValue={selected?.last_number ?? 0}
              required
              placeholder="0"
              aria-invalid={Boolean(errors.last_number)}
              aria-describedby={errors.last_number ? 'last-number-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <span className="mt-1 block text-xs font-normal text-slate-500">
              Most recent number already used; use 0 for a new series.
            </span>
            <FieldError id="last-number-error" message={errors.last_number} />
          </label>

          <label className="block text-sm font-medium">
            Padding<RequiredMark />
            <input
              name="padding"
              type="number"
              min={1}
              max={10}
              defaultValue={selected?.padding ?? 4}
              required
              placeholder="e.g. 4"
              aria-invalid={Boolean(errors.padding)}
              aria-describedby={errors.padding ? 'padding-error' : undefined}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
            />
            <span className="mt-1 block text-xs font-normal text-slate-500">
              Minimum digits for the number part; 4 makes 1 display as 0001.
            </span>
            <FieldError id="padding-error" message={errors.padding} />
          </label>

          <div className="flex gap-3 self-end sm:col-span-2">
            <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 font-medium text-white shadow-sm hover:bg-emerald-800">
              <ActionIcon name="save" />
              {selected ? 'Save sequence' : 'Create sequence'}
            </button>
            <button
              type="button"
              onClick={() => {
                setSelected(null);
                setIsFormOpen(false);
              }}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="mt-6 overflow-x-auto rounded-lg border border-slate-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Prefix</th>
              <th className="px-4 py-3">Year</th>
              <th className="px-4 py-3">Last number</th>
              <th className="px-4 py-3">Next number</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sequences.map((sequence) => (
              <tr key={sequence.id} className="hover:bg-slate-50/60">
                <td className="px-4 py-3 font-medium text-slate-900">{sequence.doc_type}</td>
                <td className="px-4 py-3 text-slate-600">{sequence.prefix}</td>
                <td className="px-4 py-3 text-slate-600">{sequence.year}</td>
                <td className="px-4 py-3 text-slate-600">{sequence.last_number}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-800">{preview(sequence)}</td>
                <td className="px-4 py-3">
                  {profile?.permissions.includes('master_data.document_numbering.update') && (
                    <IconActionButton
                      icon="edit"
                      label={`Edit ${sequence.doc_type}`}
                      onClick={() => {
                        setErrors({});
                        setSelected(sequence);
                        setIsFormOpen(true);
                      }}
                      className="mr-1 p-2 text-emerald-800 hover:bg-emerald-50"
                    />
                  )}
                  {profile?.permissions.includes('master_data.document_numbering.delete') && (
                    <IconActionButton
                      icon="delete"
                      label={`Delete ${sequence.doc_type}`}
                      onClick={() => void deleteSequence(sequence)}
                      className="p-2 text-rose-700 hover:bg-rose-50"
                    />
                  )}
                </td>
              </tr>
            ))}
            {sequences.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No sequences yet. Add one for each document type and year before posting, such as
                  PAYROLL for payroll runs.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function DocumentNumberingPage() {
  return (
    <ProtectedPage>
      <DocumentNumberingContent />
    </ProtectedPage>
  );
}