'use client';

import { useEffect, useState, type FormEvent } from 'react';
import Swal from 'sweetalert2';

import {
  FieldError,
  getApiFieldErrors,
  getFieldErrors,
  RequiredMark,
  type FieldErrors,
} from '@/components/forms/field-error';
import { ActionIcon, IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { partyContactSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type PartyContact = {
  id: number;
  name: string;
  phone: string | null;
  email: string | null;
  designation: string | null;
};

type PartyContactsProps = {
  partyType: 'customers' | 'suppliers';
  partyId: number;
  partyName: string;
  canCreate: boolean;
  canUpdate: boolean;
  canDelete: boolean;
};

export function PartyContacts({
  partyType,
  partyId,
  partyName,
  canCreate,
  canUpdate,
  canDelete,
}: PartyContactsProps) {
  const [contacts, setContacts] = useState<PartyContact[]>([]);
  const [editing, setEditing] = useState<PartyContact | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const endpoint = `/api/v1/${partyType}/${partyId}/contacts`;

  async function reload() {
    setContacts(await apiRequest<PartyContact[]>(endpoint));
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      showErrorToast(cause instanceof Error ? cause.message : 'Could not load contacts'),
    );
    // The endpoint is stable for this mounted party panel.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openCreateForm() {
    setErrors({});
    setEditing(null);
    setFormOpen(true);
  }

  function openEditForm(contact: PartyContact) {
    setErrors({});
    setEditing(contact);
    setFormOpen(true);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = partyContactSchema.safeParse({
      name: form.get('name'),
      phone: form.get('phone') || null,
      email: form.get('email') || null,
      designation: form.get('designation') || null,
    });
    if (!parsed.success) {
      setErrors(getFieldErrors(parsed.error.issues));
      return;
    }

    try {
      await apiRequest<PartyContact>(editing ? `${endpoint}/${editing.id}` : endpoint, {
        method: editing ? 'PATCH' : 'POST',
        body: JSON.stringify(parsed.data),
      });
      showSuccessToast(editing ? 'Contact updated.' : 'Contact added.');
      setFormOpen(false);
      setEditing(null);
      setErrors({});
      await reload();
    } catch (cause) {
      const apiErrors = getApiFieldErrors(cause);
      if (Object.keys(apiErrors).length) setErrors(apiErrors);
      else showErrorToast(cause instanceof Error ? cause.message : 'Could not save contact');
    }
  }

  async function deleteContact(contact: PartyContact) {
    const confirmation = await Swal.fire({
      title: 'Remove this contact?',
      text: `${contact.name} will be removed from ${partyName}.`,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Remove contact',
      confirmButtonColor: '#be123c',
      cancelButtonText: 'Cancel',
    });
    if (!confirmation.isConfirmed) return;

    try {
      await apiRequest<void>(`${endpoint}/${contact.id}`, { method: 'DELETE' });
      showSuccessToast('Contact removed.');
      await reload();
    } catch (cause) {
      showErrorToast(cause instanceof Error ? cause.message : 'Could not remove contact');
    }
  }

  const fieldId = (field: string) => `contact-${partyType}-${partyId}-${field}-error`;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold text-slate-900">Contacts for {partyName}</h3>
          <p className="text-sm text-slate-600">Additional people associated with this record.</p>
        </div>
        {canCreate && !formOpen && (
          <button
            type="button"
            onClick={openCreateForm}
            className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50"
          >
            <ActionIcon name="add" />
            Add contact
          </button>
        )}
      </div>

      {formOpen && (
        <form
          key={editing?.id ?? 'new-contact'}
          noValidate
          onSubmit={submit}
          className="mt-4 grid gap-3 sm:grid-cols-2"
        >
          <label className="text-sm font-medium">
            Name<RequiredMark />
            <input type="text"
              name="name"
              required
              minLength={1}
              maxLength={255}
              defaultValue={editing?.name ?? ''}
              placeholder="Contact person's name"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? fieldId('name') : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id={fieldId('name')} message={errors.name} />
          </label>
          <label className="text-sm font-medium">
            Phone
            <input
              name="phone"
              type="tel"
              inputMode="numeric"
              pattern="01[3-9][0-9]{8}"
              maxLength={11}
              defaultValue={editing?.phone ?? ''}
              placeholder="e.g. 01712345678"
              aria-invalid={Boolean(errors.phone)}
              aria-describedby={errors.phone ? fieldId('phone') : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id={fieldId('phone')} message={errors.phone} />
          </label>
          <label className="text-sm font-medium">
            Email
            <input
              name="email"
              type="email"
              maxLength={255}
              defaultValue={editing?.email ?? ''}
              placeholder="name@example.com"
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email ? fieldId('email') : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id={fieldId('email')} message={errors.email} />
          </label>
          <label className="text-sm font-medium">
            Designation
            <input type="text"
              name="designation"
              maxLength={100}
              defaultValue={editing?.designation ?? ''}
              placeholder="e.g. Purchasing Manager"
              aria-invalid={Boolean(errors.designation)}
              aria-describedby={errors.designation ? fieldId('designation') : undefined}
              className="mt-1 w-full rounded-md border px-3 py-2"
            />
            <FieldError id={fieldId('designation')} message={errors.designation} />
          </label>
          <div className="flex gap-2 sm:col-span-2">
            <button className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-3 py-2 text-sm font-medium text-white">
              <ActionIcon name="save" />
              {editing ? 'Save contact' : 'Create contact'}
            </button>
            <button
              type="button"
              onClick={() => {
                setFormOpen(false);
                setEditing(null);
                setErrors({});
              }}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <ul className="mt-4 divide-y divide-slate-100">
        {contacts.map((contact) => (
          <li key={contact.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
            <div>
              <p className="font-medium text-slate-900">
                {contact.name}
                {contact.designation && <span className="ml-2 text-sm font-normal text-slate-600">{contact.designation}</span>}
              </p>
              <p className="text-sm text-slate-600">
                {[contact.phone, contact.email].filter(Boolean).join(' · ') || 'No phone or email'}
              </p>
            </div>
            <div className="flex">
              {canUpdate && (
                <IconActionButton
                  icon="edit"
                  label={`Edit ${contact.name}`}
                  onClick={() => openEditForm(contact)}
                  className="p-2 text-emerald-800 hover:bg-emerald-50"
                />
              )}
              {canDelete && (
                <IconActionButton
                  icon="delete"
                  label={`Remove ${contact.name}`}
                  onClick={() => void deleteContact(contact)}
                  className="p-2 text-rose-700 hover:bg-rose-50"
                />
              )}
            </div>
          </li>
        ))}
        {contacts.length === 0 && (
          <li className="py-3 text-sm text-slate-500">No additional contacts recorded.</li>
        )}
      </ul>
    </section>
  );
}
