import { describe, expect, it } from 'vitest';

import { ApiError } from '@/lib/auth-api';
import { getApiFieldErrors, getFieldErrors } from './field-error';

describe('field-error helpers', () => {
  describe('getFieldErrors', () => {
    it('maps Zod validation issues into an object by path', () => {
      const issues = [
        { path: ['username'], message: 'Username is required' },
        { path: ['password'], message: 'Use at least 8 characters' },
        { path: ['username'], message: 'Second issue for username' },
      ];
      const errors = getFieldErrors(issues);
      expect(errors).toEqual({
        username: 'Username is required',
        password: 'Use at least 8 characters',
      });
    });
  });

  describe('getApiFieldErrors', () => {
    it('returns empty object for non-ApiError cause', () => {
      expect(getApiFieldErrors(new Error('Network error'))).toEqual({});
      expect(getApiFieldErrors(null)).toEqual({});
    });

    it('handles 409 duplicate errors', () => {
      expect(
        getApiFieldErrors(new ApiError('Username is already in use', 409)),
      ).toEqual({ username: 'Username is already in use' });

      expect(
        getApiFieldErrors(new ApiError('Email is already in use', 409)),
      ).toEqual({ email: 'Email is already in use' });

      expect(
        getApiFieldErrors(new ApiError('Mobile is already in use', 409)),
      ).toEqual({ mobile: 'Mobile is already in use' });

      expect(
        getApiFieldErrors(new ApiError('Role name is already in use', 409)),
      ).toEqual({ name: 'Role name is already in use' });

      expect(
        getApiFieldErrors(new ApiError('Unit code is already in use', 409)),
      ).toEqual({ code: 'Unit code is already in use' });

      expect(
        getApiFieldErrors(new ApiError('Product SKU is already in use', 409)),
      ).toEqual({ sku: 'Product SKU is already in use' });
    });

    it('handles password mismatch errors', () => {
      expect(
        getApiFieldErrors(new ApiError('Current password is incorrect', 400)),
      ).toEqual({ current_password: 'Current password is incorrect' });

      expect(
        getApiFieldErrors(new ApiError('New password must be different', 400)),
      ).toEqual({ new_password: 'New password must be different' });
    });

    it('parses 422 validation error details array', () => {
      const details = [
        { loc: ['body', 'mobile'], msg: 'Value error, String should match pattern' },
        { loc: ['body', 'role_ids'], msg: 'Input should be a valid integer' },
      ];
      const error = new ApiError(JSON.stringify(details), 422);
      expect(getApiFieldErrors(error)).toEqual({
        mobile: 'String should match pattern',
        role_ids: 'Input should be a valid integer',
      });
    });

    it('returns empty object for malformed 422 message', () => {
      const error = new ApiError('Unprocessable Entity', 422);
      expect(getApiFieldErrors(error)).toEqual({});
    });
  });
});
