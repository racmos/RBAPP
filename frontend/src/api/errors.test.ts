import { describe, expect, it } from 'vitest';
import { ApiError, deriveCode, errorFromResponse } from './errors';

const headers = (init: Record<string, string> = {}) => new Headers(init);

describe('deriveCode (F0 bodies without a code)', () => {
  it.each([
    [401, 'Unauthorized', 'Invalid credentials', 'invalid_credentials'],
    [401, 'Unauthorized', 'Authentication is required', 'unauthenticated'],
    [409, 'Conflict', 'Username already exists', 'username_taken'],
    [409, 'Conflict', 'Email already registered', 'email_taken'],
    [429, 'Too Many Requests', 'Invalid credentials or account temporarily locked', 'locked'],
    [
      429,
      'Too Many Requests',
      'Too many requests. Please wait before trying again.',
      'rate_limited',
    ],
    [400, 'CSRF Error', 'The CSRF token is missing.', 'csrf_invalid'],
    [400, 'Captcha Error', 'Captcha verification failed', 'captcha_failed'],
    [400, 'Validation Error', 'Invalid request data', 'validation_error'],
  ])('maps %i %s "%s" to %s', (status, error, message, code) => {
    expect(deriveCode(error, status, message)).toBe(code);
  });

  it.each([
    [404, 'Not Found', 'The requested resource was not found'],
    [500, 'Internal Server Error', 'An unexpected error occurred'],
    [409, 'Conflict', 'Something else is in conflict'],
  ])('leaves %i %s without a code', (status, error, message) => {
    expect(deriveCode(error, status, message)).toBeNull();
  });
});

describe('errorFromResponse', () => {
  it('keeps the code the server sent and does not derive over it', () => {
    const error = errorFromResponse(
      409,
      {
        success: false,
        error: 'Conflict',
        message: 'Email already registered',
        code: 'username_taken',
      },
      headers(),
    );
    expect(error.kind).toBe('http');
    expect(error.status).toBe(409);
    expect(error.code).toBe('username_taken');
  });

  it('derives the code of an F0 body that has none', () => {
    const error = errorFromResponse(
      409,
      { success: false, error: 'Conflict', message: 'Email already registered' },
      headers(),
    );
    expect(error.code).toBe('email_taken');
    expect(error.message).toBe('Email already registered');
  });

  it('reads retryAfter from the header first, then from params.retry_after', () => {
    const body = {
      success: false,
      error: 'x',
      message: 'm',
      code: 'locked',
      params: { retry_after: 99 },
    };
    expect(errorFromResponse(429, body, headers({ 'Retry-After': '30' })).retryAfter).toBe(30);
    expect(errorFromResponse(429, body, headers()).retryAfter).toBe(99);
  });

  it('ignores a Retry-After that is not a positive whole number of seconds', () => {
    const body = { success: false, error: 'x', message: 'm', code: 'rate_limited' };
    expect(errorFromResponse(429, body, headers({ 'Retry-After': 'soon' })).retryAfter).toBeNull();
    expect(errorFromResponse(429, body, headers({ 'Retry-After': '0' })).retryAfter).toBeNull();
    expect(errorFromResponse(400, body, headers()).retryAfter).toBeNull();
  });

  it('keeps field details with their codes and params', () => {
    const error = errorFromResponse(
      400,
      {
        success: false,
        error: 'Validation Error',
        message: 'Invalid request data',
        code: 'validation_error',
        details: [
          {
            field: 'password',
            message: 'too short',
            type: 'string_too_short',
            code: 'too_short',
            params: { min: 8 },
          },
        ],
      },
      headers(),
    );
    expect(error.details).toEqual([
      {
        field: 'password',
        message: 'too short',
        type: 'string_too_short',
        code: 'too_short',
        params: { min: 8 },
      },
    ]);
  });

  it('tolerates a body that is not the error envelope', () => {
    const error = errorFromResponse(502, 'Bad gateway', headers());
    expect(error.kind).toBe('http');
    expect(error.status).toBe(502);
    expect(error.code).toBeNull();
    expect(error.details).toEqual([]);
  });
});

describe('ApiError kinds', () => {
  it.each(['network', 'timeout', 'parse'] as const)('has no status for kind %s', (kind) => {
    const error = new ApiError({ kind });
    expect(error).toBeInstanceOf(Error);
    expect(error.kind).toBe(kind);
    expect(error.status).toBeNull();
    expect(error.code).toBeNull();
  });
});
