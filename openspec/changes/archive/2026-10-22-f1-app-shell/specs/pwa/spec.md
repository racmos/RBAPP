# Delta for pwa

> Tags: all requirements are unit `[f]` of change f1-app-shell. `[build]` = asserted by a test/script over the production build output (`dist/`). `[vitest]` = Vitest + Testing Library. `[GH-CI]` = observable in GitHub Actions. `[MANUAL]` = real device/browser check. Identity: app name "Rift Manager". The SW never controls or caches Jinja pages or the API; the installed window may still open Jinja pages (manifest scope is wider than SW scope).

## ADDED Requirements

### Requirement: PWA-1 Manifest identity and scope [f]

The build MUST emit `manifest.webmanifest` with: `name` "Rift Manager", `short_name` "Rift Manager", `id` `/riftbound/`, `scope` `/riftbound/`, `start_url` `/riftbound/app/`, `display` `standalone`, `theme_color` and `background_color` `#06222c`, `categories` containing `games`. `start_url` MUST fall inside `scope`. `index.html` MUST link the manifest, set `<title>` "Rift Manager" and `apple-mobile-web-app-title` "Rift Manager".

#### Scenario: Manifest fields [build]
- GIVEN the production build
- WHEN `dist/manifest.webmanifest` is parsed
- THEN every field above has the stated value and `start_url` starts with `scope`

#### Scenario: Document head [build]
- GIVEN `dist/index.html`
- WHEN parsed
- THEN it has the manifest link, `theme-color` `#06222c`, title "Rift Manager" and the apple meta tags

### Requirement: PWA-2 Icons [f]

The manifest MUST list icons 192x192 and 512x512 (purpose `any`) and a 512x512 `maskable` icon whose mark lies inside the central 80% safe zone on `#06222c`. The build MUST also contain an `apple-touch-icon` 180x180 and a favicon (SVG or ICO; a simplified mark if the full mark is illegible at 16 to 32 px). The icons MUST be generated from the brand mark and committed (CI does not generate them). Declared sizes MUST match the real PNG dimensions.

#### Scenario: Icons present and sized [build]
- GIVEN the production build
- WHEN each manifest icon and the apple-touch icon are read
- THEN files exist, PNG dimensions equal the declared sizes, and one 512 icon has purpose `maskable`

#### Scenario: Safe zone and favicon [MANUAL]
- GIVEN the maskable icon in a mask previewer and the favicon at 16, 32 and 48 px
- WHEN reviewed
- THEN the mark is within the safe zone and the favicon is legible

### Requirement: PWA-3 Service worker scope and precache [f]

The service worker MUST be served at `/riftbound/app/sw.js` with scope `/riftbound/app/`. It MUST precache only the app shell: hashed JS/CSS, `index.html`, latin fonts, the background image variants (1920 px, 1280 px and portrait), the brand assets and icons. Navigation fallback MUST be `/riftbound/app/index.html`, allowed only for `^/riftbound/app/` and denying API, static and legacy paths. It MUST clean outdated caches. It MUST NOT register any runtime caching for `/riftbound/api/*`, `/riftbound/static/*` or Jinja pages and MUST NOT intercept their requests. In development the SW MUST be disabled.

#### Scenario: Precache content [build]
- GIVEN the generated `sw.js`
- WHEN its precache manifest is parsed
- THEN it includes `index.html`, hashed assets, the background images and icons, and no URL starting with `/riftbound/api`

#### Scenario: No runtime API caching [build]
- GIVEN the generated `sw.js`
- WHEN its routes are inspected
- THEN there is no route matching `/riftbound/api` and the navigation denylist covers API, static and legacy paths

#### Scenario: Registered scope [MANUAL]
- GIVEN the built app opened over HTTPS
- WHEN the SW registration is inspected
- THEN its scope is `/riftbound/app/` and a Jinja page is not controlled by it

### Requirement: PWA-4 Prompt-based update [f]

The SW registration MUST use prompt mode: a new SW waits and MUST NOT take control or reload the page by itself. The app MUST show a toast ("Nueva versión" with an "Actualizar" action) when an update is waiting. Activating the action MUST activate the new SW and reload. Dismissing MUST keep the current version running without losing in-progress form data. The app MUST check for updates hourly and when the page becomes visible again.

#### Scenario: Update available [vitest]
- GIVEN the registration reports `needRefresh = true`
- WHEN the app renders
- THEN the update toast with the "Actualizar" action is shown and the page is not reloaded

#### Scenario: Accept
- GIVEN the toast [vitest]
- WHEN the user activates "Actualizar"
- THEN the update function is called once

#### Scenario: Dismiss keeps state
- GIVEN a half-filled form and the update toast [vitest]
- WHEN the toast is dismissed
- THEN the form values remain and no reload happens

#### Scenario: Real update flow [MANUAL]
- GIVEN an installed older build and a newly deployed build
- WHEN the app is reopened
- THEN the prompt appears and accepting loads the new version

### Requirement: PWA-5 Rollback by self-destroying SW [f]

`sw.js` MUST be served with `no-cache` (HOST-2). The build tooling MUST support a self-destroying SW mode, documented in the rollback section of the docs, that unregisters the SW and clears its caches on clients. A plain revert of the frontend MUST NOT be considered a rollback of the PWA.

#### Scenario: Self-destroying build [build]
- GIVEN a build made with the self-destroying option
- WHEN `sw.js` is read
- THEN it contains unregister/cache-clearing logic and no precache manifest

#### Scenario: Documented
- GIVEN the docs
- WHEN searched for "self-destroying"
- THEN the rollback procedure is described

### Requirement: PWA-6 Install entry [f]

When the browser fires `beforeinstallprompt` and the app is not running standalone, the "Más" sheet and the equivalent desktop menu MUST show an "Install" item that triggers the saved prompt. On iOS Safari (no install event) the same item MUST open an instructions dialog (Share, then Add to Home Screen). The item MUST be hidden when the app already runs standalone or no install path exists.

#### Scenario: Android prompt [vitest]
- GIVEN a captured `beforeinstallprompt` event
- WHEN the user activates "Install"
- THEN the saved event's `prompt()` is called

#### Scenario: iOS dialog [vitest]
- GIVEN an iOS Safari user agent and no install event
- WHEN the user activates "Install"
- THEN a dialog with the Share and Add to Home Screen instructions opens

#### Scenario: Standalone hides it [vitest]
- GIVEN `display-mode: standalone` matches
- WHEN the sheet opens
- THEN there is no Install item

### Requirement: PWA-7 Offline shell and banner [f]

The shell MUST open offline from the precache. While the browser is offline the app MUST show a non-blocking `OfflineBanner` (`role="status"`, translated) and mutating controls MUST not pretend to succeed (F1 is read-only offline). If the boot session request fails with a network error AND the "was signed in" hint exists, the shell MUST render with the banner; without the hint the app MUST show an ErrorState with retry. A 401 always goes to login. The banner MUST disappear when connectivity returns.

#### Scenario: Offline boot with hint [vitest]
- GIVEN the session request fails with a network error and the hint is set
- WHEN the app boots
- THEN the shell and the offline banner are rendered

#### Scenario: Offline boot without hint [vitest]
- GIVEN the same failure and no hint
- WHEN the app boots
- THEN an ErrorState with a retry action is rendered

#### Scenario: Back online [vitest]
- GIVEN the banner is shown
- WHEN the `online` event fires
- THEN the banner is removed

#### Scenario: Real offline [MANUAL]
- GIVEN an installed app and airplane mode
- WHEN it is opened
- THEN the shell opens with the banner

### Requirement: PWA-8 Session persistence in the installed app [f]

Because the installed app has its own cookie jar, a login with "Remember me" (default) MUST keep the user signed in after the installed app is closed and reopened (SESS-1 remember cookie, 30 days).

#### Scenario: Reopen installed app [MANUAL]
- GIVEN an installed app signed in with Remember me on
- WHEN it is closed completely and reopened the next day
- THEN the user is still signed in

### Requirement: PWA-9 Installability verification [f]

Lighthouse installability MUST pass for `/riftbound/app/` over HTTPS. Installation MUST work on Android (Chrome) and on iOS (Safari Add to Home Screen). Results are recorded in the PR.

#### Scenario: Device checklist [MANUAL]
- GIVEN the deployed build over HTTPS
- WHEN Lighthouse installability, Android install and iOS add-to-home are run
- THEN all succeed and the launched window uses the "Rift Manager" name and icon
