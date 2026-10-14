import { ApiError } from '@/lib/auth-api';

type ValidationIssue = { path: PropertyKey[]; message: string };

export type FieldErrors = Record<string, string>;

export function getFieldErrors(issues: readonly ValidationIssue[]): FieldErrors {
  const errors: FieldErrors = {};
  for (const issue of issues) {
    const field = issue.path.join('.');
    if (field && !errors[field]) errors[field] = issue.message;
  }
  return errors;
}

export function getApiFieldErrors(cause: unknown): FieldErrors {
  if (!(cause instanceof ApiError)) return {};

  const duplicate = cause.message.match(
    /^(username|email|mobile|role name|unit code|product sku|customer code|supplier code) is already in use$/i,
  );
  if (cause.status === 409 && duplicate) {
    const field = duplicate[1]
      .toLowerCase()
      .replace('role name', 'name')
      .replace('unit code', 'code')
      .replace('product sku', 'sku')
      .replace('customer code', 'code')
      .replace('supplier code', 'code');
    return { [field]: `${duplicate[1]} is already in use` };
  }
  if (/^current password is incorrect$/i.test(cause.message)) {
    return { current_password: cause.message };
  }
  if (/^new password must be different$/i.test(cause.message)) {
    return { new_password: cause.message };
  }

  if (cause.status !== 422) return {};
  try {
    const details: unknown = JSON.parse(cause.message);
    if (!Array.isArray(details)) return {};
    const errors: FieldErrors = {};
    for (const issue of details) {
      if (
        typeof issue === 'object' &&
        issue !== null &&
        'loc' in issue &&
        Array.isArray(issue.loc) &&
        typeof issue.msg === 'string'
      ) {
        const field = issue.loc.at(-1);
        if (typeof field === 'string' && field !== 'body' && !errors[field]) {
          errors[field] = issue.msg.replace(/^Value error,\s*/i, '');
        }
      }
    }
    return errors;
  } catch {
    return {};
  }
}

export function RequiredMark() {
  return (
    <span aria-hidden="true" className="ml-1 text-rose-600">
      *
    </span>
  );
}

export function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1 text-sm text-rose-700">
      {message}
    </p>
  );
}
