import type { ErrorDetail, ErrorEnvelope, ErrorParams } from './types';

export type ApiErrorKind = 'http' | 'network' | 'timeout' | 'parse';

type ApiErrorInit = {
  kind: ApiErrorKind;
  status?: number | null;
  error?: string | null;
  code?: string | null;
  params?: ErrorParams | null;
  message?: string | null;
  details?: ErrorDetail[];
  retryAfter?: number | null;
};

/** Every failure of an API call. `code` is normalised, so UI code never inspects `message`. */
export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly error: string | null;
  /** The `message` the server sent (English prose); `message` falls back to the kind. */
  readonly serverMessage: string | null;
  readonly code: string | null;
  readonly params: ErrorParams | null;
  readonly details: ErrorDetail[];
  readonly retryAfter: number | null;

  constructor(init: ApiErrorInit) {
    super(init.message ?? init.kind);
    this.name = 'ApiError';
    this.kind = init.kind;
    this.status = init.status ?? null;
    this.error = init.error ?? null;
    this.serverMessage = init.message?.trim() ? init.message : null;
    this.code = init.code ?? null;
    this.params = init.params ?? null;
    this.details = init.details ?? [];
    this.retryAfter = init.retryAfter ?? null;
  }
}

/**
 * The code of an F0-shaped body that carries none (API-9 is additive, so an older server or a
 * handler that was not touched answers with `error` and `message` only). `null` = no code.
 */
export function deriveCode(error: string, status: number, message: string): string | null {
  const text = message.toLowerCase();
  if (status === 401)
    return text.includes('invalid credentials') ? 'invalid_credentials' : 'unauthenticated';
  if (status === 409) {
    if (text.includes('username')) return 'username_taken';
    if (text.includes('email')) return 'email_taken';
    return null;
  }
  if (status === 429) return text.includes('locked') ? 'locked' : 'rate_limited';
  if (status === 400) {
    if (error === 'CSRF Error') return 'csrf_invalid';
    if (error === 'Captcha Error') return 'captcha_failed';
    if (error === 'Validation Error') return 'validation_error';
  }
  return null;
}

const isEnvelope = (body: unknown): body is Partial<ErrorEnvelope> =>
  typeof body === 'object' && body !== null;

/** A positive whole number of seconds, or null. */
const seconds = (value: unknown): number | null => {
  const text = typeof value === 'string' ? value.trim() : value;
  const parsed = typeof text === 'string' ? (/^\d+$/.test(text) ? Number(text) : NaN) : text;
  return typeof parsed === 'number' && Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};

/** Build the error of an HTTP failure from the decoded body (any shape) and the headers. */
export function errorFromResponse(status: number, body: unknown, headers: Headers): ApiError {
  const envelope = isEnvelope(body) ? body : {};
  const error = typeof envelope.error === 'string' ? envelope.error : null;
  const message = typeof envelope.message === 'string' ? envelope.message : null;
  const code =
    typeof envelope.code === 'string'
      ? envelope.code
      : deriveCode(error ?? '', status, message ?? '');
  const params = envelope.params ?? null;
  return new ApiError({
    kind: 'http',
    status,
    error,
    message,
    code,
    params,
    details: Array.isArray(envelope.details) ? envelope.details : [],
    retryAfter: seconds(headers.get('Retry-After')) ?? seconds(params?.retry_after),
  });
}
