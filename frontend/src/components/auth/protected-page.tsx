'use client';

import type { ReactNode } from 'react';

import { SessionShell } from '@/components/auth/session-shell';

export function ProtectedPage({ children }: { children: ReactNode }) {
  return <SessionShell>{children}</SessionShell>;
}
