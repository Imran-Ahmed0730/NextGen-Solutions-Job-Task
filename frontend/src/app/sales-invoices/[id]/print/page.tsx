'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

import { ProtectedPage } from '@/components/auth/protected-page';
import {
  PrintDocumentButton,
  PrintDocumentHeader,
  type PrintBranding,
} from '@/components/documents/print-document';
import { apiRequest } from '@/lib/auth-api';

type InvoicePrintData = {
  company: PrintBranding & {
    address: string;
    phone: string;
    email: string;
    currency_code: string | null;
    footer: string;
  };
  invoice_no: string;
  invoice_date: string;
  due_date: string;
  delivery_no: string;
  order_no: string;
  customer: {
    code: string;
    name: string;
    mobile: string | null;
    email: string | null;
    address: string | null;
  };
  lines: Array<{
    product_sku: string;
    product_name: string;
    unit_code: string;
    qty: string;
    unit_price: string;
    line_total: string;
  }>;
  subtotal: string;
  discount: string;
  total: string;
};

function formatMoney(value: string, currencyCode: string | null): string {
  const amount = Number(value).toFixed(2);
  return currencyCode ? `${currencyCode} ${amount}` : amount;
}

function formatDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString();
}

export default function SalesInvoicePrintPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const [invoice, setInvoice] = useState<InvoicePrintData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    let active = true;
    apiRequest<InvoicePrintData>(`/api/v1/sales/invoices/${id}/print`)
      .then((data) => {
        if (active) setInvoice(data);
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(cause instanceof Error ? cause.message : 'Could not load invoice');
        }
      });
    return () => {
      active = false;
    };
  }, [id]);

  return (
    <ProtectedPage>
      <div className="space-y-5">
        <div className="flex items-center justify-between gap-3 print:hidden">
          <Link
            href="/sales-invoices"
            className="text-sm font-medium text-emerald-800 hover:underline"
          >
            Back to invoices
          </Link>
          {invoice && <PrintDocumentButton />}
        </div>
        {error && <p className="text-sm text-rose-700">{error}</p>}
        {!invoice && !error && <p className="text-sm text-slate-600">Loading invoice…</p>}
        {invoice && (
          <article className="mx-auto max-w-4xl space-y-6 rounded-xl border border-slate-200 bg-white p-8 shadow-sm print:max-w-none print:border-0 print:p-0 print:shadow-none">
            <PrintDocumentHeader
              branding={invoice.company}
              title="Sales Invoice"
              subtitle={[
                invoice.company.address,
                invoice.company.phone,
                invoice.company.email,
              ]
                .filter(Boolean)
                .join(' · ')}
            />
            <section className="grid gap-6 sm:grid-cols-2">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Bill to
                </h3>
                <p className="mt-2 font-semibold text-slate-900">{invoice.customer.name}</p>
                <p className="text-sm text-slate-600">Customer code: {invoice.customer.code}</p>
                {invoice.customer.address && (
                  <p className="text-sm text-slate-600">{invoice.customer.address}</p>
                )}
                {invoice.customer.mobile && (
                  <p className="text-sm text-slate-600">{invoice.customer.mobile}</p>
                )}
                {invoice.customer.email && (
                  <p className="text-sm text-slate-600">{invoice.customer.email}</p>
                )}
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <dt className="text-slate-500">Invoice number</dt>
                <dd className="text-right font-medium text-slate-900">{invoice.invoice_no}</dd>
                <dt className="text-slate-500">Invoice date</dt>
                <dd className="text-right text-slate-900">{formatDate(invoice.invoice_date)}</dd>
                <dt className="text-slate-500">Due date</dt>
                <dd className="text-right text-slate-900">{formatDate(invoice.due_date)}</dd>
                <dt className="text-slate-500">Delivery</dt>
                <dd className="text-right text-slate-900">{invoice.delivery_no}</dd>
                <dt className="text-slate-500">Sales order</dt>
                <dd className="text-right text-slate-900">{invoice.order_no}</dd>
              </dl>
            </section>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2">Product</th>
                    <th className="px-3 py-2 text-right">Quantity</th>
                    <th className="px-3 py-2 text-right">Unit price</th>
                    <th className="px-3 py-2 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.lines.map((line, index) => (
                    <tr key={`${line.product_sku}-${index}`} className="border-t border-slate-100">
                      <td className="px-3 py-2">
                        <p className="font-medium text-slate-900">{line.product_name}</p>
                        <p className="text-xs text-slate-500">{line.product_sku}</p>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {line.qty} {line.unit_code}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {formatMoney(line.unit_price, invoice.company.currency_code)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {formatMoney(line.line_total, invoice.company.currency_code)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="ml-auto w-full max-w-xs space-y-2 text-sm">
              <div className="flex justify-between text-slate-600">
                <span>Subtotal</span>
                <span>{formatMoney(invoice.subtotal, invoice.company.currency_code)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Discount</span>
                <span>{formatMoney(invoice.discount, invoice.company.currency_code)}</span>
              </div>
              <div className="flex justify-between border-t border-slate-200 pt-2 text-base font-semibold text-slate-900">
                <span>Total due</span>
                <span>{formatMoney(invoice.total, invoice.company.currency_code)}</span>
              </div>
            </div>
            {invoice.company.footer && (
              <footer className="border-t border-slate-200 pt-4 text-sm text-slate-600">
                {invoice.company.footer}
              </footer>
            )}
          </article>
        )}
      </div>
    </ProtectedPage>
  );
}
