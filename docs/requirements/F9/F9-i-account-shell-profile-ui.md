# F9-i: Account shell and profile UI

| Field | Value |
|---|---|
| Phase / unit | F9 / i |
| Branch | `feat/f9i-account-profile-ui` (from up-to-date `main`, F9-b and F9-c merged) |
| Depends on | F9-b (`GET`/`PATCH /me`, optional e-mail, `countries`, types), F9-c (`POST`/`DELETE /me/avatar`, `avatar_url`) |
| Size forecast | ~600 authored lines (tests and docs included) |
| Risk | `Risk: none` |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` |
| Save as | `docs/requirements/F9/F9-i-account-shell-profile-ui.md` |

## Objective

The account area becomes one place with sections (Profile and Interface now; Security and API come in
F9-j): tabs on phones, a sidebar on desktop. On the profile page a user sets a display name, bio,
country and city, uploads a photo with a preview or removes it, and keeps changing their e-mail and
password as today; the e-mail can now be removed, and registration accepts an empty e-mail. Signed-in
users see each other's photo instead of initials. Frontend only.

## Read first

- `AGENTS.md` (Frontend; App shell and preferences), `docs/knowledge/conventions.md` section 5
- `docs/requirements/F9/README.md` (UI table, D-F9-1, D-F9-3/D-F9-12, D-F9-7),
  `F9-b-profile-reauth.md` (S4-S8, S12, S14), `F9-c-avatar.md` (S3, S4, S7-S9, S11)
- `frontend/src/account/ProfilePage.tsx` (+ test), `InterfacePage.tsx`, `frontend/src/app/routes.tsx`,
  `frontend/src/shell/navRegistry.ts`, `Topbar.tsx`, `HomeHub.tsx`, `frontend/src/components/ui/`
  (`Avatar`, `SettingsCard`, `Field`, `Input`, `Select`, `Modal`, `ConfirmDialog`, `Skeleton`,
  `ErrorState`), `frontend/src/auth/RegisterPage.tsx`, `registerChecks.ts`, `frontend/src/lib/breakpoints.ts`
- `frontend/src/i18n/resources.ts` (adding a namespace), `catalogCheck.test.ts`

## Scope

In:
- `AccountLayout` (route layout for `/account/*`) and its section navigation
- Profile page: identity card (avatar), details form, e-mail card with "Remove email", the existing
  password card unchanged (F9-j moves it to Security)
- `Avatar` primitive shows an image when given one (topbar, home hub, account)
- Register form: optional e-mail
- New `account` i18n namespace (new strings only; the existing `prefs:profile.*` keys stay where they
  are)

Out (do not do, even if tempting):
- Security and API sections, re-auth dialog (F9-j), connections card (F9-g)
- Any backend change (if a contract is missing, stop and report)
- Client-side image cropping tools (the server centre-crops; the preview shows that crop)
- A public profile page or showing other users' bio/country/city anywhere

## Specs

S1. Routes: `/account` redirects (loader) to `/account/profile` (it went to `/account/interface`);
    `/account/profile` and `/account/interface` become children of a lazy `AccountLayout` route inside
    the signed-in shell (`requireAuth` as today). Unknown `/account/<x>` → the shell's NotFound. The
    topbar account link points to `/account` (was `/account/interface`).
S2. Section navigation (`account/sections.ts`, one list): `profile` "Profile", `interface` "Interface"
    (F9-j adds `security` and `api` between them: order Profile, Security, API, Interface). Rendered as:
    below 1240 px a horizontally scrollable row of tabs (`nav` with `aria-label` "Account sections",
    links with `aria-current="page"`), at 1240 px and wider a sticky sidebar 264 px wide with the
    identity summary (avatar 42 px, display name or username, `@username`) and the section links. The
    nav registry keeps `profile` and `interface` entries (no new module).
S3. Profile layout: below 860 px one column of cards (Identity, Details, Email, Password); 860-1239 px
    two card columns (Identity + Details | Email + Password); 1240 px and wider the sidebar plus two
    columns; 1600 px and wider the sidebar plus three columns (Identity | Details | Email + Password).
    Desktop shows more cards side by side, it never just stretches one card.
S4. Identity card: avatar 80 px (image when `avatar_url`, else initials of the display name or
    username), display name (or username), `@username`, "Member since {{date}}" (`member_since`, date
    via `lib/format.ts`), buttons "Change photo" and "Remove photo" (the second only with an avatar).
S5. Photo upload: "Change photo" opens the file picker (`accept="image/jpeg,image/png,image/webp,image/gif"`).
    A file over 5 MB is refused in the browser with the `file_too_large` message (`max_mb: 5`) and
    nothing is sent. Otherwise a `Modal` "New profile photo" shows the image centre-cropped in a circle
    of 160 px (CSS `object-fit: cover`, the same crop the server makes) with "Use this photo" and
    "Cancel"; the object URL is revoked on close. "Use this photo" → `POST /me/avatar` (multipart,
    through `request()` like `uploadAdminCardImage`) → the session user and the `GET /me` query get the
    new `avatar_url`, toast "Profile photo updated."; `image_invalid` / `file_too_large` / 429 → the
    translated error inside the modal, which stays open. Hint under the buttons: "JPEG, PNG, WebP or
    GIF, up to 5 MB. It is cropped to a square."
S6. Remove photo: `ConfirmDialog` "Remove your profile photo?" / "Signed-in users will see your
    initials instead." / "Remove" → `DELETE /me/avatar` → toast "Profile photo removed."
S7. Details card ("Details", hint "Your display name and photo are shown to signed-in users. Your bio,
    country and city are only for you."): fields Display name (hint "Up to 40 characters. Empty shows
    your username."), Bio (textarea, live counter "{{count}} of 240 characters"), Country (`Select`
    with "Not set" plus every code of `/meta/config` `countries`, labelled with
    `Intl.DisplayNames(['en'], {type: 'region'})` and sorted by label; the code itself when no label
    exists), City; one "Save details" button ("Saving…"), enabled only when something changed. Sends
    only the changed fields to `PATCH /me` (`""` clears). Client checks mirror the server limits (40,
    240, 80) with the `errors:validation.*` messages; server `details` map to the fields; focus moves
    to the first invalid field; toast "Details saved."
S8. Email card (existing form, `prefs:profile.email.*` strings): the field may be emptied; an empty
    value with an e-mail on file shows a "Remove email" action instead of "Save email" →
    `ConfirmDialog` "Remove your email?" / "Your account will have no email address. There is no
    password recovery by email either way." / "Remove" → `PATCH /me/account {email: null}` → toast
    "Email removed."; without an e-mail on file the card says "No email on file." above the field.
S9. Password card: unchanged behaviour and strings (moved to Security by F9-j).
S10. Register form (`/register`): the e-mail label becomes "Email (optional)" with the hint "Used only
    to identify your account. There is no password recovery by email."; an empty e-mail passes the
    client check and is sent as absent; a non-empty one keeps today's checks.
S11. `Avatar` primitive: optional `src` (and `size`); renders an `<img>` (`alt` = the `label` when
    given, else `""` with the wrapper hidden as today) and falls back to the initials when the image
    fails to load; 64-px image (`&size=64`) for sizes up to 64 px, 256 otherwise. Topbar, home hub,
    account sidebar and identity card pass `avatar_url`.
S12. Loading, error, offline: `GET /me` loading → `Skeleton` cards; error → `ErrorState` with retry
    (the section navigation stays); offline (`useOffline()`) → the cached session data is shown
    read-only (identity from the session, details from the cached `GET /me` if any), every button and
    field disabled with the offline reason (existing pattern of `ProfilePage`).
S13. Strings: new namespace `account` (`src/i18n/locales/en/account.json`, registered in
    `resources.ts`), exact English: `layout.title` "Account"; `layout.navLabel` "Account sections";
    `sections.profile` "Profile"; `sections.interface` "Interface"; `identity.title` "Identity";
    `identity.memberSince` "Member since {{date}}"; `identity.changePhoto` "Change photo";
    `identity.removePhoto` "Remove photo"; `identity.photoHint` "JPEG, PNG, WebP or GIF, up to 5 MB. It
    is cropped to a square."; `identity.photoAlt` "Profile photo of {{name}}"; `photo.title` "New
    profile photo"; `photo.use` "Use this photo"; `photo.uploading` "Uploading…"; `photo.cancel`
    "Cancel"; `photo.updated` "Profile photo updated."; `photo.removeTitle` "Remove your profile
    photo?"; `photo.removeBody` "Signed-in users will see your initials instead."; `photo.removeConfirm`
    "Remove"; `photo.removed` "Profile photo removed."; `details.title` "Details"; `details.hint` "Your
    display name and photo are shown to signed-in users. Your bio, country and city are only for you.";
    `details.displayName` "Display name"; `details.displayNameHint` "Up to 40 characters. Empty shows
    your username."; `details.bio` "Bio"; `details.bioCount` "{{count}} of 240 characters";
    `details.country` "Country"; `details.countryNone` "Not set"; `details.city` "City";
    `details.save` "Save details"; `details.saving` "Saving…"; `details.saved` "Details saved.";
    `email.remove` "Remove email"; `email.removeTitle` "Remove your email?"; `email.removeBody` "Your
    account will have no email address. There is no password recovery by email either way.";
    `email.removeConfirm` "Remove"; `email.removed` "Email removed."; `email.none` "No email on file.".
    `auth` namespace: `register.emailOptional` "Email (optional)"; `register.emailHint` "Used only to
    identify your account. There is no password recovery by email.".
S14. Accessibility: every form control through `Field`; the tab row and sidebar are `nav` landmarks
    with `aria-current`; the photo modal is the native-dialog `Modal` (focus trapped and returned to
    "Change photo"); the bio counter is tied with `aria-describedby`; status toasts are announced;
    targets ≥ 24×24 px; an axe test per page/breakpoint.

## API / data contract

No change. Uses `GET`/`PATCH /me`, `POST`/`DELETE /me/avatar`, `GET /users/<id>/avatar`,
`PATCH /me/account` (`email: null`), `POST /auth/register` (no e-mail), `GET /meta/config` (`countries`).

## UI

| Breakpoint | Layout |
|---|---|
| Mobile < 860 | Tab row (scrollable) under the page header; one column: Identity, Details, Email, Password. |
| Tablet 860-1239 | Tab row; two card columns. |
| Desktop ≥ 1240 | Sticky sidebar 264 px (avatar 42, name, `@username`, section links) + two card columns. |
| Wide ≥ 1600 | Sidebar + three card columns. |

States: S12. The Interface section keeps its page (live preview from 1240 px) inside the layout.

## Acceptance criteria

- [ ] AC1 `src/account/AccountLayout.test.tsx`: `/account` → profile, tabs below 1240 and sidebar from
      1240 (viewport mock), `aria-current`, interface still reachable, axe clean (S1, S2, S14)
- [ ] AC2 `src/account/ProfilePage.test.tsx` extended: column counts per breakpoint (class or
      structure), identity card, details form (changed-fields-only PATCH, limits, server details,
      focus), country labels via `Intl.DisplayNames`, e-mail removal with confirm, no-email state,
      password card unchanged, loading/error/offline states, axe clean (S3, S4, S7-S9, S12)
- [ ] AC3 `src/account/AvatarUpload.test.tsx`: 5 MB client refusal, preview modal, upload updates the
      session cache, server `image_invalid` keeps the modal open, remove with confirm, object URL
      revoked (S5, S6)
- [ ] AC4 `src/components/ui/Avatar.test.tsx`: image, size choice, fallback to initials on error (S11);
      Topbar/HomeHub tests show the image when `avatar_url` is set
- [ ] AC5 `src/auth/RegisterPage.test.tsx`: empty e-mail accepted and omitted from the body; bad e-mail
      still refused (S10)
- [ ] AC6 `src/i18n/catalogCheck.test.ts` green with the `account` namespace; CSS module and breakpoint
      rules hold (layers, `@media` from `breakpoints.ts`); `no-legacy-links` green
- [ ] AC7 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck &&
      npx vitest run && npm run build && npm run check:dist`
- [ ] AC8 Docs: `docs/frontend.md` (account area), `AGENTS.md` (Frontend tree `account/`: layout,
      sections, profile cards, avatar upload), `docs/knowledge/state.md`

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- PR title: `feat(frontend): account sections and profile with photo (F9 unit i)`. PR body: S# → tests,
  screenshots at 390 / 1024 / 1280 / 1600 px, rollback (revert; frontend rebuild).
- Never merge. The owner merges.

## After merge

- Deploy to dev: frontend rebuild only.
- Live checks: `/riftbound/app/account` opens Profile; save a display name and a country; upload a
  phone photo; the topbar shows it; remove it.
- Manual checks for the owner: phone photo upload (portrait and landscape come out upright and
  centred); register a test account without e-mail.

## Open questions

none
