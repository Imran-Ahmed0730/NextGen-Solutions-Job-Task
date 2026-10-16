'use client';

import { useCallback, useEffect, useState, type FormEvent } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import { useSessionProfile } from '@/components/auth/session-shell';
import { RequiredMark } from '@/components/forms/field-error';
import { IconActionButton } from '@/components/ui/action-icon';
import { apiRequest } from '@/lib/auth-api';
import { approvalRuleSchema } from '@/lib/auth-validation';
import { showErrorToast, showSuccessToast } from '@/lib/notifications';

type RoleOption = { id: number; name: string };
type ApprovalRule = {
  id: number;
  doc_type: string;
  min_amount: string;
  max_amount: string | null;
  approver_role_id: number;
  approver_role: RoleOption;
  is_active: boolean;
};

function ApprovalRulesContent() {
  const permissions = useSessionProfile()?.permissions ?? [];
  const canRead = permissions.includes('approvals.rules.read');
  const canCreate = permissions.includes('approvals.rules.create');
  const canUpdate = permissions.includes('approvals.rules.update');
  const [rules, setRules] = useState<ApprovalRule[]>([]);
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [selected, setSelected] = useState<ApprovalRule | null>(null);
  const [docType, setDocType] = useState('');
  const [minAmount, setMinAmount] = useState('');
  const [maxAmount, setMaxAmount] = useState('');
  const [approverRoleId, setApproverRoleId] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    const [ruleList, roleList] = await Promise.all([
      apiRequest<ApprovalRule[]>('/api/v1/approvals/rules?include_inactive=true'),
      apiRequest<RoleOption[]>('/api/v1/approvals/rules/options/roles'),
    ]);
    setRules(ruleList);
    setRoles(roleList);
  }, []);

  useEffect(() => {
    if (!canRead) return;
    let active = true;
    setLoading(true);
    reload()
      .catch((cause: unknown) => {
        if (!active) return;
        const message = cause instanceof Error ? cause.message : 'Could not load approval rules';
        setError(message);
        showErrorToast(message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [canRead, reload]);

  function clearForm() {
    setSelected(null);
    setDocType('');
    setMinAmount('');
    setMaxAmount('');
    setApproverRoleId('');
    setError('');
  }

  function editRule(rule: ApprovalRule) {
    setSelected(rule);
    setDocType(rule.doc_type);
    setMinAmount(rule.min_amount);
    setMaxAmount(rule.max_amount ?? '');
    setApproverRoleId(String(rule.approver_role_id));
    setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = approvalRuleSchema.safeParse({
      doc_type: docType,
      min_amount: minAmount,
      max_amount: maxAmount,
      approver_role_id: Number(approverRoleId),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check the approval rule');
      return;
    }
    setError('');
    setBusy(true);
    try {
      const payload = {
        ...parsed.data,
        max_amount: parsed.data.max_amount || null,
      };
      await apiRequest<ApprovalRule>(
        selected ? `/api/v1/approvals/rules/${selected.id}` : '/api/v1/approvals/rules',
        {
          method: selected ? 'PATCH' : 'POST',
          body: JSON.stringify(payload),
        },
      );
      showSuccessToast(selected ? 'Approval rule updated.' : 'Approval rule created.');
      clearForm();
      await reload();
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not save approval rule';
      setError(message);
      showErrorToast(message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(rule: ApprovalRule) {
    setBusy(true);
    try {
      await apiRequest<ApprovalRule>(
        `/api/v1/approvals/rules/${rule.id}/${rule.is_active ? 'deactivate' : 'activate'}`,
        { method: 'POST' },
      );
      showSuccessToast(rule.is_active ? 'Approval rule deactivated.' : 'Approval rule activated.');
      await reload();
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not update approval rule';
      setError(message);
      showErrorToast(message);
    } finally {
      setBusy(false);
    }
  }

  if (!canRead) {
    return (
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">
        Your account does not have permission to view approval rules.
      </p>
    );
  }

  return (
    <main className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Approval Rules</h1>
        <p className="mt-1 text-sm text-slate-600">
          Configure non-overlapping amount ranges and the role that must approve matching documents.
        </p>
      </header>

      {error && <p role="alert" className="rounded-md bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      {(canCreate || selected && canUpdate) && (
        <form onSubmit={(event) => void submit(event)} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-medium">{selected ? 'Edit approval rule' : 'Create approval rule'}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-sm font-medium text-slate-700">
              Document type<RequiredMark />
              <input
                type="text"
                required
                maxLength={50}
                placeholder="e.g. PURCHASE_ORDER"
                value={docType}
                onChange={(event) => setDocType(event.target.value)}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Minimum amount<RequiredMark />
              <input
                type="number"
                required
                min="0"
                step="0.01"
                placeholder="e.g. 10000.00"
                value={minAmount}
                onChange={(event) => setMinAmount(event.target.value)}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Maximum amount
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="Leave blank for no upper limit"
                value={maxAmount}
                onChange={(event) => setMaxAmount(event.target.value)}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
              />
            </label>
            <label className="text-sm font-medium text-slate-700">
              Approver role<RequiredMark />
              <select
                required
                value={approverRoleId}
                onChange={(event) => setApproverRoleId(event.target.value)}
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2"
              >
                <option value="">Choose an approver role</option>
                {roles.map((role) => (
                  <option key={role.id} value={role.id}>{role.name}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={busy}
              className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {selected ? 'Save rule' : 'Create rule'}
            </button>
            {selected && (
              <button
                type="button"
                onClick={clearForm}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm"
              >
                Cancel edit
              </button>
            )}
          </div>
        </form>
      )}

      <section className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full min-w-[700px] text-left text-sm">
          <thead className="border-b bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Document type</th>
              <th className="px-4 py-3">Amount range (BDT)</th>
              <th className="px-4 py-3">Approver role</th>
              <th className="px-4 py-3">Status</th>
              {canUpdate && <th className="px-4 py-3">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">Loading rules…</td></tr>
            ) : rules.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">No approval rules configured.</td></tr>
            ) : rules.map((rule) => (
              <tr key={rule.id} className="border-b last:border-0">
                <td className="px-4 py-3 font-medium">{rule.doc_type}</td>
                <td className="px-4 py-3">
                  {rule.min_amount} – {rule.max_amount ?? 'No maximum'}
                </td>
                <td className="px-4 py-3">{rule.approver_role.name}</td>
                <td className="px-4 py-3">{rule.is_active ? 'Active' : 'Inactive'}</td>
                {canUpdate && (
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      {canUpdate && (
                        <IconActionButton
                          icon="edit"
                          label={`Edit ${rule.doc_type} approval rule`}
                          tooltip="Edit approval rule"
                          disabled={busy}
                          onClick={() => editRule(rule)}
                          className="border border-slate-300 p-2 hover:bg-slate-50"
                        />
                      )}
                      {canUpdate && (
                        <IconActionButton
                          icon={rule.is_active ? 'deactivate' : 'activate'}
                          label={`${rule.is_active ? 'Deactivate' : 'Activate'} ${rule.doc_type} approval rule`}
                          tooltip={`${rule.is_active ? 'Deactivate' : 'Activate'} approval rule`}
                          disabled={busy}
                          onClick={() => void toggleActive(rule)}
                          className="border border-slate-300 p-2 hover:bg-slate-50"
                        />
                      )}
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}

export default function ApprovalRulesPage() {
  return (
    <ProtectedPage>
      <ApprovalRulesContent />
    </ProtectedPage>
  );
}
