/** Where to go after sign-in: inside the router, or to a legacy Jinja page with a full load. */
export type NextTarget = { kind: 'router'; to: string } | { kind: 'document'; href: string };

export const HOME: NextTarget = { kind: 'router', to: '/' };

const PRODUCT = '/riftbound/';
const SPA_ROOT = '/riftbound/app';
const MAX_DECODES = 2;
// eslint-disable-next-line no-control-regex -- the point is to reject control characters
const CONTROL = /[\u0000-\u001f\u007f]/;
const SCHEME = /^[a-z][a-z0-9+.-]*:/i;

/** True when one form of the input (raw or decoded) is something an open redirect could use. */
function isHostile(value: string): boolean {
  if (CONTROL.test(value) || value.includes('\\')) return true;
  if (value.startsWith('//') || SCHEME.test(value)) return true;
  return value.split(/[?#]/, 1)[0].split('/').includes('..');
}

/** `value`, then decoded once, then decoded twice; null when the encoding is malformed. */
function variants(value: string): string[] | null {
  const forms = [value];
  try {
    for (let i = 0; i < MAX_DECODES; i += 1) forms.push(decodeURIComponent(forms[i]));
  } catch {
    return null;
  }
  return forms;
}

/**
 * Validate a `next` value (FAUTH-9, D13). Only same-origin paths under `/riftbound/` pass; the
 * raw value is checked together with its once and twice decoded forms, and returned unchanged.
 * Anything else is the app home.
 */
export function safeNext(raw: string | null | undefined): NextTarget {
  if (!raw || !raw.startsWith(PRODUCT)) return HOME;
  const forms = variants(raw);
  if (forms === null || forms.some(isHostile)) return HOME;

  const path = raw.split(/[?#]/, 1)[0];
  if (path === SPA_ROOT || path.startsWith(`${SPA_ROOT}/`)) {
    const rest = raw.slice(SPA_ROOT.length);
    return { kind: 'router', to: rest.startsWith('/') ? rest : `/${rest}` };
  }
  return { kind: 'document', href: raw };
}
