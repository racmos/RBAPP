# Delta for ui-preferences

> Tags: `[c]` = backend unit (migration + API), `[e]` = frontend unit (change f1-app-shell). `[PG-CI]` = runs in the PostgreSQL CI job. `[vitest]` = frontend unit test (jsdom/MSW). Untagged backend scenarios are pytest-testable (SQLite). All routes are under `/riftbound/api/v1`. Preferences are account-level (not per device). `NULL` = Auto / product default.

## ADDED Requirements

### Requirement: PREF-1 Storage in rbuserprefs [c]

Migration `0006_user_prefs` (down revision `0005_login_protection`) MUST create table `riftbound.rbuserprefs` with a 1:1 relation to `rbusers`: `rbprf_user_id` (primary key, FK to `riftbound.rbusers.id`, ON DELETE CASCADE), `rbprf_lang`, `rbprf_density`, `rbprf_accent`, `rbprf_bg_intensity` (SMALLINT), `rbprf_collection_view`, `rbprf_updated_at`. All preference columns MUST be nullable; `NULL` means Auto. Value domains MUST be enforced by named CHECK constraints. The migration MUST upgrade and downgrade on SQLite and PostgreSQL; `flask db check` MUST be clean after it; `docs/migrations.md` MUST mention it. Rows are created lazily (no row is required for a user).

#### Scenario: Up and down [PG-CI]
- GIVEN a database at `0005_login_protection`
- WHEN `upgrade head` then `downgrade 0005_login_protection` then `upgrade head` run
- THEN all succeed on PostgreSQL and SQLite, the table appears/disappears, and `flask db check` reports no drift

#### Scenario: CHECK rejects bad values [PG-CI]
- GIVEN the migrated schema
- WHEN a row with `rbprf_bg_intensity = 101` or `rbprf_density = 'huge'` is inserted
- THEN the database raises an integrity error

#### Scenario: Cascade on user delete [PG-CI]
- GIVEN a user with a prefs row
- WHEN the user row is deleted
- THEN the prefs row is gone

### Requirement: PREF-2 Allowed values [c]

The preference domains are: `lang` in {`es`,`en`}; `density` in {`compact`,`regular`,`comfy`}; `accent` in {`cyan`,`orange`}; `bg_intensity` an integer 0 to 100 inclusive; `collection_view` in {`table`,`grid`}. Each MAY be `null` (Auto). The API, the Pydantic schema and the DB CHECKs MUST agree on these domains.

#### Scenario: Domain parity
- GIVEN the Pydantic `PrefsUpdate` schema and the model CHECKs
- WHEN every allowed value and one invalid value per field are validated
- THEN allowed values pass and invalid ones are rejected at both layers

### Requirement: PREF-3 GET /me/prefs [c]

Authenticated only (JSON 401 for anonymous callers, never a redirect). MUST return 200 `data:{prefs:{lang,density,accent,bg_intensity,collection_view}}` with exactly those five keys, each `null` when unset. A user without a row MUST receive all `null` and the GET MUST NOT create a row.

#### Scenario: Defaults
- GIVEN a logged-in user without a prefs row
- WHEN `GET /me/prefs`
- THEN 200 with five keys all `null`, and no row exists afterwards

#### Scenario: Anonymous
- GIVEN no session
- WHEN `GET /me/prefs`
- THEN 401 JSON error envelope

### Requirement: PREF-4 PATCH /me/prefs semantics [c]

Authenticated, CSRF-protected (400 without a valid `X-CSRFToken`), validated with `@validate_json`. A field that is ABSENT from the body MUST remain unchanged. A field present with `null` MUST reset it to Auto (`NULL`). A field present with a valid value MUST be stored. An empty object `{}` MUST be accepted and change nothing. Invalid values (outside the domains of PREF-2, wrong type, booleans or non-integral numbers for `bg_intensity`) MUST yield 400 `Validation Error` with `details` naming the field, and MUST NOT change any field of the request (all-or-nothing). Unknown fields MUST NOT be persisted and MUST NOT cause a 500. Success MUST return 200 `data:{prefs:{...full resulting prefs...}}` and refresh `rbprf_updated_at`; the row is created on first write.

#### Scenario: Partial update
- GIVEN stored prefs `{lang:"en", accent:"cyan"}`
- WHEN `PATCH {"density":"compact"}`
- THEN `lang` stays `en`, `accent` stays `cyan`, `density` is `compact`

#### Scenario: Null resets to Auto
- GIVEN stored `density:"comfy"`
- WHEN `PATCH {"density":null}`
- THEN the response and `GET /me/prefs` show `density:null`, other fields unchanged

#### Scenario: Invalid value
- GIVEN any logged-in user
- WHEN `PATCH {"bg_intensity":101}` and `PATCH {"accent":"purple"}` and `PATCH {"bg_intensity":50.5}`
- THEN each returns 400 with `details` naming the field and the stored prefs are unchanged

#### Scenario: All-or-nothing
- GIVEN stored `lang:"es"`
- WHEN `PATCH {"lang":"en","density":"huge"}`
- THEN 400 and `lang` is still `es`

#### Scenario: CSRF and auth
- GIVEN `csrf_app`
- WHEN PATCH is sent without a token, then anonymously with a token
- THEN 400, then 401 JSON

### Requirement: PREF-5 Session carries prefs [c]

After `PATCH /me/prefs`, `GET /auth/session` MUST report the same prefs under `data.prefs` (see API-4), so a client can bootstrap everything from one call.

#### Scenario: Round trip
- GIVEN a logged-in user who patched `{"accent":"cyan"}`
- WHEN `GET /auth/session`
- THEN `data.prefs.accent == "cyan"`

### Requirement: PREF-6 Client defaults and Auto resolution [e]

The SPA MUST resolve effective values as: `density` Auto = `compact` when the viewport width is at most 860 px, else `regular`; `collection_view` Auto = `grid` when width is at most 860 px, else `table`; `accent` null = `orange`; `bg_intensity` null = 100 (the default is confirmed visually in the PR screenshots and MAY change); `lang` null = browser language, then `es`. Auto values MUST re-evaluate when the viewport crosses the threshold. Effective values MUST be applied as `data-density` (absent for `regular`) and `data-accent` on `<html>` plus the background variables of DS-5.

#### Scenario: Auto density on a phone
- GIVEN prefs all `null` and viewport 390 px wide [vitest]
- WHEN the app renders
- THEN `<html data-density="compact">`

#### Scenario: Auto density on desktop
- GIVEN prefs all `null` and viewport 1280 px wide [vitest]
- WHEN the app renders
- THEN `<html>` has no `data-density` attribute and `data-accent="orange"`

#### Scenario: Explicit overrides Auto
- GIVEN `density:"comfy"` and a 390 px viewport [vitest]
- WHEN the app renders
- THEN `data-density="comfy"`

### Requirement: PREF-7 Applied before first render [e]

The SPA MUST mirror the last known stored prefs (`null` = Auto is preserved) in `localStorage` key `rb_prefs_v1` and apply them to `<html>` synchronously before the first paint of React, for anonymous and authenticated visits, so there is no theme flash. Once the session loads, the server prefs MUST replace the mirror. A missing, corrupt or out-of-domain mirror MUST be ignored (defaults apply). The mirror MUST contain only the five preference fields.

#### Scenario: Cached prefs applied early
- GIVEN `rb_prefs_v1 = {"accent":"cyan"}` and the session request still pending [vitest]
- WHEN the document boots
- THEN `<html data-accent="cyan">` before the session response arrives

#### Scenario: Corrupt mirror
- GIVEN `rb_prefs_v1 = "{not json"` [vitest]
- WHEN the document boots
- THEN no error is thrown and defaults apply

#### Scenario: Server wins
- GIVEN mirror `accent:"cyan"` and a session with `prefs.accent:"orange"` [vitest]
- WHEN the session loads
- THEN `data-accent="orange"` and the mirror is updated

### Requirement: PREF-8 Saving behaviour [e]

Changes made on the Interface page (SHELL-7) and the ES/EN toggle MUST apply immediately (optimistic), then persist with `PATCH /me/prefs` sending only the changed field. The background slider MUST be debounced (one PATCH after the user stops). If the PATCH fails the UI MUST revert to the previous value and show an error toast. Choosing "Auto" MUST send `null`. For anonymous users the language toggle MUST persist only to `rb_lang`.

#### Scenario: Optimistic success
- GIVEN a logged-in user on the Interface page [vitest]
- WHEN they pick accent Cyan
- THEN `data-accent="cyan"` immediately and one PATCH `{"accent":"cyan"}` is sent

#### Scenario: Failure reverts
- GIVEN the PATCH is mocked to fail with 500 [vitest]
- WHEN the user picks density Comfy
- THEN the previous density is restored and a toast with an error is shown

#### Scenario: Slider debounce
- GIVEN the user drags the slider through 10 values within the debounce window [vitest]
- WHEN dragging stops
- THEN exactly one PATCH is sent with the last value

#### Scenario: Auto sends null
- GIVEN `density:"comfy"` stored [vitest]
- WHEN the user chooses Auto
- THEN the request body is `{"density":null}`
