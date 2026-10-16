import { z } from 'zod';

const bangladeshMobilePattern = /^01[3-9]\d{8}$/;
const usernamePattern = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const optionalEmail = z
  .string()
  .trim()
  .max(255, 'Use at most 255 characters')
  .email('Enter a valid email address')
  .or(z.literal(''))
  .optional();
const optionalBangladeshMobile = z
  .string()
  .trim()
  .max(11, 'Use an 11-digit Bangladesh mobile number')
  .refine(
    (value) => value === undefined || value === '' || bangladeshMobilePattern.test(value),
    'Use a valid Bangladesh mobile number, e.g. 01712345678',
  )
  .optional();
const optionalPartyBangladeshMobile = z
  .string()
  .trim()
  .max(11, 'Use an 11-digit Bangladesh mobile number')
  .regex(/^$|^01[3-9]\d{8}$/, 'Use a valid Bangladesh mobile number, e.g. 01712345678')
  .nullable()
  .optional();

export const loginSchema = z.object({
  username: z
    .string()
    .trim()
    .min(1, 'Enter your username, email, or mobile number')
    .max(255, 'Use at most 255 characters'),
  password: z.string().min(1, 'Enter your password').max(256, 'Use at most 256 characters'),
});

export const forgotPasswordSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, 'Email address is required')
    .max(255, 'Use at most 255 characters')
    .email('Enter a valid email address'),
});

export const resetPasswordSchema = z
  .object({
    token: z.string().trim().min(1, 'Enter the reset token').max(512, 'Token is too long'),
    new_password: z.string().min(8, 'Use at least 8 characters').max(256, 'Use at most 256 characters'),
    confirm_password: z.string().min(1, 'Confirm your password'),
  })
  .refine((value) => value.new_password === value.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

export const changePasswordSchema = z
  .object({
    current_password: z
      .string()
      .min(1, 'Enter your current password')
      .max(256, 'Use at most 256 characters'),
    new_password: z.string().min(8, 'Use at least 8 characters').max(256, 'Use at most 256 characters'),
    confirm_password: z.string().min(1, 'Confirm your password'),
  })
  .refine((value) => value.new_password === value.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

export const profileSchema = z.object({
  full_name: z
    .string()
    .trim()
    .min(1, 'Name is required')
    .max(255, 'Use at most 255 characters'),
  email: optionalEmail,
  mobile: optionalBangladeshMobile,
});

export const userSchema = z.object({
  username: z
    .string()
    .trim()
    .min(1, 'Username is required')
    .max(100, 'Use at most 100 characters')
    .regex(usernamePattern, 'Use letters, numbers, dots, underscores, or hyphens'),
  full_name: z
    .string()
    .trim()
    .min(1, 'Name is required')
    .max(255, 'Use at most 255 characters'),
  email: optionalEmail,
  mobile: optionalBangladeshMobile,
  password: z
    .string()
    .max(256, 'Use at most 256 characters')
    .refine((value) => value === '' || value.length >= 8, 'Use at least 8 characters')
    .optional(),
  role_ids: z.array(z.number().int().positive()).refine(
    (ids) => new Set(ids).size === ids.length,
    'A role may only be selected once',
  ),
});

export const roleSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Role name is required')
    .max(100, 'Use at most 100 characters'),
  description: z.string().max(2000, 'Use at most 2000 characters').optional(),
  permission_ids: z.array(z.number().int().positive()).refine(
    (ids) => new Set(ids).size === ids.length,
    'A permission may only be selected once',
  ),
});

export const unitSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Unit name is required')
    .max(100, 'Use at most 100 characters'),
  code: z.string().trim().min(1, 'Unit code is required').max(30, 'Use at most 30 characters'),
  allow_decimal: z.boolean(),
});

export const productCategorySchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Category name is required')
    .max(100, 'Use at most 100 characters'),
  parent_id: z.number().int().positive().nullable(),
  is_active: z.boolean(),
});

export const productSchema = z.object({
  sku: z
    .string()
    .trim()
    .min(1, 'Product SKU is required')
    .max(50, 'Use at most 50 characters')
    .regex(
      usernamePattern,
      'SKU must start with a letter or digit and contain only letters, numbers, dots, hyphens, or underscores',
    ),
  name: z
    .string()
    .trim()
    .min(1, 'Product name is required')
    .max(255, 'Use at most 255 characters'),
  type: z.enum(['RAW', 'FINISHED', 'TRADING'] as const),
  category_id: z.number().int().positive('Category is required'),
  unit_id: z.number().int().positive('Unit is required'),
  is_stocked: z.boolean(),
  reorder_level: z.coerce.number().min(0, 'Reorder level cannot be negative'),
  sales_price_default: z.coerce.number().min(0, 'Sales price cannot be negative'),
  description: z.string().max(1000, 'Use at most 1000 characters').optional().nullable(),
  is_active: z.boolean(),
});

export const warehouseSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Warehouse name is required')
    .max(100, 'Use at most 100 characters'),
  code: z
    .string()
    .trim()
    .min(1, 'Warehouse code is required')
    .max(30, 'Use at most 30 characters'),
  address: z.string().trim().max(255, 'Use at most 255 characters').optional().nullable(),
  is_default: z.boolean(),
  is_active: z.boolean(),
});

export const assetSchema = z.object({
  asset_code: z.string().trim().min(1, 'Asset code is required').max(50),
  name: z.string().trim().min(1, 'Asset name is required').max(150),
  category: z.string().trim().min(1, 'Category is required').max(100),
  purchase_date: z.string().min(1, 'Purchase date is required'),
  purchase_cost: z.coerce.number().min(0, 'Cost cannot be negative'),
  location: z.string().trim().min(1, 'Location is required').max(150),
  status: z.enum(['IN_USE', 'IN_STORE', 'UNDER_MAINTENANCE', 'DISPOSED']),
});

export const assetAssignmentSchema = z.object({
  location: z.string().trim().min(1, 'Location is required').max(150),
  assigned_on: z.string().min(1, 'Assigned date is required'),
});

export const assetMaintenanceSchema = z.object({
  maintenance_date: z.string().min(1, 'Maintenance date is required'),
  description: z.string().trim().min(1, 'Description is required').max(2000),
  cost: z.coerce.number().min(0, 'Cost cannot be negative'),
  next_due_date: z.string().optional(),
});

export const employeeSchema = z.object({
  code: z.string().trim().min(1, 'Employee code is required').max(50),
  name: z.string().trim().min(1, 'Employee name is required').max(150),
  mobile: z
    .string()
    .trim()
    .min(1, 'Mobile number is required')
    .max(11, 'Use an 11-digit Bangladesh mobile number')
    .regex(/^01[3-9]\d{8}$/, 'Use a valid Bangladesh mobile number, e.g. 01712345678'),
  email: z
    .string()
    .trim()
    .max(255, 'Use at most 255 characters')
    .email('Enter a valid email address')
    .or(z.literal(''))
    .nullable()
    .optional(),
  designation: z.string().trim().max(100).optional(),
  department: z.string().trim().max(100).optional(),
  join_date: z.string().date('Enter a valid joining date'),
  base_salary: z
    .string()
    .regex(/^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/, 'Salary must be nonnegative with at most 2 decimals'),
});

const attendanceTime = z
  .string()
  .regex(/^$|^(?:[01]\d|2[0-3]):[0-5]\d$/, 'Enter a valid time')
  .transform((value) => value || null);

export const attendanceCreateSchema = z.object({
  employee_id: z.number().int().positive('Choose an employee'),
  att_date: z.string().date('Enter a valid attendance date'),
  status: z.enum(['PRESENT', 'ABSENT', 'LEAVE', 'LATE'] as const),
  in_time: attendanceTime,
  out_time: attendanceTime,
});

export const attendanceUpdateSchema = z.object({
  status: z.enum(['PRESENT', 'ABSENT', 'LEAVE', 'LATE'] as const),
  in_time: attendanceTime,
  out_time: attendanceTime,
});

export const attendanceDateRangeSchema = z
  .object({
    from_date: z.string().date('Enter a valid start date'),
    to_date: z.string().date('Enter a valid end date'),
  })
  .refine((value) => value.from_date <= value.to_date, {
    message: 'Start date cannot be after end date',
    path: ['to_date'],
  });

export const payrollRunSchema = z.object({
  period_month: z.number().int().min(1).max(12),
  period_year: z.number().int().min(2000).max(9999),
});

export const payrollDeductionSchema = z.object({
  deductions: z
    .string()
    .trim()
    .regex(/^\d{1,16}(?:\.\d{1,2})?$/, 'Enter a nonnegative amount with up to 2 decimals'),
});

export const payrollPostSchema = z.object({
  account_id: z.number().int().positive('Choose a money account'),
  paid_on: z.string().date('Enter a valid payment date'),
});

export const bomSchema = z.object({
  code: z.string().trim().min(1, 'BOM code is required').max(50, 'Use at most 50 characters'),
  finished_product_id: z.number().int().positive('Choose a finished product'),
  output_qty: z
    .string()
    .regex(/^(?:0|[1-9]\d{0,14})(?:\.\d{1,3})?$/, 'Output quantity must have at most 3 decimals')
    .refine((value) => Number(value) > 0, 'Output quantity must be greater than zero'),
  labor_cost_default: z
    .string()
    .regex(/^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/, 'Labor cost must have at most 2 decimals'),
  overhead_cost_default: z
    .string()
    .regex(/^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/, 'Overhead cost must have at most 2 decimals'),
  lines: z
    .array(
      z.object({
        raw_product_id: z.number().int().positive('Choose a raw material'),
        qty: z
          .string()
          .regex(/^(?:0|[1-9]\d{0,14})(?:\.\d{1,3})?$/, 'Quantity must have at most 3 decimals')
          .refine((value) => Number(value) > 0, 'Quantity must be greater than zero'),
      }),
    )
    .min(1, 'Add at least one raw material')
    .max(500, 'A BOM may contain at most 500 raw materials')
    .refine(
      (lines) => new Set(lines.map((line) => line.raw_product_id)).size === lines.length,
      'A raw material may only appear once',
    ),
});

export const productionOrderSchema = z.object({
  doc_date: z.string().date('Enter a valid production date'),
  bom_id: z.number().int().positive('Choose a BOM'),
  sales_order_line_id: z.number().int().positive().nullable(),
  planned_qty: z
    .string()
    .regex(/^(?:0|[1-9]\d{0,14})(?:\.\d{1,3})?$/, 'Planned quantity must have at most 3 decimals')
    .refine((value) => Number(value) > 0, 'Planned quantity must be greater than zero'),
  warehouse_id: z.number().int().positive('Choose a warehouse'),
});

export const productionOrderCompleteSchema = z.object({
  actual_qty: z
    .string()
    .regex(/^(?:0|[1-9]\d{0,14})(?:\.\d{1,3})?$/, 'Actual quantity must have at most 3 decimals')
    .refine((value) => Number(value) > 0, 'Actual quantity must be greater than zero'),
  labor_cost: z
    .string()
    .regex(/^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/, 'Labor cost must have at most 2 decimals'),
  overhead_cost: z
    .string()
    .regex(/^(?:0|[1-9]\d{0,15})(?:\.\d{1,2})?$/, 'Overhead cost must have at most 2 decimals'),
});

export const stockTransferSchema = z
  .object({
    doc_date: z.string().date('Enter a valid transfer date'),
    from_warehouse_id: z.number().int().positive('Choose a source warehouse'),
    to_warehouse_id: z.number().int().positive('Choose a destination warehouse'),
    note: z.string().trim().max(1000, 'Use at most 1000 characters').nullable(),
    lines: z
      .array(
        z.object({
          product_id: z.number().int().positive('Choose a product'),
          qty: z
            .string()
            .regex(
              /^(?:0|[1-9]\d{0,14})(?:\.\d{1,3})?$/,
              'Quantity must be positive with at most 3 decimal places',
            )
            .refine((value) => Number(value) > 0, 'Quantity must be greater than zero'),
        }),
      )
      .min(1, 'Add at least one product')
      .max(500, 'A transfer may contain at most 500 products')
      .refine(
        (items) => new Set(items.map((item) => item.product_id)).size === items.length,
        'A product may only be selected once',
      ),
  })
  .refine((value) => value.from_warehouse_id !== value.to_warehouse_id, {
    message: 'Choose different source and destination warehouses',
    path: ['to_warehouse_id'],
  });

export const stockAdjustmentSchema = z.object({
  doc_date: z.string().date('Enter a valid adjustment date'),
  warehouse_id: z.number().int().positive('Choose a warehouse'),
  reason: z.string().trim().min(1, 'Enter an adjustment reason').max(500),
  lines: z
    .array(
      z.object({
        product_id: z.number().int().positive('Choose a product'),
        qty_signed: z
          .string()
          .regex(
            /^-?(?:0|[1-9]\d{0,14})(?:\.\d{1,3})?$/,
            'Quantity must be nonzero with at most 3 decimal places',
          )
          .refine((value) => Number(value) !== 0, 'Quantity must not be zero'),
      }),
    )
    .min(1, 'Add at least one product')
    .max(500, 'An adjustment may contain at most 500 products')
    .refine(
      (items) => new Set(items.map((item) => item.product_id)).size === items.length,
      'A product may only be selected once',
    ),
});

export const physicalCountLinesSchema = z.object({
lines: z
  .array(
    z.object({
      product_id: z.number().int().positive(),
      counted_qty: z
        .string()
        .regex(
          /^(?:0|[1-9]\d{0,14})(?:\.\d{1,3})?$/,
          'Counted quantity must be nonnegative with at most 3 decimal places',
        ),
    }),
  )
  .min(1, 'Enter at least one counted quantity')
  .refine(
    (items) => new Set(items.map((item) => item.product_id)).size === items.length,
    'A product may only be counted once',
  ),
});

export const expenseCategorySchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Category name is required')
    .max(100, 'Use at most 100 characters'),
  parent_id: z.number().int().positive().nullable(),
  is_active: z.boolean(),
});

export const incomeCategorySchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Category name is required')
    .max(100, 'Use at most 100 characters'),
  is_active: z.boolean(),
});

export const paymentMethodSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Payment method name is required')
    .max(100, 'Use at most 100 characters'),
  type: z.enum(['CASH', 'BANK', 'MFS', 'ONLINE'] as const),
  is_active: z.boolean(),
});

export const moneyAccountSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Money account name is required')
    .max(100, 'Use at most 100 characters'),
  type: z.enum(['CASH', 'BANK', 'MFS'] as const),
  payment_method_id: z.number().int().positive().nullable(),
  account_no: z.string().trim().max(50, 'Use at most 50 characters').optional().nullable(),
  opening_balance: z.coerce.number(),
  allow_overdraft: z.boolean(),
  is_active: z.boolean(),
});

export const priceListSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Price list name is required')
    .max(100, 'Use at most 100 characters'),
  is_default: z.boolean(),
  valid_from: z.string().trim().max(10).nullable().optional(),
  valid_to: z.string().trim().max(10).nullable().optional(),
  is_active: z.boolean(),
});

export const productPriceSchema = z.object({
  product_id: z.number().int().positive(),
  price: z.coerce.number().min(0, 'Price must be zero or greater'),
});

export const companySettingSchema = z.object({
  key: z
    .string()
    .trim()
    .min(1, 'Setting key is required')
    .max(100, 'Use at most 100 characters'),
  value: z.string(),
});

const companyPhonePattern = /^\+?[0-9][0-9 ()-]{5,28}[0-9]$/;
const timezonePattern = /^[A-Za-z][A-Za-z0-9._+-]*(?:\/[A-Za-z0-9._+-]+)+$/;
const decimalSettingPattern = /^\+?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

export const companySettingValueSchemas = {
  company_name: z.string().trim().min(1, 'Company name is required').max(255),
  company_email: z
    .string()
    .trim()
    .max(255, 'Use at most 255 characters')
    .email('Enter a valid email address')
    .or(z.literal('')),
  company_phone: z
    .string()
    .trim()
    .max(30, 'Use at most 30 characters')
    .refine(
      (value) => value === '' || companyPhonePattern.test(value),
      'Enter a valid phone number with 7 to 30 digits',
    ),
  company_address: z.string().trim().max(1000, 'Use at most 1000 characters'),
  currency_code: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{3}$/, 'Enter a three-letter currency code')
    .transform((value) => value.toUpperCase()),
  timezone: z
    .string()
    .trim()
    .max(100, 'Use at most 100 characters')
    .refine(
      (value) => value === 'UTC' || timezonePattern.test(value),
      'Enter UTC or an IANA-style timezone',
    ),
  invoice_footer: z.string().max(1000, 'Use at most 1000 characters'),
  credit_limit_mode: z
    .string()
    .trim()
    .toUpperCase()
    .refine((value) => value === 'WARN' || value === 'BLOCK', 'Choose WARN or BLOCK'),
  receipt_tolerance_pct: z
    .string()
    .trim()
    .regex(decimalSettingPattern, 'Enter a non-negative number')
    .refine(
      (value) => Number(value) >= 0,
      'Receiving tolerance must be non-negative',
    ),
} satisfies Record<string, z.ZodType<string>>;

export const customerSchema = z.object({
  code: z.string().trim().min(1, 'Customer code is required').max(30, 'Use at most 30 characters'),
  name: z.string().trim().min(1, 'Customer name is required').max(255, 'Use at most 255 characters'),
  mobile: optionalPartyBangladeshMobile,
  email: z.string().trim().max(255, 'Use at most 255 characters').nullable().optional(),
  address: z.string().trim().max(1000, 'Use at most 1000 characters').nullable().optional(),
  credit_limit: z.coerce.number().min(0),
  opening_due: z.coerce.number(),
  price_list_id: z.number().int().positive().nullable().optional(),
  is_active: z.boolean(),
});

export const supplierSchema = z.object({
  code: z.string().trim().min(1, 'Supplier code is required').max(30, 'Use at most 30 characters'),
  name: z.string().trim().min(1, 'Supplier name is required').max(255, 'Use at most 255 characters'),
  mobile: optionalPartyBangladeshMobile,
  email: z.string().trim().max(255, 'Use at most 255 characters').nullable().optional(),
  address: z.string().trim().max(1000, 'Use at most 1000 characters').nullable().optional(),
  opening_due: z.coerce.number(),
  is_active: z.boolean(),
});

const purchaseOrderQuantity = z
  .string()
  .regex(/^\d{1,15}(?:\.\d{1,3})?$/, 'Enter a quantity with up to 3 decimal places')
  .refine((value) => /[1-9]/.test(value), 'Quantity must be greater than zero');
const purchaseOrderUnitPrice = z
  .string()
  .regex(/^\d{1,16}(?:\.\d{1,2})?$/, 'Enter an amount with up to 2 decimal places');

export const purchaseOrderSchema = z.object({
  doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid document date'),
  supplier_id: z.number().int().positive('Select a supplier'),
  warehouse_id: z.number().int().positive('Select a warehouse'),
  expected_date: z
    .string()
    .regex(/^$|^\d{4}-\d{2}-\d{2}$/, 'Enter a valid expected date')
    .transform((value) => value || null),
  discount: z
    .string()
    .regex(/^\d{1,16}(?:\.\d{1,2})?$/, 'Enter a discount with up to 2 decimal places'),
  note: z.string().max(2000, 'Use at most 2000 characters'),
  lines: z
    .array(
      z.object({
        product_id: z.number().int().positive('Select a product'),
        qty: purchaseOrderQuantity,
        unit_price: purchaseOrderUnitPrice,
      }),
    )
    .min(1, 'Add at least one product')
    .max(500, 'A purchase order can have at most 500 lines'),
});

export const goodsReceiptSchema = z.object({
  doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid receipt date'),
  po_id: z.number().int().positive('Select an approved purchase order'),
  note: z.string().max(2000, 'Use at most 2000 characters'),
  lines: z
    .array(
      z.object({
        po_line_id: z.number().int().positive(),
        qty: purchaseOrderQuantity,
        unit_cost: z
          .string()
          .regex(/^\d{1,14}(?:\.\d{1,4})?$/, 'Enter a unit cost with up to 4 decimal places'),
      }),
    )
    .min(1, 'Enter quantities for at least one purchase order line')
    .max(500, 'A receipt can have at most 500 lines'),
});

export const directPurchaseSchema = z.object({
  doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid purchase date'),
  supplier_id: z.number().int().positive('Select a supplier'),
  warehouse_id: z.number().int().positive('Select a warehouse'),
  note: z.string().max(2000, 'Use at most 2000 characters'),
  lines: z
    .array(
      z.object({
        product_id: z.number().int().positive('Select a product'),
        qty: purchaseOrderQuantity,
        unit_cost: z
          .string()
          .regex(/^\d{1,14}(?:\.\d{1,4})?$/, 'Enter a unit cost with up to 4 decimal places'),
      }),
    )
    .min(1, 'Add at least one product')
    .max(500, 'A direct purchase can have at most 500 lines'),
});

export const quotationSchema = z.object({
  doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid quotation date'),
  customer_id: z.number().int().positive('Select a customer'),
  valid_until: z
    .string()
    .regex(/^$|^\d{4}-\d{2}-\d{2}$/, 'Enter a valid expiry date')
    .transform((value) => value || null),
  discount: z
    .string()
    .regex(/^\d{1,16}(?:\.\d{1,2})?$/, 'Enter a discount with up to 2 decimal places'),
  note: z.string().max(2000, 'Use at most 2000 characters'),
  lines: z
    .array(
      z.object({
        product_id: z.number().int().positive('Select a product'),
        qty: purchaseOrderQuantity,
        unit_price: purchaseOrderUnitPrice,
      }),
    )
    .min(1, 'Add at least one product')
    .max(500, 'A quotation can have at most 500 lines'),
});

export const quotationConversionSchema = z.object({
  doc_date: z.string().date('Enter a valid order date'),
  warehouse_id: z.number().int().positive('Select a warehouse'),
  delivery_date: z
    .string()
    .regex(/^$|^\d{4}-\d{2}-\d{2}$/, 'Enter a valid delivery date')
    .transform((value) => value || null),
});

export const salesOrderSchema = z.object({
  doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid order date'),
  customer_id: z.number().int().positive('Select a customer'),
  warehouse_id: z.number().int().positive('Select a warehouse'),
  delivery_date: z
    .string()
    .regex(/^$|^\d{4}-\d{2}-\d{2}$/, 'Enter a valid delivery date')
    .transform((value) => value || null),
  discount: z
    .string()
    .regex(/^\d{1,16}(?:\.\d{1,2})?$/, 'Enter a discount with up to 2 decimal places'),
  note: z.string().max(2000, 'Use at most 2000 characters'),
  lines: z
    .array(
      z.object({
        product_id: z.number().int().positive('Select a product'),
        qty_ordered: purchaseOrderQuantity,
        unit_price: purchaseOrderUnitPrice,
      }),
    )
    .min(1, 'Add at least one product')
    .max(500, 'A sales order can have at most 500 lines'),
});

export const salesOrderReservationSchema = z.object({
  qty: purchaseOrderQuantity,
});

export const salesDeliverySchema = z.object({
  doc_date: z.string().date('Enter a valid delivery date'),
  lines: z
    .array(
      z.object({
        order_line_id: z.number().int().positive(),
        qty: purchaseOrderQuantity,
      }),
    )
    .min(1, 'Enter a delivery quantity for at least one order line')
    .max(500, 'A delivery can contain at most 500 lines')
    .refine(
      (items) => new Set(items.map((item) => item.order_line_id)).size === items.length,
      'An order line may only be selected once',
    ),
});

export const salesInvoiceSchema = z
  .object({
    delivery_id: z.number().int().positive('Select a delivery'),
    doc_date: z.string().date('Enter a valid invoice date'),
    due_date: z.string().date('Enter a valid due date'),
  })
  .refine((value) => value.due_date >= value.doc_date, {
    message: 'Due date cannot precede invoice date',
    path: ['due_date'],
  });

export const purchaseReturnSchema = z.object({
  doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid return date'),
  receipt_id: z.number().int().positive('Select a goods receipt'),
  note: z.string().max(2000, 'Use at most 2000 characters'),
  lines: z
    .array(
      z.object({
        receipt_line_id: z.number().int().positive(),
        qty: purchaseOrderQuantity,
      }),
    )
    .min(1, 'Enter quantities for at least one receipt line')
    .max(500, 'A purchase return can have at most 500 lines'),
});

export const salesReturnSchema = z.object({
  doc_date: z.string().date('Enter a valid return date'),
  invoice_id: z.number().int().positive('Select an invoice'),
  note: z.string().max(2000, 'Use at most 2000 characters'),
  lines: z
    .array(
      z.object({
        invoice_line_id: z.number().int().positive(),
        qty: purchaseOrderQuantity,
      }),
    )
    .min(1, 'Enter a return quantity for at least one invoice line')
    .max(500, 'A return may contain at most 500 invoice lines')
    .refine(
      (items) => new Set(items.map((item) => item.invoice_line_id)).size === items.length,
      'An invoice line may only be selected once',
    ),
});

export function moneyAmountToCents(value: string): bigint | null {
  const match = /^(\d{1,16})(?:\.(\d{1,2}))?$/.exec(value);
  if (!match) return null;
  return BigInt(match[1]) * 100n + BigInt((match[2] ?? '').padEnd(2, '0') || '0');
}

const moneyAmount = z
  .string()
  .regex(/^\d{1,16}(?:\.\d{1,2})?$/, 'Enter an amount with up to 2 decimal places')
  .refine((value) => /[1-9]/.test(value), 'Amount must be greater than zero');

export const customerCollectionSchema = z.object({
  doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid collection date'),
  customer_id: z.number().int().positive('Select a customer'),
  account_id: z.number().int().positive('Select a money account'),
  amount: moneyAmount,
  method_ref: z.string().trim().max(100, 'Use at most 100 characters').optional(),
  note: z.string().max(2000, 'Use at most 2000 characters').optional(),
});

export const supplierPaymentSchema = z.object({
  doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid payment date'),
  supplier_id: z.number().int().positive('Select a supplier'),
  account_id: z.number().int().positive('Select a money account'),
  amount: moneyAmount,
  note: z.string().max(2000, 'Use at most 2000 characters').optional(),
  allocations: z
    .array(
      z.object({
        ref_type: z.enum(['RECEIPT', 'DIRECT_PURCHASE'] as const),
        ref_id: z.number().int().positive(),
        amount: moneyAmount,
      }),
    )
    .max(100, 'A payment can be allocated to at most 100 bills'),
}).superRefine((value, context) => {
  const paymentCents = moneyAmountToCents(value.amount);
  const allocationCents = value.allocations.map((allocation) =>
    moneyAmountToCents(allocation.amount),
  );
  if (
    paymentCents !== null &&
    allocationCents.every((amount) => amount !== null) &&
    allocationCents.reduce((total, amount) => total + (amount ?? 0n), 0n) > paymentCents
  ) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Bill allocations cannot exceed the payment amount',
      path: ['allocations'],
    });
  }
});

const optionalPartyEmail = z
  .string()
  .trim()
  .max(255, 'Use at most 255 characters')
  .email('Enter a valid email address')
  .nullable()
  .optional();

export const partyContactSchema = z.object({
  name: z.string().trim().min(1, 'Contact name is required').max(255),
  phone: optionalPartyBangladeshMobile,
  email: optionalPartyEmail,
  designation: z.string().trim().max(100, 'Use at most 100 characters').nullable().optional(),
});

export const documentNumberingSchema = z.object({
  doc_type: z.string().trim().min(1, 'Document type is required').max(50, 'Use at most 50 characters'),
  prefix: z.string().trim().min(1, 'Prefix is required').max(30, 'Use at most 30 characters'),
  year: z.coerce.number().int().min(1900).max(9999),
  last_number: z.coerce.number().int().min(0),
  padding: z.coerce.number().int().min(1).max(10),
});

export const expenseSchema = z.object({
  doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid expense date'),
  category_id: z.number().int().positive('Select an expense category'),
  account_id: z.number().int().positive('Select a money account'),
  amount: moneyAmount,
  paid_to: z.string().trim().max(200, 'Use at most 200 characters').optional(),
  note: z.string().max(2000, 'Use at most 2000 characters').optional(),
});

export const incomeSchema = z.object({
  doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid income date'),
  category_id: z.number().int().positive('Select an income category'),
  account_id: z.number().int().positive('Select a money account'),
  amount: moneyAmount,
  note: z.string().max(2000, 'Use at most 2000 characters').optional(),
});

export const fundTransferSchema = z
  .object({
    doc_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Enter a valid transfer date'),
    from_account_id: z.number().int().positive('Select a source money account'),
    to_account_id: z.number().int().positive('Select a destination money account'),
    amount: moneyAmount,
    note: z.string().max(2000, 'Use at most 2000 characters').optional(),
  })
  .refine((data) => data.from_account_id !== data.to_account_id, {
    message: 'Source and destination accounts must be different',
    path: ['to_account_id'],
  });
