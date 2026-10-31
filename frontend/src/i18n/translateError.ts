import type { i18n as I18n } from 'i18next';
import { ApiError } from '@/api/errors';
import type { ErrorDetail } from '@/api/types';

/**
 * Keys here are built at run time, so they cannot be statically typed; the contract test
 * (`tests/test_frontend_contracts.py`) and the catalog test guard the catalogs instead.
 */
type Translator = Pick<I18n, 'exists'> & { t: (key: string, options?: object) => string };
const loose = (i18n: I18n): Translator => i18n as unknown as Translator;

/** I18N-4 / design 4.7: code, then the API message, then the HTTP status, then a generic text. */
export function translateError(error: unknown, i18n: I18n): string {
  const { t, exists } = loose(i18n);
  if (!(error instanceof ApiError)) return t('errors:unknown');
  if (error.kind === 'network' || error.kind === 'timeout') return t('errors:network');

  if (error.code && exists(`errors:code.${error.code}`)) {
    const retry = error.params?.retry_after ?? error.retryAfter;
    return t(`errors:code.${error.code}`, {
      ...error.params,
      ...(retry === undefined || retry === null ? {} : { retry_after: retry }),
    });
  }
  if (error.serverMessage) return error.serverMessage;
  if (error.status !== null && exists(`errors:status.${error.status}`)) {
    return t(`errors:status.${error.status}`);
  }
  return t('errors:unknown');
}

/** A field error: field-specific text, then the generic text for the code, then the API text. */
export function translateDetail(detail: ErrorDetail, i18n: I18n): string {
  const { t, exists } = loose(i18n);
  if (detail.code) {
    const specific = `errors:validation.${detail.field}.${detail.code}`;
    if (exists(specific)) return t(specific, detail.params);
    const generic = `errors:validation.${detail.code}`;
    if (exists(generic)) return t(generic, detail.params);
  }
  return detail.message || t('errors:unknown');
}
