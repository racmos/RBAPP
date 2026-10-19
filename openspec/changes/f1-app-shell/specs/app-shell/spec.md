# Delta for app-shell

> Tags: all requirements are unit `[e]` of change f1-app-shell. `[vitest]` = Vitest + Testing Library (jsdom; viewport set per scenario). Untagged backend scenarios are pytest-testable. Breakpoints: `md` = 860 px (navigation switch). Brand name: "Rift Manager".

## ADDED Requirements

### Requirement: SHELL-1 Layout and landmarks [e]

Authenticated routes MUST render inside `AppShell`: a `header` with the topbar, a `main` landmark, and the bottom navigation below `md`. Content width MUST be capped at `--maxw` (1280 px) and at `--maxw-wide` (1760 px) from `2xl` (1600 px). Bottom padding for the bottom nav (including the safe-area inset) MUST apply only when it is shown. A "skip to content" link MUST be the first focusable element.

#### Scenario: Landmarks
- GIVEN an authenticated route [vitest]
- WHEN the DOM is queried
- THEN exactly one `main`, one `banner` and one navigation per visible nav exist, and the first tab stop is "skip to content"

#### Scenario: Padding only with botnav
- GIVEN viewport 1280 px [vitest]
- WHEN the shell renders
- THEN no bottom navigation is in the DOM/visible and no extra bottom padding class is applied

### Requirement: SHELL-2 Topbar and branding [e]

The topbar MUST be sticky (64 px; 56 px below `sm`). It MUST show the **wordmark** "Rift Manager" at `md` and above and the **mark** only below `md`, both with the accessible name "Rift Manager", linking to the app home. At `md` and above it MUST list the navigation entries (SHELL-5), an ES/EN toggle, the user avatar with initials and a logout button; the logout button MUST keep an accessible name when its text is hidden. The active entry MUST have `aria-current="page"`.

#### Scenario: Wordmark on desktop
- GIVEN viewport 1280 px [vitest]
- WHEN the topbar renders
- THEN the wordmark is displayed and the mark-only variant is not

#### Scenario: Mark on phone
- GIVEN viewport 390 px [vitest]
- WHEN the topbar renders
- THEN the mark-only variant is displayed and the full nav list is not

#### Scenario: Logout name
- GIVEN any viewport [vitest]
- WHEN the logout control is queried by role "button" and name "Cerrar sesión"
- THEN it is found

### Requirement: SHELL-3 Bottom navigation [e]

Below `md` the shell MUST show a bottom navigation with at most 5 items: four primary SPA destinations and "Más". Labels MUST be at least 11 px. The active item MUST carry `aria-current="page"`. It MUST be hidden at `md` and above. Safe-area insets MUST be respected.

#### Scenario: Five items
- GIVEN viewport 390 px [vitest]
- WHEN the bottom nav renders
- THEN it contains at most 5 links/buttons, the last being "Más"

#### Scenario: Hidden on desktop
- GIVEN viewport 1024 px [vitest]
- WHEN the shell renders
- THEN the bottom nav is not present

### Requirement: SHELL-4 "Más" sheet [e]

"Más" MUST open a native `<dialog>` sheet containing: Account/Interface, the legacy modules, language selection, install (PWA-6, only when applicable), Admin (only for admins) and logout. Escape and backdrop MUST close it and focus MUST return to "Más". Activating an entry MUST close the sheet.

#### Scenario: Contents for a normal user
- GIVEN a non-admin on a phone [vitest]
- WHEN "Más" is activated
- THEN the sheet lists Interface, legacy modules, language and logout, and no Admin entry

#### Scenario: Admin entry
- GIVEN an admin user [vitest]
- WHEN the sheet is opened
- THEN an Admin entry is present

#### Scenario: Close and focus
- GIVEN the open sheet [vitest]
- WHEN Escape is pressed
- THEN the sheet closes and focus is on the "Más" button

### Requirement: SHELL-5 Navigation registry [e]

Navigation MUST be generated from one registry whose entries have status `spa`, `legacy` or `planned`. `spa` entries use router links. `legacy` entries MUST be plain `<a href>` full navigations to Jinja pages taken from a tested `legacyRoutes.ts`. `planned` entries MUST NOT be rendered. Entries flagged admin-only MUST NOT be rendered for non-admins. Every `legacyRoutes.ts` URL MUST match a real Flask route (checked by a backend test against the URL map).

#### Scenario: Legacy is a real link
- GIVEN the registry entry for Collection with status `legacy` [vitest]
- WHEN rendered
- THEN it is an anchor with `href="/riftbound/collection"` and no router `Link`

#### Scenario: Planned hidden
- GIVEN an entry with status `planned` [vitest]
- WHEN the nav renders
- THEN it does not appear

#### Scenario: Routes exist
- GIVEN the list of legacy URLs exported for the test
- WHEN each is resolved against the Flask `url_map`
- THEN every URL matches an existing rule

### Requirement: SHELL-6 Home hub [e]

The SPA home MUST be a launcher with links to Dashboard, Sets, Cards, Collection, Decks and Profile (and Price only for admins), each following its registry status.

#### Scenario: Hub items
- GIVEN a non-admin [vitest]
- WHEN the home route renders
- THEN six launcher links are shown and "Price" is absent

### Requirement: SHELL-7 Interface page [e]

Route `/account/interface` MUST offer: density (Auto, Compact, Regular, Comfy), accent (Cyan, Orange), background intensity slider 0 to 100 with its value, language (ES, EN; Auto MAY be offered) and default collection view (Auto, Table, Grid). Each control MUST be labelled, keyboard operable, and apply live. Persistence follows PREF-8. At `xl` (1240 px) and above the page SHOULD show a live preview next to the controls (desktop shows more).

#### Scenario: Controls present
- GIVEN the Interface page [vitest]
- WHEN rendered
- THEN the five controls exist with accessible names and options as listed

#### Scenario: Live background
- GIVEN the slider at 100 [vitest]
- WHEN the user sets it to 0
- THEN `--bg-image-opacity` becomes 0 immediately

#### Scenario: Axe clean
- GIVEN the rendered page [vitest]
- WHEN `vitest-axe` runs
- THEN there are no violations

### Requirement: SHELL-8 Standard states [e]

The shell MUST provide Skeleton (`aria-busy` regions), EmptyState, ErrorState (message plus a retry action), a route-level ErrorBoundary/`errorElement` that prevents a white screen, and a 404 view for unknown routes rendered inside the shell with a link home. The 404 view is a SPA route, distinct from the 404 returned by the server for missing assets (HOST-3).

#### Scenario: Unknown route
- GIVEN an authenticated user [vitest]
- WHEN they open `/riftbound/app/does-not-exist`
- THEN the 404 view is shown inside the shell with a link to home

#### Scenario: Render error
- GIVEN a route component that throws [vitest]
- WHEN it renders
- THEN the ErrorState is shown and the topbar remains usable

#### Scenario: Retry
- GIVEN an ErrorState with a retry action [vitest]
- WHEN the user activates retry
- THEN the failed query is refetched

### Requirement: SHELL-9 Axe on the shell [e]

`vitest-axe` MUST report no violations for the authenticated shell at a phone viewport (with bottom nav) and at a desktop viewport (with topbar nav), including the open "Más" sheet.

#### Scenario: Both layouts
- GIVEN shell renders at 390 px and 1280 px [vitest]
- WHEN `vitest-axe` runs
- THEN there are no violations

### Requirement: SHELL-10 Jinja coexistence and rename [e]

`app/templates/base.html` MUST contain a link labelled "Nueva app" pointing to `/riftbound/app/`. The visible product name and `<title>` text of Jinja templates other than the landing `/` MUST be "Rift Manager" (no remaining "Riftbound Manager" in them). The landing `/` is unchanged until F11. All existing Jinja routes and their tests MUST keep passing, with assertions updated only for the renamed strings.

#### Scenario: Link present
- GIVEN an authenticated request to `/riftbound/`
- WHEN the HTML is read
- THEN it contains an anchor to `/riftbound/app/` with the text "Nueva app"

#### Scenario: Titles renamed
- GIVEN the rendered pages login, register, dashboard, set, card, collection, deck, price and profile
- WHEN `<title>` and the brand text are read
- THEN they contain "Rift Manager" and not "Riftbound Manager"

#### Scenario: Landing untouched
- GIVEN `GET /`
- WHEN rendered
- THEN its content is unchanged from before the change

#### Scenario: Full suite
- GIVEN the whole pytest suite
- WHEN run
- THEN all F0 and baseline tests pass
