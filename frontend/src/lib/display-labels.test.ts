import { describe, expect, it } from 'vitest';

import {
  documentTypeLabel,
  formatCodeLabel,
  moneyTransactionLabel,
  moduleLabel,
  permissionLabel,
  sourceTypeLabel,
  statusLabel,
  stockMovementLabel,
} from './display-labels';

describe('display labels', () => {
  it('maps document types to friendly names and handles unknown types', () => {
    expect(documentTypeLabel('PAYROLL')).toBe('Payroll run');
    expect(documentTypeLabel('LEGACY_FORM')).toBe('Legacy form');
  });

  it('formats status and unknown code values without changing their meaning', () => {
    expect(statusLabel('PENDING_APPROVAL')).toBe('Pending approval');
    expect(formatCodeLabel('PARTIALLY-RECEIVED')).toBe('Partially received');
  });

  it('provides user-facing ledger labels', () => {
    expect(moneyTransactionLabel('SALARY')).toBe('Payroll payment');
    expect(stockMovementLabel('TRANSFER_IN')).toBe('Stock received from another warehouse');
    expect(sourceTypeLabel('STOCK_TRANSFER')).toBe('Stock transfer');
  });

  it('uses permission descriptions and has a readable fallback', () => {
    expect(permissionLabel('employees.payroll.post', 'Post payroll')).toBe('Post payroll');
    expect(permissionLabel('inventory.stock.read', null)).toBe('View stock');
    expect(moduleLabel('master_data')).toBe('Setup and master data');
  });
});
