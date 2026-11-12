# F9-j: Security and API UI, 2FA sign-in screen

| Field | Value |
|---|---|
| Phase / unit | F9 / j |
| Branch | `feat/f9j-security-api-ui` (from up-to-date `main`, F9-a, d, e, h, i merged) |
| Depends on | F9-a (`/me/sessions`), F9-b (`reauth_required`, `POST /me/reauth`), F9-d (`/me/2fa/*`), F9-e (`POST /auth/mfa`, `mfa_required`, `mfa_pending`), F9-h (`/me/api-key`), F9-i (account layout and sections) |
| Size forecast | ~650 authored lines (tests and docs included) |
| Risk | `Risk: none` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` |
| Save as | `docs/requirements/F9/F9-j-security-api-ui.md` |

## Objective

The account gets a Security section (password, two-factor authentication with a guided set-up and
recovery codes, the list of signed-in devices with sign-out) and an API section (the personal read-only
key, shown once). Any sensitive action that needs a fresh confirmation asks for the password or a code
in a dialog and then continues by itself. After the password, users with 2FA land on a code screen.
Frontend only.

## Read first

- `AGENTS.md` (Frontend; authentication and API access), `docs/knowledge/conventions.md` section 5
- `docs/requirements/F9/README.md` (UI: flows, a11y, offline), `F9-a-sessions.md` (S7, S10-S12),
  `F9-b-profile-reauth.md` (S5, S9-S11), `F9-d-totp-enrolment.md` (S7-S14, S16),
  `F9-e-2fa-sign-in.md` (S2-S4, S10), `F9-h-api-key.md` (S2-S6, S8, S15),
  `F9-i-account-shell-profile-ui.md` (S1-S3, S12-S14)
- `frontend/src/auth/LoginPage.tsx`, `useRetryCountdown.ts`, `safeNext.ts`, `useAuth.ts` (`useLogout`),
  `frontend/src/api/client.ts`, `frontend/src/account/` (layout, ProfilePage password form),
  `frontend/src/components/ui/` (`Modal`, `ConfirmDialog`, `Field`, `Input`, `PasswordInput`,
  `Checkbox`, `SettingsCard`, `TableScroll`, `Badge`, `toastStore`)

## Scope

In:
- Sections `security` and `api` in the account layout (`/account/security`, `/account/api`)
- Re-auth dialog and the `withReauth` helper (one retry after success)
- Security: password card (moved from Profile; "Set a password" for accounts without one), 2FA card and
  wizard, recovery codes, turn off, sessions card
- API: key card, create/replace shown once, revoke, `curl` example
- `/login/2fa` screen; the login page sends 2FA users there
- English strings, axe tests

Out (do not do, even if tempting):
- Any backend change (if a contract is missing, stop and report)
- OAuth buttons and the provider option of the re-auth dialog (F9-g)
- Storing codes, keys or secrets in web storage or the query cache after their dialog closes

## Specs

S1. Sections: the F9-i list becomes Profile, Security, API, Interface (`sections.security` "Security",
    `sections.api` "API"). The password card moves from Profile to Security (same component and
    `prefs:profile.password.*` strings).
S2. `withReauth(action)` (`account/reauth/`): runs the action; when it fails with `ApiError` code
    `reauth_required`, opens `ReauthDialog` with `params.methods`; after a successful `POST /me/reauth`
    it runs the action **once more** and returns its result; cancelling rejects with a cancellation that
    callers ignore (no toast). A second `reauth_required` after the retry is shown as an error toast
    (no loop).
S3. `ReauthDialog` (`Modal`, title "Confirm it's you", text "For your security, confirm your identity
    to continue."): with `password` in methods a `PasswordInput` "Password"; with `totp` a code field
    "Code from your authenticator app" (`inputmode="numeric"`, `autocomplete="one-time-code"`, 6
    digits); with both, a link switches between them ("Use your authenticator app instead" / "Use your
    password instead"), password first. Submit "Confirm" ("Confirming…"); `current_password_incorrect`
    and `mfa_invalid` → field error; 429 → retry countdown; Cancel closes.
S4. Password card (Security): with `has_password` the existing form plus the line "Changing your
    password signs out your other devices."; without a password the card "Set a password" (hint "Add a
    password to sign in without Discord or Google.") with New password + Confirm only → `PATCH
    /me/account {password}` through `withReauth` → toast "Password set." and `GET /me` refetched.
S5. Two-factor card: title "Two-factor authentication", hint "Ask for a code from an authenticator app
    when you sign in."; `mfa.available` false → text "Two-factor authentication is not available on
    this server." and no actions; off → badge "Off" and button "Turn on"; on → badge "On", "Recovery
    codes left: {{count}}" (warning style when ≤ 3), buttons "New recovery codes" and "Turn off".
S6. Wizard (`Modal` "Turn on two-factor authentication", three steps with a step indicator "Step
    {{step}} of 3"):
    1. `withReauth(POST /me/2fa/setup)` → "Scan the QR code with your authenticator app, or enter this
       key by hand." The QR is `<img src={qr} alt="QR code for your authenticator app">` (220 px);
       below it the key grouped by 4 in monospace with a "Copy key" button (text alternative to the
       QR). Button "Next".
    2. "Enter the 6-digit code your app shows." Code field (as S3) → "Turn on" ("Turning on…") →
       `POST /me/2fa/enable` through `withReauth`; `mfa_invalid` → field error "That code is not valid.
       Check your authenticator app and try again."; "Back" returns to step 1.
    3. "Save your recovery codes" — "Each code works once if you lose your phone. Keep them somewhere
       safe; you will not see them again." The 10 codes in a monospace list; "Copy codes"; "Download"
       (a text file `rift-manager-recovery-codes.txt`, one code per line, from a `Blob` URL revoked
       right after); checkbox "I saved these codes somewhere safe"; "Done" enabled only when checked.
       At this step Esc, the backdrop and the close button do nothing until the box is checked.
    On "Done": toast "Two-factor authentication is on. Your other devices were signed out.", `GET /me`
    and `GET /me/sessions` refetched, the codes dropped from component state.
S7. Turn off: dialog "Turn off two-factor authentication?" with the text "Enter a code from your app or
    one of your recovery codes." and a field "Code" (`autocomplete="one-time-code"`, any of the two
    formats), confirm "Turn off" → `withReauth(POST /me/2fa/disable {code})`; `mfa_invalid` → field
    error; success → toast "Two-factor authentication is off. Your other devices were signed out."
S8. New recovery codes: `ConfirmDialog` "Create new recovery codes?" / "Your current codes stop working
    and your other devices are signed out." / "Create codes" → `withReauth(POST /me/2fa/recovery-codes)`
    → the step-3 view of S6 in its own `Modal` "New recovery codes".
S9. Sessions card ("Signed-in devices", hint "Where your account is signed in now."): `GET
    /me/sessions`. Each item: device label, badge "This device" for the current one, "Signed in with
    {{method}}" (`Password`, `Discord`, `Google`), badge "2FA" when `mfa`, "Network {{ip}}" when
    `ip_prefix`, "Last active {{when}}" (relative for < 7 days via `lib/format.ts`, else the date),
    "Signed in {{date}}", and "Stays signed in until {{date}}" for remembered sessions. Below 860 px
    cards; from 860 px a table (`TableScroll`) with columns Device, Method, Network, Last active,
    Signed in, Actions. Actions: other sessions "Sign out" → `ConfirmDialog` "Sign out this device?" /
    "{{device}} will need to sign in again." / "Sign out" → `DELETE /me/sessions/<id>` → toast "Device
    signed out."; the current one "Sign out" → the existing logout flow (`useLogout`). Card button
    "Sign out all other devices" (only when there are others) → `ConfirmDialog` "Sign out all other
    devices?" / "Every other browser and app will need to sign in again." / "Sign out others" →
    `DELETE /me/sessions` → toast "Signed out {{count}} device" / "Signed out {{count}} devices"
    (English plural keys `_one` / `_other`). A 404 on a row (already gone) refetches silently.
S10. API section: card "API key", intro "A personal key to read your data (collection, decks,
    wishlists, products) from scripts and other tools. It can't change anything or open your account
    settings." No key → "You have no API key." + "Create key". With a key → "Key {{prefix}}…",
    "Created {{date}}", "Last used {{when}}" or "Never used", buttons "Replace key" and "Revoke key".
    Create → `withReauth(POST /me/api-key)`; Replace → `ConfirmDialog` "Replace your API key?" / "The
    current key stops working at once." / "Replace" → same call. Success → `Modal` "Your new API key":
    the key in a read-only monospace field, "Copy key", warning "Copy it now. You will not see it
    again.", "Done" (the key is dropped from state on close). Revoke → `ConfirmDialog` "Revoke your API
    key?" / "Scripts using it stop working at once." / "Revoke" → `DELETE /me/api-key` → toast "API key
    revoked."
S11. `curl` example card ("Example"): `curl -H "Authorization: Bearer rb_live_<your key>"
    <origin>/riftbound/api/v1/collection` where `<origin>` is `window.location.origin` at run time
    (nothing hard-coded), with "Copy"; text "Only GET requests are allowed. Limit: 60 requests per
    minute." Below 1600 px it sits under the key card; from 1600 px beside it.
S12. Login page: when `POST /auth/login` answers `mfa_required`, navigate (`replace`) to `/login/2fa`
    keeping the `next` parameter; no session refetch before that.
S13. `/login/2fa` (`requireAnon`, inside `AuthLayout`, lazy): on mount reads the session; without
    `mfa_pending` → redirect to `/login`. Title "Two-step verification", text "Enter the 6-digit code
    from your authenticator app."; field "Code" (`inputmode="numeric"`, `autocomplete="one-time-code"`,
    autofocus); link "Use a recovery code" switches to a field "Recovery code" (`autocomplete="off"`,
    text "Enter one of the recovery codes you saved.") and back with "Use your authenticator app";
    submit "Verify" ("Verifying…"); link "Back to sign in". `POST /auth/mfa`:
    - 200 → refetch the session, go to `next` (same `safeNext` rule as login); when
      `recovery_code_used`, toast "You have {{count}} recovery code left. Create new ones in Security." /
      "...codes left..." (`_one` / `_other`);
    - 401 `mfa_invalid` → field error; 401 `mfa_expired` → `/login` with the alert "The sign-in step
      expired. Sign in again."; 429 `locked` or `rate_limited` → the login page's retry countdown and
      the button disabled; offline → disabled with the offline reason.
S14. Strings (exact English). `account` namespace: `sections.security` "Security"; `sections.api` "API";
    `reauth.title` "Confirm it's you"; `reauth.text` "For your security, confirm your identity to
    continue."; `reauth.password` "Password"; `reauth.code` "Code from your authenticator app";
    `reauth.useCode` "Use your authenticator app instead"; `reauth.usePassword` "Use your password
    instead"; `reauth.confirm` "Confirm"; `reauth.confirming` "Confirming…"; `reauth.cancel` "Cancel";
    `password.othersNote` "Changing your password signs out your other devices."; `password.setTitle`
    "Set a password"; `password.setHint` "Add a password to sign in without Discord or Google.";
    `password.setSave` "Set password"; `password.set` "Password set."; `mfa.title` "Two-factor
    authentication"; `mfa.hint` "Ask for a code from an authenticator app when you sign in.";
    `mfa.unavailable` "Two-factor authentication is not available on this server."; `mfa.on` "On";
    `mfa.off` "Off"; `mfa.codesLeft` "Recovery codes left: {{count}}"; `mfa.turnOn` "Turn on";
    `mfa.turnOff` "Turn off"; `mfa.newCodes` "New recovery codes"; `mfa.wizardTitle` "Turn on two-factor
    authentication"; `mfa.step` "Step {{step}} of 3"; `mfa.scan` "Scan the QR code with your
    authenticator app, or enter this key by hand."; `mfa.qrAlt` "QR code for your authenticator app";
    `mfa.copyKey` "Copy key"; `mfa.next` "Next"; `mfa.back` "Back"; `mfa.enterCode` "Enter the 6-digit
    code your app shows."; `mfa.enable` "Turn on"; `mfa.enabling` "Turning on…"; `mfa.codesTitle` "Save
    your recovery codes"; `mfa.codesText` "Each code works once if you lose your phone. Keep them
    somewhere safe; you will not see them again."; `mfa.copyCodes` "Copy codes"; `mfa.download`
    "Download"; `mfa.saved` "I saved these codes somewhere safe"; `mfa.done` "Done"; `mfa.enabled`
    "Two-factor authentication is on. Your other devices were signed out."; `mfa.disableTitle` "Turn
    off two-factor authentication?"; `mfa.disableText` "Enter a code from your app or one of your
    recovery codes."; `mfa.disableCode` "Code"; `mfa.disabled` "Two-factor authentication is off. Your
    other devices were signed out."; `mfa.newCodesTitle` "Create new recovery codes?";
    `mfa.newCodesText` "Your current codes stop working and your other devices are signed out.";
    `mfa.newCodesConfirm` "Create codes"; `mfa.newCodesModal` "New recovery codes"; `mfa.copied`
    "Copied."; `sessions.title` "Signed-in devices"; `sessions.hint` "Where your account is signed in
    now."; `sessions.thisDevice` "This device"; `sessions.method` "Signed in with {{method}}";
    `sessions.methods.password` "Password"; `sessions.methods.discord` "Discord";
    `sessions.methods.google` "Google"; `sessions.mfa` "2FA"; `sessions.network` "Network {{ip}}";
    `sessions.lastActive` "Last active {{when}}"; `sessions.signedIn` "Signed in {{date}}";
    `sessions.until` "Stays signed in until {{date}}"; `sessions.columns.device` "Device";
    `sessions.columns.method` "Method"; `sessions.columns.network` "Network";
    `sessions.columns.lastActive` "Last active"; `sessions.columns.signedIn` "Signed in";
    `sessions.columns.actions` "Actions"; `sessions.signOut` "Sign out"; `sessions.signOutTitle` "Sign
    out this device?"; `sessions.signOutBody` "{{device}} will need to sign in again.";
    `sessions.signedOut` "Device signed out."; `sessions.signOutOthers` "Sign out all other devices";
    `sessions.othersTitle` "Sign out all other devices?"; `sessions.othersBody` "Every other browser and
    app will need to sign in again."; `sessions.othersConfirm` "Sign out others";
    `sessions.othersDone_one` "Signed out {{count}} device"; `sessions.othersDone_other` "Signed out
    {{count}} devices"; `api.title` "API key"; `api.intro` "A personal key to read your data
    (collection, decks, wishlists, products) from scripts and other tools. It can't change anything or
    open your account settings."; `api.none` "You have no API key."; `api.create` "Create key";
    `api.key` "Key {{prefix}}…"; `api.created` "Created {{date}}"; `api.lastUsed` "Last used {{when}}";
    `api.neverUsed` "Never used"; `api.replace` "Replace key"; `api.replaceTitle` "Replace your API
    key?"; `api.replaceBody` "The current key stops working at once."; `api.replaceConfirm` "Replace";
    `api.revoke` "Revoke key"; `api.revokeTitle` "Revoke your API key?"; `api.revokeBody` "Scripts
    using it stop working at once."; `api.revokeConfirm` "Revoke"; `api.revoked` "API key revoked.";
    `api.newTitle` "Your new API key"; `api.copy` "Copy key"; `api.warning` "Copy it now. You will not
    see it again."; `api.done` "Done"; `api.exampleTitle` "Example"; `api.exampleNote` "Only GET
    requests are allowed. Limit: 60 requests per minute."; `api.copyExample` "Copy".
    `auth` namespace: `mfa.title` "Two-step verification"; `mfa.text` "Enter the 6-digit code from your
    authenticator app."; `mfa.code` "Code"; `mfa.useRecovery` "Use a recovery code"; `mfa.recovery`
    "Recovery code"; `mfa.recoveryText` "Enter one of the recovery codes you saved."; `mfa.useApp` "Use
    your authenticator app"; `mfa.submit` "Verify"; `mfa.submitting` "Verifying…"; `mfa.back` "Back to
    sign in"; `mfa.codesLeft_one` "You have {{count}} recovery code left. Create new ones in Security.";
    `mfa.codesLeft_other` "You have {{count}} recovery codes left. Create new ones in Security.".
S15. Accessibility: every control through `Field` (`aria-invalid`, `aria-describedby`); focus moves to
    the first invalid field and into each wizard step's heading; the QR has the grouped key as its text
    alternative; copy actions announce "Copied." through `announce()`; dialogs are the native `Modal` /
    `ConfirmDialog`; the sessions table has a caption (visually hidden) "Signed-in devices"; axe clean
    on `/account/security`, `/account/api` and `/login/2fa` at 390 and 1280 px.
S16. Offline: Security and API show the cached data read-only and every action is disabled with the
    offline reason; `/login/2fa` disables submit offline.

## API / data contract

No change. Uses `GET /me`, `POST /me/reauth`, `PATCH /me/account`, `POST /me/2fa/setup|enable|disable|recovery-codes`,
`GET`/`DELETE /me/sessions[/<id>]`, `GET`/`POST`/`DELETE /me/api-key`, `POST /auth/login`, `POST
/auth/mfa`, `GET /auth/session` (`mfa_pending`).

## UI

| Breakpoint | Security | API |
|---|---|---|
| Mobile < 860 | Tab row; one column: Password, Two-factor, Devices (cards). | Tab row; key card, example card below. |
| Tablet 860-1239 | Tab row; Password + Two-factor in two columns; Devices table full width below. | Key card and example stacked. |
| Desktop ≥ 1240 | Sidebar + two columns (Password, Two-factor \| Devices table). | Sidebar + key card; example below. |
| Wide ≥ 1600 | Sidebar + Password \| Two-factor \| Devices. | Sidebar + key card and example side by side. |

States: loading `Skeleton` per card, error `ErrorState` with retry per card, empty sessions impossible
(the current one is always listed), offline S16. `/login/2fa`: the auth card layout of `/login` at every
width.

## Acceptance criteria

- [ ] AC1 `src/account/reauth/withReauth.test.tsx`: success without dialog; `reauth_required` → dialog
      with the right fields per `methods`, success → one retry, cancel → no toast, second
      `reauth_required` → error toast; wrong password/code field errors; 429 countdown (S2, S3)
- [ ] AC2 `src/account/SecurityPage.test.tsx`: password card both modes (set-password through re-auth),
      2FA card states, wizard steps (QR alt, key copy, wrong code, codes copy and download, Done gated by
      the checkbox, Esc ignored at step 3, state cleared), turn off, new codes, axe clean (S4-S8, S15)
- [ ] AC3 `src/account/SessionsCard.test.tsx`: cards below 860 and table from 860, labels and badges,
      revoke one with confirm, current → logout flow, sign out others with plural toast, 404 refetch
      (S9)
- [ ] AC4 `src/account/ApiPage.test.tsx`: none / existing states, create through re-auth, key shown once
      and dropped on close, replace and revoke with confirm, example with the runtime origin, layout at
      1600 px, axe clean (S10, S11)
- [ ] AC5 `src/auth/LoginPage.test.tsx` and `src/auth/MfaPage.test.tsx`: redirect on `mfa_required`
      with `next`; no pending → `/login`; code and recovery modes; success → `next`; recovery toast
      plural; `mfa_invalid`, `mfa_expired`, `locked` countdown, offline; axe clean (S12, S13, S16)
- [ ] AC6 `src/i18n/catalogCheck.test.ts` green (English plural forms only); CSS layer and breakpoint
      rules; `no-legacy-links` and ESLint boundaries green (`auth` never imports `account`)
- [ ] AC7 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck &&
      npx vitest run && npm run build && npm run check:dist`
- [ ] AC8 Docs: `docs/frontend.md` (account Security/API, re-auth pattern, 2FA sign-in), `AGENTS.md`
      (Frontend tree), `docs/knowledge/state.md`

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- PR title: `feat(frontend): security, 2FA, devices and API key screens (F9 unit j)`. PR body: S# →
  tests, screenshots at 390 / 1024 / 1280 / 1600 px, rollback (revert; frontend rebuild).
- Never merge. The owner merges.

## After merge

- Deploy to dev: frontend rebuild only.
- Live checks: turn 2FA on with an authenticator app, sign out, sign in → `/login/2fa` → code → home;
  sign in from a second browser and sign it out from Devices; create an API key and read the
  collection with the example.
- Manual checks for the owner: phone flow of the wizard (scan with the phone's own app needs a second
  device or the "enter key by hand" path), recovery-code sign-in, key copy on a phone.

## Open questions

none
