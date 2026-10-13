import type { ButtonHTMLAttributes, ReactNode } from 'react';

const icons = {
  add: <path d="M12 5v14m-7-7h14" />,
  edit: <path d="m14 5 5 5M4 20l4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z" />,
  delete: <path d="M4 7h16m-10 4v6m4-6v6M6 7l1 14h10l1-14M9 7V4h6v3" />,
  restore: <path d="M4 11a8 8 0 1 1 2.2 5.5M4 4v7h7" />,
  activate: <path d="m5 12 4 4L19 6" />,
  deactivate: <path d="m6 6 12 12M18 6 6 18" />,
  save: <path d="M5 4h12l3 3v13H4V4h1Zm2 0v6h9V4m-8 16v-7h8v7" />,
} as const;

export type ActionIconName = keyof typeof icons;

export function ActionIcon({
  name,
  className = 'h-4 w-4',
}: {
  name: ActionIconName;
  className?: string;
}) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
    >
      {icons[name]}
    </svg>
  );
}

type IconActionButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> & {
  icon: ActionIconName;
  label: string;
  children?: ReactNode;
};

export function IconActionButton({
  icon,
  label,
  children,
  className = '',
  type = 'button',
  ...props
}: IconActionButtonProps) {
  return (
    <button
      type={type}
      title={label}
      aria-label={label}
      className={`inline-flex items-center justify-center gap-2 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      {...props}
    >
      <ActionIcon name={icon} />
      {children}
    </button>
  );
}
