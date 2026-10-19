import { beforeEach, describe, expect, it } from 'vitest';
import { ApiError } from '@/api/errors';
import { createI18n } from './index';
import { translateDetail, translateError } from './translateError';

const http = (status: number, extra: Partial<ConstructorParameters<typeof ApiError>[0]> = {}) =>
  new ApiError({ kind: 'http', status, ...extra });

let i18n: Awaited<ReturnType<typeof createI18n>>;
beforeEach(async () => {
  i18n = await createI18n('es');
});

describe('translateError (I18N-4)', () => {
  it('uses the catalog text for a known code, not the API message', () => {
    const error = http(409, { code: 'username_taken', message: 'Username already exists' });
    const text = translateError(error, i18n);
    expect(text).toBe(i18n.t('errors:code.username_taken'));
    expect(text).not.toContain('already exists');
  });

  it('follows the active language', async () => {
    const error = http(409, { code: 'email_taken', message: 'Email already registered' });
    const es = translateError(error, i18n);
    await i18n.changeLanguage('en');
    const en = translateError(error, i18n);
    expect(es).not.toBe(en);
    expect(en).toBe(i18n.t('errors:code.email_taken'));
  });

  it('interpolates params such as retry_after', () => {
    const text = translateError(http(429, { code: 'locked', params: { retry_after: 30 } }), i18n);
    expect(text).toContain('30');
  });

  it('falls back to the retry_after taken from the header when params lack it', () => {
    const text = translateError(http(429, { code: 'rate_limited', retryAfter: 45 }), i18n);
    expect(text).toContain('45');
  });

  it('shows the API message for a code the catalog does not know', () => {
    const error = http(400, { code: 'brand_new_code', message: 'Something odd' });
    expect(translateError(error, i18n)).toBe('Something odd');
  });

  it('shows the API message when there is no code', () => {
    expect(translateError(http(418, { message: 'I am a teapot' }), i18n)).toBe('I am a teapot');
  });

  it('uses errors:status.<n> when there is neither code nor message', () => {
    expect(translateError(http(503), i18n)).toBe(i18n.t('errors:status.503'));
  });

  it('uses errors:unknown when nothing else applies', () => {
    expect(translateError(http(418), i18n)).toBe(i18n.t('errors:unknown'));
    expect(translateError(new Error('boom'), i18n)).toBe(i18n.t('errors:unknown'));
    expect(translateError('weird', i18n)).toBe(i18n.t('errors:unknown'));
  });

  it('uses errors:network for network and timeout failures', () => {
    expect(translateError(new ApiError({ kind: 'network' }), i18n)).toBe(i18n.t('errors:network'));
    expect(translateError(new ApiError({ kind: 'timeout' }), i18n)).toBe(i18n.t('errors:network'));
  });

  it('never returns an empty string', () => {
    for (const error of [
      http(500),
      new ApiError({ kind: 'parse' }),
      new ApiError({ kind: 'network' }),
    ]) {
      expect(translateError(error, i18n).length).toBeGreaterThan(0);
    }
  });
});

describe('translateDetail (field errors)', () => {
  const detail = (
    field: string,
    code: string,
    params?: Record<string, number>,
    message = 'raw message',
  ) => ({
    field,
    code,
    params,
    message,
    type: 'x',
  });

  it('prefers errors:validation.<field>.<code>', () => {
    expect(translateDetail(detail('email', 'invalid_format'), i18n)).toBe(
      i18n.t('errors:validation.email.invalid_format'),
    );
  });

  it('falls back to errors:validation.<code> with params', () => {
    const text = translateDetail(detail('password', 'too_short', { min: 8 }), i18n);
    expect(text).toContain('8');
    expect(text).not.toBe('raw message');
  });

  it('uses the detail message when the code is unknown', () => {
    expect(translateDetail(detail('password', 'mystery'), i18n)).toBe('raw message');
    expect(translateDetail({ field: 'x', message: 'plain', type: 't' }, i18n)).toBe('plain');
  });

  it('uses the generic error when there is nothing to show', () => {
    expect(translateDetail({ field: 'x', message: '', type: 't' }, i18n)).toBe(
      i18n.t('errors:unknown'),
    );
  });
});
