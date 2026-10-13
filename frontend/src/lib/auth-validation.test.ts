import { describe, expect, it } from 'vitest';

import {
  changePasswordSchema,
  forgotPasswordSchema,
  loginSchema,
  productCategorySchema,
  productSchema,
  profileSchema,
  resetPasswordSchema,
  roleSchema,
  unitSchema,
  userSchema,
  warehouseSchema,
} from './auth-validation';

describe('auth-validation schemas', () => {
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
});

