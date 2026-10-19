# Delta for api-v1

> Tags: all requirements of this delta are unit `[c]` of change f1-app-shell. All routes are under `/riftbound/api/v1`. Success envelope: `{"success":true,"data":<object>,"meta":<object, optional>}`. Error envelope: `{"success":false,"error":"<name>","message":"<text>","details":[...optional],"code":"<snake_case, optional>","params":{...optional}}`. Changes are additive: existing fields, status codes and F0 tests stay valid. `GET`/`PATCH /me/prefs` are specified in capability `ui-preferences` (PREF-3, PREF-4). Scenarios are pytest-testable (SQLite) unless tagged.

## MODIFIED Requirements

### Requirement: API-1 Blueprint and envelope [e]

The API MUST live in a blueprint with prefix `/riftbound/api/v1` and MUST NOT collide with landing `/api/*` routes. Every response from this prefix (including framework errors 400/401/403/404/405/415/429/500 and CSRF errors) MUST use the envelopes above with `Content-Type: application/json`. 500 responses MUST NOT leak stack traces or exception text. An error response MAY carry a machine-readable `code` (lowercase snake_case string) and a `params` object (JSON scalars) so clients can translate without parsing prose; `message` MUST always be present as a fallback. Responses that do not define a code MUST remain valid without these fields. `code` and `params` MUST NOT contain secrets, stack traces or internals.
(Previously: the error envelope had only `success`, `error`, `message` and optional `details`.)

#### Scenario: Unknown path with browser Accept
- GIVEN any client
- WHEN `GET /riftbound/api/v1/nope` is sent with `Accept: text/html`
- THEN status 404, JSON `{success:false,error:"Not Found",message}`

#### Scenario: Wrong method
- GIVEN any client
- WHEN `POST /riftbound/api/v1/health` is sent
- THEN status 405, JSON error envelope with `error:"Method Not Allowed"`

#### Scenario: Unhandled exception
- GIVEN an API route that raises `ValueError('secret detail')`
- WHEN it is called
- THEN status 500, `message` is generic and does not contain `secret detail`

#### Scenario: Optional code and params
- GIVEN an F1 endpoint that defines a code (see API-9)
- WHEN it fails
- THEN the body has `code` as a lowercase snake_case string, `params` (if present) is an object, and `message` is a non-empty string

#### Scenario: Codeless errors unchanged
- GIVEN an endpoint without a defined code (for example the 404 of an unknown path)
- WHEN it fails
- THEN the body is the F0 shape and a client reading only `success`, `error` and `message` still works

### Requirement: API-4 GET /auth/session [e]

Public. MUST return `data:{authenticated:false,csrf_token:"<non-empty>"}` for anonymous callers and `data:{authenticated:true,user:{id,username,email,is_admin},prefs:{lang,density,accent,bg_intensity,collection_view},csrf_token}` for logged-in users. `prefs` MUST always contain exactly those five keys, each `null` when unset (Auto); a user without a prefs row MUST get five `null`s and the call MUST NOT create a row. `user` MUST keep exactly its four fields. It MUST NOT include the password hash. A blocked user is anonymous. The token MUST be accepted as `X-CSRFToken` on later unsafe requests. Anonymous responses MUST NOT include `prefs`.
(Previously: logged-in `data` had only `authenticated`, `user` and `csrf_token`.)

#### Scenario: Anonymous
- GIVEN no session
- WHEN called
- THEN 200 and `authenticated == false` with a token and no `prefs` key

#### Scenario: Logged in
- GIVEN a logged-in user
- WHEN called
- THEN `user` has exactly `id, username, email, is_admin` and no hash

#### Scenario: Prefs without a row
- GIVEN a logged-in user who never saved preferences
- WHEN called
- THEN `data.prefs` has the five keys, all `null`, and no `rbuserprefs` row exists afterwards

#### Scenario: Prefs with values
- GIVEN stored `lang:"en"`, `bg_intensity:40`
- WHEN called
- THEN `data.prefs.lang == "en"` and `data.prefs.bg_intensity == 40` with the other keys `null`

### Requirement: API-5 POST /auth/login [e]

JSON `{username,password,remember?}`, validated per LOGIN-9, using the same service, lockout and limits as the form. `remember` is an optional boolean defaulting to `false` in the API (the SPA sends `true` by default); a non-boolean value MUST yield 400 `Validation Error` with `details` naming `remember`. Success: 200 `data:{user:{id,username,email,is_admin}}` and a session cookie; when `remember` is `true` a remember cookie valid for 30 days MUST also be issued (SESS-1), and when `false` or absent none. Invalid or blocked: 401 `error:"Unauthorized"`, `message:"Invalid credentials"`, `code:"invalid_credentials"`. Locked: 429 with `Retry-After` (LOGIN-2), `code:"locked"` and `params:{retry_after:<seconds>}`. Invalid body: 400 `Validation Error` with `details`. With CSRF enabled a request without a valid `X-CSRFToken` is 400 with `code:"csrf_invalid"`.
(Previously: body was `{username,password}` only, no remember cookie was ever issued, and errors had no `code`.)

#### Scenario: Success
- GIVEN user `u` / `Passw0rd!x`
- WHEN logged in via the API
- THEN 200, then `GET /auth/session` shows `authenticated:true`

#### Scenario: Bad password then lock
- GIVEN user `u`
- WHEN 5 wrong passwords then the correct one are posted
- THEN the first 5 are 401 (`code:"invalid_credentials"`) and the 6th is 429 with `Retry-After` and `code:"locked"`

#### Scenario: Missing fields
- GIVEN any client
- WHEN `{"username":"u"}` is posted
- THEN 400 with `details` naming `password`

#### Scenario: CSRF
- GIVEN `csrf_app`
- WHEN login is posted without a token, then with the token from `/auth/session`
- THEN 400 (`code:"csrf_invalid"`) then 200

#### Scenario: Remember true
- GIVEN user `u`
- WHEN `{"username":"u","password":"...","remember":true}` is posted
- THEN 200 and the response sets a remember cookie that expires in about 30 days

#### Scenario: Remember false or absent
- GIVEN user `u`
- WHEN login is posted with `remember:false`, and again without the field
- THEN neither response sets a remember cookie

#### Scenario: Remember not boolean
- GIVEN user `u`
- WHEN login is posted with `"remember":"yes"`
- THEN 400 with `details` naming `remember` and no session is created

## ADDED Requirements

### Requirement: API-9 Error codes for F1 endpoints [c]

The following errors MUST carry the listed `code` (all F1 screens translate by code; see i18n I18N-4): login 401 `invalid_credentials`; login/register rate limit or lockout 429 `locked` (account lock, `params.retry_after` seconds) or `rate_limited` (limiter, `params.retry_after` when known); register 409 `username_taken` or `email_taken`; register captcha failure 400 `captcha_failed`; CSRF failure 400 `csrf_invalid`; unauthenticated JSON access 401 `unauthenticated`; request-body validation 400 `validation_error`, where each `details` item keeps `{field,message,type}` and MAY add `code` from the stable set `required`, `too_short`, `too_long`, `invalid_format`, `invalid_value`, `out_of_range` and `params` (for example `{min:8}`). Endpoints outside this list MAY omit `code`.

#### Scenario: Register duplicate codes
- GIVEN users with username `dup` and email `dup@example.com`
- WHEN registering the same username with a new email, then a new username with the same email
- THEN both are 409 with `code` `username_taken` and `email_taken` respectively

#### Scenario: Captcha failure code
- GIVEN provider `altcha`
- WHEN register is posted without a valid payload
- THEN 400 `error:"Captcha Error"` with `code:"captcha_failed"`

#### Scenario: Validation detail codes
- GIVEN register with a 3-character password and a malformed email
- WHEN posted
- THEN 400 `code:"validation_error"` and `details` entries for `password` (`too_short`, `params.min`) and `email` (`invalid_format`), each still with `field`, `message`, `type`

#### Scenario: Rate limit params
- GIVEN the lockout of LOGIN-2 is active
- WHEN login is attempted
- THEN 429 with `code:"locked"`, `params.retry_after` a positive integer equal to the `Retry-After` header

#### Scenario: Unauthenticated JSON
- GIVEN no session
- WHEN `POST /auth/logout` or `GET /me/prefs` is called
- THEN 401 with `code:"unauthenticated"`
