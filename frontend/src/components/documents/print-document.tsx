'use client';

import Image from 'next/image';
import { useEffect, useState } from 'react';

import { apiRequest, getApiUrl } from '@/lib/auth-api';
import { showErrorToast } from '@/lib/notifications';

export type PrintBranding = {
  company_name: string;
  company_logo_path: string;
};

export type PrintBrandingState = {
  branding: PrintBranding | null;
  error: string;
};

export function usePrintBranding(): PrintBrandingState {
  const [branding, setBranding] = useState<PrintBranding | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    apiRequest<PrintBranding>('/api/v1/company-settings/branding')
      .then((loadedBranding) => {
        if (active) setBranding(loadedBranding);
      })
      .catch((cause: unknown) => {
        const message =
          cause instanceof Error ? cause.message : 'Could not load company branding';
        if (active) setError(message);
        showErrorToast(
          message,
        );
      });
    return () => {
      active = false;
    };
  }, []);

  return { branding, error };
}

export function PrintDocumentHeader({
  branding,
  title,
  subtitle,
}: {
  branding: PrintBranding;
  title: string;
  subtitle?: string;
}) {
  const logoUrl = branding.company_logo_path.startsWith('/media/')
    ? getApiUrl(branding.company_logo_path)
    : branding.company_logo_path;

  return (
    <header className="flex items-start justify-between gap-6 border-b border-slate-200 pb-5">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{branding.company_name}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-600">{subtitle}</p>}
      </div>
      <div className="text-right">
        <Image
          src={logoUrl}
          alt={`${branding.company_name} logo`}
          width={176}
          height={56}
          unoptimized
          className="ml-auto max-h-14 max-w-44 object-contain"
        />
        <h2 className="mt-3 text-xl font-semibold text-slate-900">{title}</h2>
      </div>
    </header>
  );
}

export function PrintDocumentButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white print:hidden"
    >
      Print / Save as PDF
    </button>
  );
}
