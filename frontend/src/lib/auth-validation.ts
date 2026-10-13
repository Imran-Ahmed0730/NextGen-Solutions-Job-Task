import { z } from 'zod';

export const loginSchema = z.object({
  username: z.string().trim().min(1, 'Enter your username, email, or mobile number'),
  password: z.string().min(1, 'Enter your password'),
});

export const forgotPasswordSchema = z.object({
  email: z.string().trim().min(1, 'Email address is required').email('Enter a valid email address'),
});

export const resetPasswordSchema = z
  .object({
    token: z.string().trim().min(1, 'Enter the reset token'),
    new_password: z.string().min(8, 'Use at least 8 characters'),
    confirm_password: z.string().min(1, 'Confirm your password'),
  })
  .refine((value) => value.new_password === value.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: z.string().min(8, 'Use at least 8 characters'),
    confirm_password: z.string().min(1, 'Confirm your password'),
  })
  .refine((value) => value.new_password === value.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

export const profileSchema = z.object({
  full_name: z.string().trim().min(1, 'Name is required'),
  email: z.union([z.string().trim().email(), z.literal('')]),
  mobile: z.string().max(30).optional(),
});

export const userSchema = z.object({
  username: z.string().trim().min(1, 'Username is required'),
  full_name: z.string().trim().min(1, 'Name is required'),
  email: z.union([z.string().trim().email(), z.literal('')]),
  mobile: z.string().max(30).optional(),
  password: z.string().optional(),
  role_ids: z.array(z.number()),
});

export const roleSchema = z.object({
  name: z.string().trim().min(1, 'Role name is required'),
  description: z.string().optional(),
  permission_ids: z.array(z.number()),
});

export const unitSchema = z.object({
  name: z.string().trim().min(1, 'Unit name is required').max(100, 'Use at most 100 characters'),
  code: z.string().trim().min(1, 'Unit code is required').max(30, 'Use at most 30 characters'),
  allow_decimal: z.boolean(),
});

export const productCategorySchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Category name is required')
    .max(100, 'Use at most 100 characters'),
  parent_id: z.number().nullable(),
});
