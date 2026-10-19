/**
 * Findings of the altcha 2.3.0 spike (task 4.4). Source: node_modules/altcha/dist/altcha.d.ts
 * and README.
 *
 * - Importing `altcha` (side effect) registers the `<altcha-widget>` custom element. Its
 *   `dist/altcha.d.ts` declares the global JSX element for React 19 (`React.JSX.IntrinsicElements`).
 * - Events: `statechange` is a CustomEvent with `detail = { state, payload? }`; `state` is one of
 *   `unverified | verifying | verified | expired | error` (the README also lists `code`).
 *   `payload` (the base64 solution the server verifies) is present when `state === 'verified'`.
 *   There is also a `verified` event with `detail.payload`; `statechange` covers both.
 * - Attributes: `challengejson` (the JSON of `GET /auth/captcha`'s `challenge`, no extra request),
 *   `auto="onload"` (solve as soon as the element connects), `hidelogo`, `hidefooter`,
 *   `strings` (JSON object with ariaLinkLabel, enterCode, enterCodeAria, error, expired, footer,
 *   getAudioChallenge, label, loading, reload, verificationRequired, verified, verifying,
 *   waitAlert), `name` (hidden input; we ignore it and read the payload from the event).
 * - With `challengejson` the widget cannot refetch an expired challenge: the app refetches
 *   `GET /auth/captcha` and remounts the element with a new React key (D22).
 * - Proof of work v1 matches python `altcha==2.3.0`; altcha 3.x is PoW v2 and incompatible.
 */
export type AltchaState = 'unverified' | 'verifying' | 'verified' | 'expired' | 'error';

export type AltchaStateChange = { state: AltchaState; payload?: string };
