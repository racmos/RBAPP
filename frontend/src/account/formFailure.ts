import type { i18n as I18n } from 'i18next';
import { ApiError } from '@/api/errors';
import type { ErrorDetail } from '@/api/types';
import { fieldErrorsFromDetails, type FieldErrors } from '@/auth/formHelpers';
import { translateError } from '@/i18n';

/** What a failed save shows: the 429 countdown, errors on the fields, or the form alert. */
export type Failure<Name extends string> =
  | { kind: 'retry'; seconds: number }
  | { kind: 'fields'; errors: FieldErrors<Name>; focus: Name | null }
  | { kind: 'form'; message: string };

export function failureOf<Name extends string>(
  error: unknown,
  i18n: I18n,
  fields: readonly Name[],
  /** Error codes that belong to one field (`email_taken` -> `email`). */
  codeFields: Partial<Record<string, Name>> = {},
): Failure<Name> {
  if (error instanceof ApiError && error.status === 429 && error.retryAfter) {
    return { kind: 'retry', seconds: error.retryAfter };
  }
  if (error instanceof ApiError && error.kind === 'http') {
    const field = error.code ? codeFields[error.code] : undefined;
    if (field) {
      return {
        kind: 'fields',
        errors: { [field]: translateError(error, i18n) } as FieldErrors<Name>,
        focus: field,
      };
    }
    const mapped = fieldErrorsFromDetails(error.details, i18n, fields);
    if (Object.keys(mapped).length > 0) return { kind: 'fields', errors: mapped, focus: null };
  }
  return { kind: 'form', message: translateError(error, i18n) };
}

/** A client-side check written as a server detail, so the same translators read it. */
export const problem = (
  field: string,
  code: string,
  params?: ErrorDetail['params'],
): ErrorDetail => ({
  field,
  code,
  params,
  message: code,
  type: 'client_check',
});
