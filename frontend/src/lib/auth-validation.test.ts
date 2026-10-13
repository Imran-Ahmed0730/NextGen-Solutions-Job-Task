import { describe, expect, it } from 'vitest';

import {
  changePasswordSchema,
  forgotPasswordSchema,
  loginSchema,
  productCategorySchema,
  profileSchema,
  resetPasswordSchema,
  roleSchema,
  unitSchema,
  userSchema,
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
});

