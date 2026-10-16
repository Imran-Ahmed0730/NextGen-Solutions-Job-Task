import { describe, expect, it } from 'vitest';

import {
  attendanceCreateSchema,
  attendanceDateRangeSchema,
  attendanceUpdateSchema,
  changePasswordSchema,
  companySettingValueSchemas,
  customerCollectionSchema,
  customerSchema,
  employeeSchema,
  expenseCategorySchema,
  forgotPasswordSchema,
  incomeCategorySchema,
  loginSchema,
  moneyAccountSchema,
  paymentMethodSchema,
  productCategorySchema,
  productSchema,
  profileSchema,
  resetPasswordSchema,
  roleSchema,
  salesDeliverySchema,
  salesInvoiceSchema,
  salesOrderSchema,
  salesOrderReservationSchema,
  salesReturnSchema,
  stockAdjustmentSchema,
  supplierPaymentSchema,
  supplierSchema,
  unitSchema,
  userSchema,
  warehouseSchema,
} from './auth-validation';

describe('auth-validation schemas', () => {
  it('validates attendance statuses, dates, employees, and optional times', () => {
    const valid = {
      employee_id: 2,
      att_date: '2026-10-16',
      status: 'PRESENT' as const,
      in_time: '08:30',
      out_time: '',
    };
    expect(attendanceCreateSchema.parse(valid)).toEqual({ ...valid, out_time: null });
    expect(attendanceCreateSchema.safeParse({ ...valid, employee_id: 0 }).success).toBe(false);
    expect(attendanceCreateSchema.safeParse({ ...valid, status: 'HOLIDAY' }).success).toBe(false);
    expect(attendanceUpdateSchema.safeParse({ ...valid, in_time: '25:00' }).success).toBe(false);
    expect(attendanceDateRangeSchema.safeParse({
      from_date: '2026-10-17',
      to_date: '2026-10-16',
    }).success).toBe(false);
  });

  it('validates company setting values consistently with backend rules', () => {
    expect(companySettingValueSchemas.company_name.safeParse('  ').success).toBe(false);
    expect(companySettingValueSchemas.company_email.safeParse('bad-email').success).toBe(false);
    expect(companySettingValueSchemas.company_phone.safeParse('letters').success).toBe(false);
    expect(companySettingValueSchemas.currency_code.parse('bdt')).toBe('BDT');
    expect(companySettingValueSchemas.timezone.safeParse('Not/A-Timezone').success).toBe(true);
    expect(companySettingValueSchemas.credit_limit_mode.safeParse('INVALID').success).toBe(false);
    expect(companySettingValueSchemas.receipt_tolerance_pct.safeParse('-1').success).toBe(false);
    expect(companySettingValueSchemas.receipt_tolerance_pct.safeParse('0.001').success).toBe(true);
  });

  it('validates sales-order draft fields and lines', () => {
    const valid = {
      doc_date: '2026-10-24',
      customer_id: 1,
      warehouse_id: 2,
      delivery_date: '',
      discount: '1.00',
      note: '',
      lines: [{ product_id: 3, qty_ordered: '2.500', unit_price: '4.00' }],
    };
    expect(salesOrderSchema.safeParse(valid).success).toBe(true);
    expect(salesOrderSchema.safeParse({ ...valid, warehouse_id: 0 }).success).toBe(false);
    expect(
      salesOrderSchema.safeParse({
        ...valid,
        lines: [{ ...valid.lines[0], qty_ordered: '0.000' }],
      }).success,
    ).toBe(false);
  });

  it('validates sales returns with unique, positive invoice-line quantities', () => {
    const valid = {
      doc_date: '2026-10-26',
      invoice_id: 4,
      note: '',
      lines: [{ invoice_line_id: 9, qty: '1.250' }],
    };
    expect(salesReturnSchema.safeParse(valid).success).toBe(true);
    expect(salesReturnSchema.safeParse({ ...valid, lines: [] }).success).toBe(false);
    expect(
      salesReturnSchema.safeParse({
        ...valid,
        lines: [
          { invoice_line_id: 9, qty: '1.000' },
          { invoice_line_id: 9, qty: '0.500' },
        ],
      }).success,
    ).toBe(false);
  });

  it('validates reservation quantities', () => {
    expect(salesOrderReservationSchema.safeParse({ qty: '2.500' }).success).toBe(true);
    expect(salesOrderReservationSchema.safeParse({ qty: '0.000' }).success).toBe(false);
    expect(salesOrderReservationSchema.safeParse({ qty: '1.0000' }).success).toBe(false);
  });

  it('validates sales delivery dates, quantities, and unique order lines', () => {
    const valid = {
      doc_date: '2026-10-27',
      lines: [{ order_line_id: 1, qty: '2.500' }],
    };
    expect(salesDeliverySchema.safeParse(valid).success).toBe(true);
    expect(salesDeliverySchema.safeParse({ ...valid, doc_date: 'invalid' }).success).toBe(false);
    expect(
      salesDeliverySchema.safeParse({
        ...valid,
        lines: [{ order_line_id: 1, qty: '0.000' }],
      }).success,
    ).toBe(false);
    expect(
      salesDeliverySchema.safeParse({
        ...valid,
        lines: [
          { order_line_id: 1, qty: '1.000' },
          { order_line_id: 1, qty: '1.000' },
        ],
      }).success,
    ).toBe(false);
  });

  it('validates invoice delivery selection and due-date order', () => {
    const valid = {
      delivery_id: 3,
      doc_date: '2026-10-25',
      due_date: '2026-11-05',
    };
    expect(salesInvoiceSchema.safeParse(valid).success).toBe(true);
    expect(salesInvoiceSchema.safeParse({ ...valid, delivery_id: 0 }).success).toBe(false);
    expect(
      salesInvoiceSchema.safeParse({ ...valid, due_date: '2026-10-24' }).success,
    ).toBe(false);
  });

  it('validates customer collections', () => {
    const valid = {
      doc_date: '2026-10-15',
      customer_id: 1,
      account_id: 2,
      amount: '25.50',
      method_ref: '',
      note: '',
    };
    expect(customerCollectionSchema.safeParse(valid).success).toBe(true);
    expect(customerCollectionSchema.safeParse({ ...valid, amount: '0.00' }).success).toBe(false);
    expect(customerCollectionSchema.safeParse({ ...valid, customer_id: 0 }).success).toBe(false);
  });

  it('validates supplier payments and allocation totals', () => {
    const valid = {
      doc_date: '2026-10-15',
      supplier_id: 1,
      account_id: 2,
      amount: '40.00',
      note: '',
      allocations: [
        { ref_type: 'DIRECT_PURCHASE' as const, ref_id: 3, amount: '25.00' },
      ],
    };
    expect(supplierPaymentSchema.safeParse(valid).success).toBe(true);
    expect(
      supplierPaymentSchema.safeParse({
        ...valid,
        amount: '0.30',
        allocations: [
          { ref_type: 'RECEIPT' as const, ref_id: 1, amount: '0.10' },
          { ref_type: 'DIRECT_PURCHASE' as const, ref_id: 2, amount: '0.20' },
        ],
      }).success,
    ).toBe(true);
    expect(
      supplierPaymentSchema.safeParse({
        ...valid,
        allocations: [{ ...valid.allocations[0], amount: '40.01' }],
      }).success,
    ).toBe(false);
    expect(supplierPaymentSchema.safeParse({ ...valid, amount: '1.001' }).success).toBe(false);
  });

  it('validates login input length constraints', () => {
    expect(loginSchema.safeParse({ username: 'admin', password: 'password123' }).success).toBe(true);
    expect(loginSchema.safeParse({ username: '', password: 'password' }).success).toBe(false);
    expect(loginSchema.safeParse({ username: 'a'.repeat(256), password: 'password' }).success).toBe(false);
  });

  it('validates Bangladesh mobile numbers correctly in profile and user', () => {
    expect(
      profileSchema.safeParse({
        full_name: 'Imran Ahmed',
        email: 'imran@example.com',
        mobile: '01712345678',
      }).success,
    ).toBe(true);

    // Empty or omitted mobile is valid
    expect(
      profileSchema.safeParse({
        full_name: 'Imran Ahmed',
        email: '',
        mobile: '',
      }).success,
    ).toBe(true);

    // Invalid BD prefixes or lengths
    expect(
      profileSchema.safeParse({
        full_name: 'Imran Ahmed',
        mobile: '01234567890', // 012 is not valid BD prefix
      }).success,
    ).toBe(false);

    expect(
      profileSchema.safeParse({
        full_name: 'Imran Ahmed',
        mobile: '017123456', // Too short
      }).success,
    ).toBe(false);
  });

  it('requires and validates employee mobile numbers', () => {
    const employee = {
      code: 'EMP-001',
      name: 'Ayesha Rahman',
      mobile: '01712345678',
      email: '',
      designation: '',
      department: '',
      join_date: '2024-02-01',
      base_salary: '25000.00',
    };
    expect(employeeSchema.safeParse(employee).success).toBe(true);
    expect(employeeSchema.safeParse({ ...employee, mobile: '' }).success).toBe(false);
    expect(employeeSchema.safeParse({ ...employee, mobile: 'abc' }).success).toBe(false);
  });

  it('validates optional customer and supplier mobile numbers consistently', () => {
    const customer = {
      code: 'CUS-001',
      name: 'Customer',
      mobile: 'abc',
      email: null,
      address: null,
      credit_limit: '0',
      opening_due: '0',
      price_list_id: null,
      is_active: true,
    };
    const supplier = {
      code: 'SUP-001',
      name: 'Supplier',
      mobile: 'abc',
      email: null,
      address: null,
      opening_due: '0',
      is_active: true,
    };
    expect(customerSchema.safeParse(customer).success).toBe(false);
    expect(supplierSchema.safeParse(supplier).success).toBe(false);
    expect(customerSchema.safeParse({ ...customer, mobile: null }).success).toBe(true);
    expect(supplierSchema.safeParse({ ...supplier, mobile: null }).success).toBe(true);
  });

  it('validates username format in userSchema', () => {
    expect(
      userSchema.safeParse({
        username: 'john.doe_01',
        full_name: 'John Doe',
        email: 'john@example.com',
        role_ids: [1, 2],
      }).success,
    ).toBe(true);

    // Spaces or invalid characters in username
    expect(
      userSchema.safeParse({
        username: 'john doe',
        full_name: 'John Doe',
        role_ids: [1],
      }).success,
    ).toBe(false);

    // Duplicate role IDs rejected
    expect(
      userSchema.safeParse({
        username: 'johndoe',
        full_name: 'John Doe',
        role_ids: [1, 1],
      }).success,
    ).toBe(false);
  });

  it('validates password matching on reset and change password', () => {
    expect(
      resetPasswordSchema.safeParse({
        token: 'valid-token',
        new_password: 'new-password-123',
        confirm_password: 'new-password-123',
      }).success,
    ).toBe(true);

    expect(
      resetPasswordSchema.safeParse({
        token: 'valid-token',
        new_password: 'new-password-123',
        confirm_password: 'different-password',
      }).success,
    ).toBe(false);

    expect(
      changePasswordSchema.safeParse({
        current_password: 'old-password',
        new_password: 'new-password-123',
        confirm_password: 'new-password-123',
      }).success,
    ).toBe(true);
  });

  it('validates forgot password email format', () => {
    expect(forgotPasswordSchema.safeParse({ email: 'user@example.com' }).success).toBe(true);
    expect(forgotPasswordSchema.safeParse({ email: 'not-an-email' }).success).toBe(false);
  });

  it('validates role and unit schemas', () => {
    expect(
      roleSchema.safeParse({
        name: 'Manager',
        description: 'Store manager',
        permission_ids: [1, 2],
      }).success,
    ).toBe(true);

    expect(
      roleSchema.safeParse({
        name: '',
        permission_ids: [1],
      }).success,
    ).toBe(false);

    expect(
      unitSchema.safeParse({
        name: 'Kilogram',
        code: 'kg',
        allow_decimal: true,
      }).success,
    ).toBe(true);
  });

  it('validates productCategorySchema parent_id and status', () => {
    expect(
      productCategorySchema.safeParse({
        name: 'Electronics',
        parent_id: null,
        is_active: true,
      }).success,
    ).toBe(true);

    expect(
      productCategorySchema.safeParse({
        name: 'Phones',
        parent_id: 1,
        is_active: true,
      }).success,
    ).toBe(true);

    expect(
      productCategorySchema.safeParse({
        name: 'Phones',
        parent_id: -1,
        is_active: true,
      }).success,
    ).toBe(false);
  });

  it('validates productSchema fields, types, and numbers', () => {
    expect(
      productSchema.safeParse({
        sku: 'RAW-WHEAT-01',
        name: 'Wheat Grain',
        type: 'RAW',
        category_id: 1,
        unit_id: 2,
        is_stocked: true,
        reorder_level: 10,
        sales_price_default: 25.5,
        description: 'Test wheat',
        is_active: true,
      }).success,
    ).toBe(true);

    // Invalid SKU format
    expect(
      productSchema.safeParse({
        sku: 'invalid sku with spaces',
        name: 'Wheat Grain',
        type: 'RAW',
        category_id: 1,
        unit_id: 2,
        is_stocked: true,
        reorder_level: 10,
        sales_price_default: 25,
        is_active: true,
      }).success,
    ).toBe(false);

    // Negative reorder level
    expect(
      productSchema.safeParse({
        sku: 'SKU-01',
        name: 'Wheat Grain',
        type: 'RAW',
        category_id: 1,
        unit_id: 2,
        is_stocked: true,
        reorder_level: -5,
        sales_price_default: 25,
        is_active: true,
      }).success,
    ).toBe(false);
  });

  it('validates warehouseSchema fields and defaults', () => {
    expect(
      warehouseSchema.safeParse({
        name: 'Main Store',
        code: 'MS',
        address: 'Dhaka',
        is_default: true,
        is_active: true,
      }).success,
    ).toBe(true);

    // Empty address is allowed
    expect(
      warehouseSchema.safeParse({
        name: 'Overflow',
        code: 'OF',
        address: null,
        is_default: false,
        is_active: true,
      }).success,
    ).toBe(true);

    // Missing name or code is rejected
    expect(
      warehouseSchema.safeParse({
        name: '',
        code: 'OF',
        address: '',
        is_default: false,
        is_active: true,
      }).success,
    ).toBe(false);

    // Over-long address is rejected
    expect(
      warehouseSchema.safeParse({
        name: 'Overflow',
        code: 'OF',
        address: 'a'.repeat(256),
        is_default: false,
        is_active: true,
      }).success,
    ).toBe(false);
  });

  it('validates signed stock adjustment quantities and required reason', () => {
    const validAdjustment = {
      doc_date: '2026-10-14',
      warehouse_id: 1,
      reason: 'Physical review',
      lines: [
        { product_id: 1, qty_signed: '2.500' },
        { product_id: 2, qty_signed: '-1.250' },
      ],
    };
    expect(stockAdjustmentSchema.safeParse(validAdjustment).success).toBe(true);
    expect(
      stockAdjustmentSchema.safeParse({
        ...validAdjustment,
        reason: '   ',
      }).success,
    ).toBe(false);
    expect(
      stockAdjustmentSchema.safeParse({
        ...validAdjustment,
        lines: [{ product_id: 1, qty_signed: '0.000' }],
      }).success,
    ).toBe(false);
    expect(
      stockAdjustmentSchema.safeParse({
        ...validAdjustment,
        lines: [
          { product_id: 1, qty_signed: '1.000' },
          { product_id: 1, qty_signed: '-1.000' },
        ],
      }).success,
    ).toBe(false);
  });

  it('validates expense and income category schemas', () => {
    expect(
      expenseCategorySchema.safeParse({
        name: 'Transport',
        parent_id: null,
        is_active: true,
      }).success,
    ).toBe(true);

    expect(
      expenseCategorySchema.safeParse({
        name: 'Fuel',
        parent_id: 3,
        is_active: true,
      }).success,
    ).toBe(true);

    expect(
      expenseCategorySchema.safeParse({
        name: '',
        parent_id: null,
        is_active: true,
      }).success,
    ).toBe(false);

    expect(
      incomeCategorySchema.safeParse({ name: 'Interest Income', is_active: true }).success,
    ).toBe(true);

    expect(
      incomeCategorySchema.safeParse({ name: '', is_active: true }).success,
    ).toBe(false);
  });

  it('validates paymentMethodSchema type and status', () => {
    expect(
      paymentMethodSchema.safeParse({ name: 'Cash', type: 'CASH', is_active: true }).success,
    ).toBe(true);

    expect(
      paymentMethodSchema.safeParse({ name: 'Bank', type: 'BANK', is_active: true }).success,
    ).toBe(true);

    expect(
      paymentMethodSchema.safeParse({ name: 'Crypto', type: 'CRYPTO', is_active: true }).success,
    ).toBe(false);

    expect(
      paymentMethodSchema.safeParse({ name: '', type: 'CASH', is_active: true }).success,
    ).toBe(false);
  });

  it('validates moneyAccountSchema fields and numbers', () => {
    expect(
      moneyAccountSchema.safeParse({
        name: 'Main Bank',
        type: 'BANK',
        payment_method_id: 1,
        account_no: '1234567890',
        opening_balance: 5000.5,
        allow_overdraft: false,
        is_active: true,
      }).success,
    ).toBe(true);

    // Optional payment method and account number
    expect(
      moneyAccountSchema.safeParse({
        name: 'Petty Cash',
        type: 'CASH',
        payment_method_id: null,
        account_no: null,
        opening_balance: 0,
        allow_overdraft: false,
        is_active: true,
      }).success,
    ).toBe(true);

    // Invalid type
    expect(
      moneyAccountSchema.safeParse({
        name: 'Wallet',
        type: 'CASH',
        payment_method_id: null,
        opening_balance: 0,
        allow_overdraft: false,
        is_active: true,
      }).success,
    ).toBe(true);

    expect(
      moneyAccountSchema.safeParse({
        name: 'Wallet',
        type: 'ONLINE',
        payment_method_id: null,
        opening_balance: 0,
        allow_overdraft: false,
        is_active: true,
      }).success,
    ).toBe(false);

    // Non-numeric opening balance is coerced/rejected
    expect(
      moneyAccountSchema.safeParse({
        name: 'Wallet',
        type: 'MFS',
        payment_method_id: null,
        opening_balance: 'not-a-number',
        allow_overdraft: false,
        is_active: true,
      }).success,
    ).toBe(false);
  });
});
