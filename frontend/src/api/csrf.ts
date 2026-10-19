/**
 * The CSRF token lives in this module variable only (FAUTH-1): it is never written to
 * localStorage, sessionStorage or a cookie by the SPA.
 */
let token: string | null = null;

export const getCsrfToken = (): string | null => token;
export const setCsrfToken = (value: string): void => {
  token = value;
};
export const clearCsrfToken = (): void => {
  token = null;
};
