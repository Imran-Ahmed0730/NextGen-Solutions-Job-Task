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
