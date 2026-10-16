import type { ButtonHTMLAttributes, ReactNode } from 'react';

const icons = {
  add: <path d="M12 5v14m-7-7h14" />,
  edit: <path d="m14 5 5 5M4 20l4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z" />,
  delete: <path d="M4 7h16m-10 4v6m4-6v6M6 7l1 14h10l1-14M9 7V4h6v3" />,
  restore: <path d="M4 11a8 8 0 1 1 2.2 5.5M4 4v7h7" />,
  activate: <path d="m5 12 4 4L19 6" />,
  deactivate: <path d="m6 6 12 12M18 6 6 18" />,
  save: <path d="M5 4h12l3 3v13H4V4h1Zm2 0v6h9V4m-8 16v-7h8v7" />,
  contacts: <path d="M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 18.5V20m6-9a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm6-6.5a3.5 3.5 0 0 1 0 6.8m2 3.2a3.5 3.5 0 0 1 2 3.2V20" />,
  statement: <path d="M7 3h7l5 5v13H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm7 0v5h5M9 13h6m-6 4h6" />,
  prices: <path d="M20 13 13 20 3 10V4h6l11 9Zm-12-6h.01" />,
  assign: <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Zm-5 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />,
  maintenance: <path d="M14.5 6.5a5 5 0 0 0-6.7 6.7L3 18l3 3 4.8-4.8a5 5 0 0 0 6.7-6.7L14 13l-3-3 3.5-3.5Z" />,
  return: <path d="M9 14 4 9l5-5M4 9h10a6 6 0 0 1 0 12h-2" />,
  view: <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />,
  send: <path d="m22 2-7 20-4-9-9-4 20-7ZM22 2 11 13" />,
  reject: <path d="m6 6 12 12M18 6 6 18" />,
  convert: <path d="M7 7h13l-3-3m3 3-3 3M17 17H4l3 3m-3-3 3-3" />,
  submit: <path d="M12 16V4m-5 5 5-5 5 5M5 14v6h14v-6" />,
  cancel: <path d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Zm-3-13 6 6m0-6-6 6" />,
  start: <path d="m8 5 12 7-12 7V5Z" />,
  complete: <path d="m5 12 4 4L19 6" />,
  reserve: <path d="M5 11h14v10H5V11Zm3 0V7a4 4 0 0 1 8 0v4m-4 4v2" />,
  release: <path d="M5 11h14v10H5V11Zm3 0V7a4 4 0 0 1 8 0m-4 8v2" />,
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
  tooltip?: string;
  children?: ReactNode;
};

export function IconActionButton({
  icon,
  label,
  tooltip,
  children,
  className = '',
  type = 'button',
  ...props
}: IconActionButtonProps) {
  return (
    <button
      type={type}
      title={tooltip ?? label}
      aria-label={label}
      className={`inline-flex items-center justify-center gap-2 rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      {...props}
    >
      <ActionIcon name={icon} />
      {children}
    </button>
  );
}
