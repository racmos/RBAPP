import type { ErrorDetail } from '@/api/types';

/** Client-side mirror of the server's `RegisterRequest`, so common mistakes do not burn the captcha payload. */
export const USERNAME_PATTERN = /^[A-Za-z0-9_.-]{3,32}$/;
export const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
export const EMAIL_MAX_LENGTH = 120;
export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 128;

export type RegisterValues = { username: string; email: string; password: string };

const detail = (
  field: keyof RegisterValues,
  code: string,
  params?: ErrorDetail['params'],
): ErrorDetail => ({ field, code, params, message: code, type: 'client_check' });

/** Problems with the form values, in field order, as details the translators understand. */
export function checkRegister({ username, email, password }: RegisterValues): ErrorDetail[] {
  const problems: ErrorDetail[] = [];

  if (!username.trim()) problems.push(detail('username', 'required'));
  else if (!USERNAME_PATTERN.test(username.trim()))
    problems.push(detail('username', 'invalid_format'));

  const mail = email.trim();
  if (!mail) problems.push(detail('email', 'required'));
  else if (mail.length > EMAIL_MAX_LENGTH)
    problems.push(detail('email', 'too_long', { max: EMAIL_MAX_LENGTH }));
  else if (!EMAIL_PATTERN.test(mail)) problems.push(detail('email', 'invalid_format'));

  if (!password) problems.push(detail('password', 'required'));
  else if (password.length < PASSWORD_MIN_LENGTH) {
    problems.push(detail('password', 'too_short', { min: PASSWORD_MIN_LENGTH }));
  } else if (password.length > PASSWORD_MAX_LENGTH) {
    problems.push(detail('password', 'too_long', { max: PASSWORD_MAX_LENGTH }));
  }
  return problems;
}
