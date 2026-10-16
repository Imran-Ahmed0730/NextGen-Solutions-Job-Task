export const DOCUMENT_TYPES = [
  { value: 'CUSTOMER_COLLECTION', label: 'Customer collection' },
  { value: 'DELIVERY', label: 'Sales delivery' },
  { value: 'DIRECT_PURCHASE', label: 'Direct purchase' },
  { value: 'EXPENSE', label: 'Expense' },
  { value: 'FUND_TRANSFER', label: 'Fund transfer' },
  { value: 'GOODS_RECEIPT', label: 'Goods receipt' },
  { value: 'INCOME', label: 'Income' },
  { value: 'INVOICE', label: 'Sales invoice' },
  { value: 'PAYROLL', label: 'Payroll run' },
  { value: 'PHYSICAL_COUNT', label: 'Physical stock count' },
  { value: 'PRODUCTION_ORDER', label: 'Production order' },
  { value: 'PURCHASE_ORDER', label: 'Purchase order' },
  { value: 'PURCHASE_RETURN', label: 'Purchase return' },
  { value: 'QUOTATION', label: 'Quotation' },
  { value: 'SALES_ORDER', label: 'Sales order' },
  { value: 'SALES_RETURN', label: 'Sales return' },
  { value: 'STOCK_ADJUSTMENT', label: 'Stock adjustment' },
  { value: 'STOCK_TRANSFER', label: 'Stock transfer' },
  { value: 'SUPPLIER_PAYMENT', label: 'Supplier payment' },
] as const;

const DOCUMENT_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  DOCUMENT_TYPES.map(({ value, label }) => [value, label]),
);

const MONEY_TRANSACTION_LABELS: Record<string, string> = {
  COLLECTION: 'Customer collection',
  EXPENSE: 'Expense payment',
  INCOME: 'Income received',
  OPENING: 'Opening balance adjustment',
  PAYMENT: 'Payment',
  PURCHASE_PAYMENT: 'Supplier payment',
  SALARY: 'Payroll payment',
  TRANSFER_IN: 'Money received by transfer',
  TRANSFER_OUT: 'Money sent by transfer',
};

const STOCK_MOVEMENT_LABELS: Record<string, string> = {
  ADJUSTMENT_IN: 'Stock adjustment in',
  ADJUSTMENT_OUT: 'Stock adjustment out',
  COUNT_ADJUSTMENT: 'Physical count adjustment',
  OPENING: 'Opening stock',
  PRODUCTION_CONSUME: 'Materials used in production',
  PRODUCTION_OUTPUT: 'Goods completed in production',
  PURCHASE_RECEIPT: 'Goods received from supplier',
  PURCHASE_RETURN: 'Goods returned to supplier',
  SALE_DELIVERY: 'Goods delivered to customer',
  SALE_RETURN: 'Goods returned by customer',
  TRANSFER_IN: 'Stock received from another warehouse',
  TRANSFER_OUT: 'Stock sent to another warehouse',
};

const SOURCE_TYPE_LABELS: Record<string, string> = {
  ...DOCUMENT_TYPE_LABELS,
  CUSTOMER_COLLECTION: 'Customer collection',
  DIRECT_PURCHASE: 'Direct purchase',
  GOODS_RECEIPT: 'Goods receipt',
  INVOICE: 'Sales invoice',
  PAYROLL: 'Payroll run',
  STOCK_ADJUSTMENT: 'Stock adjustment',
  STOCK_TRANSFER: 'Stock transfer',
  SUPPLIER_PAYMENT: 'Supplier payment',
};

const MODULE_LABELS: Record<string, string> = {
  auth: 'User access',
  employees: 'Employees',
  inventory: 'Inventory',
  master_data: 'Setup and master data',
  money: 'Money and accounts',
  production: 'Production',
  purchases: 'Purchases',
  sales: 'Sales',
};

export function formatCodeLabel(value: string): string {
  const words = value.trim().toLowerCase().replaceAll(/[_\-.]+/g, ' ');
  return words ? words[0].toUpperCase() + words.slice(1) : '';
}

export function statusLabel(value: string): string {
  return formatCodeLabel(value);
}

export function documentTypeLabel(value: string): string {
  return DOCUMENT_TYPE_LABELS[value] ?? formatCodeLabel(value);
}

export function moneyTransactionLabel(value: string): string {
  return MONEY_TRANSACTION_LABELS[value] ?? formatCodeLabel(value);
}

export function stockMovementLabel(value: string): string {
  return STOCK_MOVEMENT_LABELS[value] ?? formatCodeLabel(value);
}

export function sourceTypeLabel(value: string): string {
  return SOURCE_TYPE_LABELS[value] ?? formatCodeLabel(value);
}

export function moduleLabel(value: string): string {
  return MODULE_LABELS[value] ?? formatCodeLabel(value);
}

export function permissionLabel(code: string, description: string | null): string {
  if (description) return description;
  const parts = code.split('.');
  const action = parts.pop() ?? '';
  const resource = formatCodeLabel(parts.slice(1).join(' ')).toLowerCase();
  const actionLabel: Record<string, string> = {
    create: 'Create',
    delete: 'Deactivate',
    read: 'View',
    update: 'Update',
  };
  return `${actionLabel[action] ?? formatCodeLabel(action)} ${resource}`.trim();
}
