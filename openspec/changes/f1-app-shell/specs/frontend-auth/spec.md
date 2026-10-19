# Delta for frontend-auth

> Tags: all requirements are unit `[d]` of change f1-app-shell unless stated. `[vitest]` = Vitest + Testing Library + MSW (jsdom). `[MANUAL]` = browser check. The SPA lives at `/riftbound/app/` (router basename `/riftbound/app`) and shares ONE session cookie with the Jinja pages: logging in or out in either applies to both. The SPA consumes the F0 API (`/riftbound/api/v1`) and the F1 additions of api-v1.

## ADDED Requirements

### Requirement: FAUTH-1 Session boot [d]

On start the SPA MUST call `GET /auth/session` before rendering any guarded route, show a loading state meanwhile (never flash the login form to a signed-in user), and keep `authenticated`, `user`, `prefs` and the CSRF token. The CSRF token MUST be held in memory only (not in `localStorage`, `sessionStorage` or cookies written by the SPA). Passwords and tokens MUST NOT be persisted client-side. The SPA MUST keep a non-sensitive "was signed in" hint to support offline boot (PWA-7) and clear it on logout or on an anonymous session.

#### Scenario: Signed-in boot
- GIVEN the session endpoint returns `authenticated:true` [vitest]
- WHEN the app starts at `/riftbound/app/`
- THEN a loading state is shown first, then the home route; the login form is never rendered

#### Scenario: Anonymous boot
- GIVEN `authenticated:false` [vitest]
- WHEN the app starts at a guarded route
- THEN the user lands on `/login` with `next` set to the requested route

#### Scenario: No token persistence
- GIVEN a completed boot [vitest]
- WHEN `localStorage` and `sessionStorage` are inspected
- THEN no key holds the CSRF token or a password

### Requirement: FAUTH-2 Login flow [d]

The login screen MUST show a labelled username and password field and a "Remember me" checkbox that is checked by default. Submit MUST `POST /auth/login` with `{username,password,remember}` and `X-CSRFToken`; on 200 the SPA MUST refetch the session (to obtain the new token and prefs) and navigate to `safeNext(next)` or the app home. The submit control MUST be disabled while pending. A 401 MUST show a generic "invalid credentials" message (no user enumeration), keep the username and clear the password. A 400 MUST map `details` to field errors. The wordmark MUST be shown.

#### Scenario: Success with remember default
- GIVEN the login form untouched except credentials [vitest]
- WHEN the user submits
- THEN the request body contains `remember:true` and the app navigates home after the session refetch

#### Scenario: Remember unchecked
- GIVEN the user unchecks "Remember me" [vitest]
- WHEN they submit
- THEN the body contains `remember:false`

#### Scenario: Bad credentials
- GIVEN the API answers 401 [vitest]
- WHEN the user submits
- THEN a translated generic error is announced, the username is kept, the password is cleared, and no redirect occurs

#### Scenario: Next honoured
- GIVEN the URL `/login?next=/riftbound/app/account/interface` [vitest]
- WHEN login succeeds
- THEN the app navigates to `/account/interface`

### Requirement: FAUTH-3 Register flow [d]

The register screen MUST fetch `GET /meta/config` and `GET /auth/captcha`. When the captcha provider is `none` or the challenge is `null` it MUST render no widget and submit without `altcha`. Otherwise it MUST render the ALTCHA widget (npm `altcha` 2.3.0, loaded lazily only on this route) and include the solved payload as `altcha`; submit MUST stay disabled until the widget is verified. On 201 the SPA MUST navigate to `/login` with a success toast and MUST NOT create a session. Field errors (400 `details`, 409 `username_taken` / `email_taken`) MUST be shown inline on the matching field and 409 MUST be announced.

#### Scenario: Created
- GIVEN provider `none` [vitest]
- WHEN valid fields are submitted and the API returns 201
- THEN the router is at `/login`, a success toast is visible and the session stays anonymous

#### Scenario: Widget required
- GIVEN provider `altcha` and an unsolved widget [vitest]
- WHEN the form is rendered
- THEN the submit control is disabled until the widget reports verified, then the request includes `altcha`

#### Scenario: Duplicate username
- GIVEN the API answers 409 with `code:"username_taken"` [vitest]
- WHEN the user submits
- THEN the username field shows the translated message and is focused

#### Scenario: Lazy loading
- GIVEN the production build
- WHEN the entry chunk list is inspected
- THEN the ALTCHA library is not in the initial entry chunk of `/login`

### Requirement: FAUTH-4 ALTCHA reset after any register error [d]

After ANY failed register attempt (400, 409, 429, 5xx or network error) the SPA MUST refetch `GET /auth/captcha`, reset the widget and require solving again before the next submit, because the payload is single-use and is consumed server-side before the duplicate check. The JS `altcha` version in `package.json`/lockfile MUST equal the Python `altcha` pin in `requirements.txt` (both 2.3.0, proof-of-work v1).

#### Scenario: 409 burns the payload
- GIVEN a solved widget and a 409 response [vitest]
- WHEN the error is shown
- THEN a new captcha request is made and the submit control is disabled until re-verified

#### Scenario: Pin contract
- GIVEN `requirements.txt` and `frontend/package-lock.json`
- WHEN the contract test compares the `altcha` versions
- THEN they are equal

### Requirement: FAUTH-5 Logout [d]

Logout MUST `POST /auth/logout` with the CSRF token. On 200 OR 401 (already signed out) the SPA MUST clear the TanStack Query cache, the "was signed in" hint and any per-user client data, refresh to an anonymous session and navigate to `/login`. On other failures the SPA MUST stay signed in and show an error toast.

#### Scenario: Normal logout
- GIVEN a signed-in user with cached queries [vitest]
- WHEN they log out and the API returns 200
- THEN the query cache is empty and the router is at `/login`

#### Scenario: Already expired
- GIVEN the API answers 401 to logout [vitest]
- WHEN the user logs out
- THEN the outcome is identical to a 200

#### Scenario: Server error
- GIVEN the API answers 500 [vitest]
- WHEN the user logs out
- THEN the user remains in the shell and an error toast appears

### Requirement: FAUTH-6 CSRF retry once [d]

When an unsafe request fails with 400 and `code:"csrf_invalid"`, the API client MUST refetch `GET /auth/session`, replace the in-memory token and retry the original request exactly once. If the retry also fails, the error MUST surface normally (no loops). Every unsafe request MUST send `X-CSRFToken` and the client MUST NOT set `Referrer-Policy: no-referrer` on its requests (the server checks Referer over HTTPS).

#### Scenario: Stale token
- GIVEN the first POST returns 400 `csrf_invalid` and the refreshed token is accepted [vitest]
- WHEN the user submits
- THEN exactly two POSTs and one session GET occur and the user sees success

#### Scenario: Still failing
- GIVEN both POSTs return 400 `csrf_invalid` [vitest]
- WHEN the user submits
- THEN no third POST is made and an error is shown

### Requirement: FAUTH-7 401 and 429 handling [d]

A 401 from any API call other than login or logout MUST switch the app to anonymous, clear caches and navigate to `/login?next=<current path>`. A 429 MUST be shown with a countdown derived from `Retry-After` (or `params.retry_after`), keep the submit control disabled until the countdown ends, and then re-enable it. Rate-limit and lock messages MUST be announced politely (`aria-live`).

#### Scenario: Session expires mid-use
- GIVEN a signed-in user and the next API call returns 401 [vitest]
- WHEN the call is made from `/collection`
- THEN the user is at `/login?next=%2Fcollection` and the caches are cleared

#### Scenario: Locked account
- GIVEN login returns 429 with `Retry-After: 30` [vitest]
- WHEN the message is shown
- THEN a countdown starts near 30 s, submit is disabled and re-enabled at 0

### Requirement: FAUTH-8 Route guards [d]

The router MUST provide `requireAuth` (anonymous -> `/login?next=...`), `requireAnon` (an authenticated user visiting `/login` or `/register` goes to `safeNext(next)` or home) and `requireAdmin` (non-admin sees the 404 view). `requireAdmin` is UX only; the server remains the authority for admin actions.

#### Scenario: Signed-in user opens login
- GIVEN an authenticated session [vitest]
- WHEN the user navigates to `/login`
- THEN they are redirected to home

#### Scenario: Non-admin on admin route
- GIVEN an authenticated non-admin [vitest]
- WHEN they navigate to an admin-only route
- THEN the 404 view is rendered

### Requirement: FAUTH-9 safeNext [d]

`safeNext(raw)` MUST return a path only if it is same-origin and under `/riftbound/`: it MUST start with a single `/`, MUST NOT start with `//` or contain `\`, a scheme, control characters or encoded variants of these after decoding, and MUST begin with `/riftbound/`. Paths under `/riftbound/app/` navigate inside the router (basename stripped); other `/riftbound/` paths (legacy Jinja) navigate with a full page load. Anything else MUST return the app home.

#### Scenario: Accepted and rejected inputs
- GIVEN the inputs `/riftbound/app/collection`, `/riftbound/collection`, `https://evil.example`, `//evil.example`, `/\evil`, `javascript:alert(1)`, `/riftbound/../etc`, `%2f%2fevil.example`, `/other`, empty and `null` [vitest]
- WHEN `safeNext` is applied
- THEN the first two are accepted and every other input returns home

### Requirement: FAUTH-10 Auth screen accessibility [d]

Login and register MUST have programmatic labels for every control, correct `autocomplete` values (`username`, `current-password`, `new-password`, `email`), errors associated with fields via `aria-describedby` and announced, focus moved to the first invalid field after a failed submit, a show/hide password control with an accessible name, and the wordmark with the accessible name "Rift Manager". `vitest-axe` MUST report no violations on both screens.

#### Scenario: Axe clean
- GIVEN the rendered login and register screens, including an error state [vitest]
- WHEN `vitest-axe` runs
- THEN there are no violations

#### Scenario: Focus on error
- GIVEN an invalid email submission [vitest]
- WHEN the 400 response arrives
- THEN focus is on the email field and its error text is referenced by `aria-describedby`

### Requirement: FAUTH-11 Shared session with Jinja [d]

A session created through the SPA MUST be valid on Jinja pages and vice versa; logout in either MUST end both.

#### Scenario: Cross-app session [MANUAL]
- GIVEN a browser signed in through the SPA
- WHEN `/riftbound/` (Jinja dashboard) is opened, then logout is done there, then `/riftbound/app/` is reloaded
- THEN the dashboard opens without login, and afterwards the SPA shows the login screen
