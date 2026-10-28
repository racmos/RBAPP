import { clearCsrfToken, getCsrfToken, setCsrfToken } from './csrf';
import { ApiError, errorFromResponse } from './errors';
import type { SessionData } from './types';

/** Base path of the API; `VITE_API_BASE` overrides it for a dev proxy (D12). */
export const API_BASE: string = import.meta.env.VITE_API_BASE || '/riftbound/api/v1';
export const REQUEST_TIMEOUT_MS = 15_000;

const UNSAFE = new Set(['POST', 'PATCH', 'PUT', 'DELETE']);
/** A 401 on these is an answer, not an expired session (FAUTH-7). */
const AUTH_ANSWER_PATHS = new Set(['/auth/login', '/auth/logout']);

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
export type RequestOptions = { method?: Method; body?: unknown; signal?: AbortSignal };

/** Options objects whose request is already on its single CSRF retry. */
const retrying = new WeakSet<RequestOptions>();

let unauthorizedHandler: (() => void) | null = null;

/** The app registers what happens on an expired session (clear caches, go to /login). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

/** One fetch with the 15 s timeout. Resolves to the response; throws ApiError or the caller's abort. */
async function send(
  path: string,
  { method = 'GET', body, signal }: RequestOptions,
  accept = 'application/json',
): Promise<Response> {
  const headers: Record<string, string> = { Accept: accept };
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  // FormData sets its own multipart boundary; a JSON content type would break it (F13-f).
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
  const token = getCsrfToken();
  if (UNSAFE.has(method) && token) headers['X-CSRFToken'] = token;

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  const relay = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', relay, { once: true });

  try {
    return await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
      credentials: 'same-origin',
      signal: controller.signal,
    });
  } catch (cause) {
    if (timedOut) throw new ApiError({ kind: 'timeout' });
    if (signal?.aborted) throw cause;
    throw new ApiError({ kind: 'network' });
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', relay);
  }
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

let sessionInFlight: Promise<SessionData> | null = null;

/** `GET /auth/session`: the account state and a CSRF token, which it stores. */
export function getSession(): Promise<SessionData> {
  sessionInFlight ??= request<SessionData>('/auth/session')
    .then((data) => {
      setCsrfToken(data.csrf_token);
      return data;
    })
    .finally(() => {
      sessionInFlight = null;
    });
  return sessionInFlight;
}

async function performRequest<T, M = undefined>(
  path: string,
  options: RequestOptions = {},
): Promise<{ data: T; meta: M | undefined }> {
  const unsafe = UNSAFE.has(options.method ?? 'GET');
  if (unsafe && !getCsrfToken()) await getSession();

  const response = await send(path, options);
  const body = await readJson(response);

  if (response.ok) {
    if (typeof body === 'object' && body !== null && 'data' in body && 'success' in body) {
      return {
        data: (body as { data: T }).data,
        meta: 'meta' in body ? (body as { meta: M }).meta : undefined,
      };
    }
    throw new ApiError({ kind: 'parse', status: response.status });
  }

  const error = errorFromResponse(response.status, body, response.headers);
  if (
    unsafe &&
    response.status === 400 &&
    error.code === 'csrf_invalid' &&
    !retrying.has(options)
  ) {
    retrying.add(options);
    try {
      clearCsrfToken();
      await getSession();
      return await performRequest<T, M>(path, options);
    } finally {
      retrying.delete(options);
    }
  }
  if (response.status === 401 && !AUTH_ANSWER_PATHS.has(path)) unauthorizedHandler?.();
  throw error;
}

/**
 * Typed `fetch` wrapper: unwraps `{success, data}`, throws `ApiError`, attaches the CSRF token
 * to unsafe methods (fetching the session first when none is held) and retries once after a
 * stale token (D12, FAUTH-6).
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return performRequest<T, undefined>(path, options).then((result) => result.data);
}

/** A file the API sent as a download (`GET /collection/export`, F3-i). */
export type FileDownload = {
  blob: Blob;
  /** From `Content-Disposition`; null when the server sent none. */
  filename: string | null;
  /** From `X-Rows-Exported`; null when the server sent none. */
  rowsExported: number | null;
};

function dispositionName(header: string | null): string | null {
  if (!header) return null;
  const encoded = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim());
    } catch {
      // fall through to the plain name
    }
  }
  const plain = /filename\s*=\s*("([^"]*)"|[^;]+)/.exec(header);
  if (!plain) return null;
  const name = (plain[2] ?? plain[1]).trim();
  return name || null;
}

/**
 * A `GET` whose success body is a file, not the JSON envelope: same timeout, credentials and
 * error handling as `request` (a failure is still JSON and becomes an `ApiError`).
 */
export async function requestFile(
  path: string,
  { signal }: { signal?: AbortSignal } = {},
): Promise<FileDownload> {
  const response = await send(path, { signal }, 'text/csv, application/json');
  if (!response.ok) {
    const error = errorFromResponse(response.status, await readJson(response), response.headers);
    if (response.status === 401) unauthorizedHandler?.();
    throw error;
  }
  let blob: Blob;
  try {
    blob = await response.blob();
  } catch {
    throw new ApiError({ kind: 'network', status: response.status });
  }
  const rows = Number(response.headers.get('X-Rows-Exported') ?? '');
  return {
    blob,
    filename: dispositionName(response.headers.get('Content-Disposition')),
    rowsExported:
      response.headers.has('X-Rows-Exported') && Number.isInteger(rows) && rows >= 0 ? rows : null,
  };
}

/**
 * Same as `request` but keeps the `meta` key from the envelope. Used for list endpoints that
 * return pagination and facet information (F2-h S1).
 */
export async function requestWithMeta<T, M>(
  path: string,
  options: RequestOptions = {},
): Promise<{ data: T; meta: M | undefined }> {
  return performRequest<T, M>(path, options);
}
