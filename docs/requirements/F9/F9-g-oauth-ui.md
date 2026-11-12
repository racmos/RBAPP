# F9-g: Sign-in with Discord or Google (UI)

| Field | Value |
|---|---|
| Phase / unit | F9 / g |
| Branch | `feat/f9g-oauth-ui` (from up-to-date `main`, F9-f merged; the last F9 unit, just before F12) |
| Depends on | F9-f (OAuth routes, `/meta/config` `oauth.providers`, `oauth_error` values, `oauthStartUrl`), F9-i (account shell, profile page), F9-j (`/login/2fa`, re-auth dialog) |
| Size forecast | ~400 authored lines (tests and docs included) |
| Risk | `Risk: none` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` |
| Save as | `docs/requirements/F9/F9-g-oauth-ui.md` |

## Objective

The login and register screens offer "Continue with Discord" and "Continue with Google" when the
provider is configured; a new person finishes their account by choosing a username; any failure or
cancellation comes back as a clear message; and on the profile page a user connects or disconnects
each provider. Frontend only.

## Read first

- `AGENTS.md` (Frontend; authentication and API access), `docs/knowledge/conventions.md` section 5
- `docs/requirements/F9/README.md` (UI), `F9-f-oauth-backend.md` (S5-S13, S15, S17),
  `F9-i-account-shell-profile-ui.md`, `F9-j-security-api-ui.md` (re-auth dialog, `/login/2fa`)
- `frontend/src/auth/LoginPage.tsx`, `RegisterPage.tsx`, `AuthLayout.tsx`, `FormAlert.tsx`,
  `safeNext.ts`, `formHelpers.ts`, `frontend/src/lib/navigateDocument.ts`, `frontend/src/app/routes.tsx`
- `frontend/src/account/` (the F9-i profile page and its cards), `frontend/src/components/ui/`

## Scope

In:
- Provider buttons on `/login` and `/register`
- New route `/oauth/complete` (anonymous, `requireAnon`)
- `oauth_error` and `oauth_linked` query handling on `/login`, `/account/profile`, `/account/security`
- Connections card on the profile page (connect, disconnect with confirmation and re-auth)
- English strings, axe and catalog tests

Out (do not do, even if tempting):
- Any backend change (if a contract is missing, stop and report)
- Provider logos as third-party assets: use the existing icon set or a plain text label (licensing)
- Showing the provider avatar or e-mail anywhere except the completion screen

## Specs

S1. Provider buttons: below the login form and the register form, a separator "or" and one full-width
    secondary `Button` per enabled provider from `GET /meta/config` → `oauth.providers` (order
    `discord`, `google`): "Continue with Discord", "Continue with Google". None enabled → neither the
    separator nor the buttons render. While `/meta/config` loads, nothing renders there (no layout jump:
    the block reserves no space and appears below the form).
S2. A click navigates with a full page load (`navigateDocument`) to `oauthStartUrl(provider, 'login',
    next, remember)`: on `/login`, `next` = the page's `next` parameter when `safeNext` accepts it, else
    omitted, and `remember` = the "Remember me on this device" checkbox; on `/register`, `next` omitted
    and `remember` = `true`. Offline → the buttons are disabled with the offline reason.
S3. `oauth_error` on `/login`: the value is shown in the form's `FormAlert` through `translateError` of
    the code (`errors:code.<value>`; unknown values → `errors:code.oauth_failed`), then removed from
    the URL with a `replace` navigation (a reload does not show it again).
S4. `/oauth/complete` (`requireAnon`, inside `AuthLayout`, lazy): loads `GET /auth/oauth/complete`.
    - 404 → redirect to `/login?oauth_error=oauth_failed`;
    - 200 → title "Finish creating your account", text "You are signing up with {{provider}} as
      {{display}}." (`display` falls back to the provider name), a Username field prefilled with
      `suggested_username` (hint: the register username hint), a read-only line "Email: {{email}}" or
      "No email will be saved. You can add one later in your profile.", submit "Create account"
      ("Creating account…" while pending);
    - submit → `POST /auth/oauth/complete {username}`: 201 → refetch the session, go to `/`;
      `username_taken` and `validation_error` → error on the field (focus moves there);
      `oauth_failed` or `oauth_identity_in_use` → redirect to `/login?oauth_error=<code>`; 429 → the
      existing retry countdown.
    - A "Cancel" link back to `/login`.
S5. After a provider sign-in with 2FA the backend redirects to `/login/2fa` (F9-j screen); nothing new
    is needed here beyond a test that the route accepts that arrival.
S6. Connections card (profile page, below the details card on mobile; in the second column from 1240
    px): title "Connected accounts", hint "Sign in with these accounts instead of your password."; one
    row per **enabled** provider: provider name, then `display` and "Connected {{date}}" when linked,
    or "Not connected"; a button "Connect" (not linked) or "Disconnect" (linked). No enabled provider →
    the card is not rendered.
S7. Connect: navigates with a full page load to `oauthStartUrl(provider, 'link', '/riftbound/app/account/profile', true)`.
    When the page comes back with `oauth_error=reauth_required`, the F9-j re-auth dialog opens; after
    a successful re-auth the same navigation runs again once. `oauth_linked=<provider>` → success toast
    "{{provider}} connected." and the session/`GET /me` queries refetch; other `oauth_error` values →
    error toast with the translated code. Both parameters are removed from the URL with `replace`.
S8. Disconnect: `ConfirmDialog` "Disconnect {{provider}}?" / "You will no longer be able to sign in with
    this {{provider}} account." / confirm "Disconnect" → `DELETE /me/connections/<provider>` through the
    F9-j re-auth wrapper (403 `reauth_required` → dialog → one retry); 200 → toast "{{provider}}
    disconnected."; 409 `last_sign_in_method` → the dialog closes and an error toast shows the
    translated code (no change).
S9. Re-auth with a provider: in the F9-j dialog, when `params.methods` lists a provider, a button
    "Confirm with {{provider}}" navigates to `oauthStartUrl(provider, 'reauth', <current path>, true)`;
    on return the user repeats the action (the dialog explains: "You will come back here; then repeat
    the action.").
S10. Strings (`auth` namespace unless noted), exact English:
    `oauth.or` "or"; `oauth.continue` "Continue with {{provider}}"; `oauth.complete.title` "Finish
    creating your account"; `oauth.complete.intro` "You are signing up with {{provider}} as
    {{display}}."; `oauth.complete.email` "Email: {{email}}"; `oauth.complete.noEmail` "No email will be
    saved. You can add one later in your profile."; `oauth.complete.submit` "Create account";
    `oauth.complete.submitting` "Creating account…"; `oauth.complete.cancel` "Cancel";
    `oauth.provider.discord` "Discord"; `oauth.provider.google` "Google".
    `account` namespace: `connections.title` "Connected accounts"; `connections.hint` "Sign in with
    these accounts instead of your password."; `connections.connected` "Connected {{date}}";
    `connections.notConnected` "Not connected"; `connections.connect` "Connect";
    `connections.disconnect` "Disconnect"; `connections.confirmTitle` "Disconnect {{provider}}?";
    `connections.confirmBody` "You will no longer be able to sign in with this {{provider}} account.";
    `connections.linked` "{{provider}} connected."; `connections.unlinked` "{{provider}}
    disconnected."; `reauth.withProvider` "Confirm with {{provider}}"; `reauth.providerNote` "You will
    come back here; then repeat the action."
S11. Accessibility: the buttons are real buttons with visible text (no icon-only control); the
    completion form uses `Field` (label, `aria-invalid`, `aria-describedby`); `document.title` via
    `useDocumentTitle` ("Finish creating your account"); messages from S3/S7 announced (`FormAlert` /
    toasts already announce).

## API / data contract

No change. Uses `GET /meta/config` (`oauth.providers`), `GET`/`POST /auth/oauth/complete`,
`DELETE /me/connections/<provider>`, `GET /me` (`security.connections`), and the browser routes
`/riftbound/auth/oauth/<provider>/start` (F9-f).

## UI

| Breakpoint | Layout |
|---|---|
| Mobile < 860 | Auth card one column; provider buttons full width under the form; connections card stacked in the profile column. |
| Desktop ≥ 1240 | Same auth card (centred, fixed width); connections card in the second card column of the profile page. |
| Wide ≥ 1600 | As desktop (the profile page's third column holds the connections card when F9-i places three columns). |

States: `/oauth/complete` loading (`Skeleton` in the card), error of the GET other than 404 (`ErrorState`
with retry), offline (form disabled with the offline reason). Connections card: loading follows the
profile page; offline → buttons disabled.

## Acceptance criteria

- [ ] AC1 `src/auth/LoginPage.test.tsx` / `RegisterPage.test.tsx` (MSW): buttons per provider list,
      none when empty, start URL with `next` and `remember`, offline disabled, `oauth_error` shown and
      removed from the URL (S1-S3)
- [ ] AC2 `src/auth/OAuthCompletePage.test.tsx`: 404 redirect, prefilled suggestion, e-mail line both
      ways, 201 → home, `username_taken` on the field, `oauth_failed` redirect, axe clean (S4, S11)
- [ ] AC3 `src/account/ConnectionsCard.test.tsx`: rows, connect URL, `oauth_linked` toast and refetch,
      `reauth_required` return opens the dialog then re-navigates once, disconnect with confirm, re-auth
      retry, `last_sign_in_method` toast, card hidden without providers, axe clean (S6-S9)
- [ ] AC4 `src/app/routes.test.tsx`: `/oauth/complete` is anonymous-only; `/login/2fa` accepts the
      OAuth arrival (S5)
- [ ] AC5 `src/i18n/catalogCheck.test.ts` green with the S10 keys; `src/test/no-legacy-links.test.ts`
      green
- [ ] AC6 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck &&
      npx vitest run && npm run build && npm run check:dist`
- [ ] AC7 Docs: `docs/frontend.md` (OAuth screens), `AGENTS.md` (Frontend tree: `auth/` OAuth complete,
      `account/` connections), `docs/knowledge/state.md`

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- PR title: `feat(frontend): Discord and Google sign-in screens and connections (F9 unit g)`. PR body:
  S# → tests, screenshots at 390 / 1280 / 1600 px, rollback (revert; frontend rebuild).
- Never merge. The owner merges.

## After merge

- Deploy to dev: frontend rebuild only.
- Live checks: login page shows both buttons; a new provider account reaches "Finish creating your
  account" and lands on the home hub; cancelling on the provider page shows "Sign-in with the provider
  was cancelled."
- Manual checks for the owner: on a phone, sign in with Discord and with Google; connect and disconnect
  a provider from the profile page; a provider-only account cannot disconnect its only provider.

## Open questions

none
