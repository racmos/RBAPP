# Delta for i18n

> Tags: all requirements are unit `[d]` of change f1-app-shell (the language toggle UI is `[e]`). `[vitest]` = Vitest + Testing Library. Languages: `es` (default) and `en`. Card names and abilities are data, not UI, and are NOT translated.

## ADDED Requirements

### Requirement: I18N-1 Bundled catalogs with parity [d]

The SPA MUST ship ES and EN catalogs as bundled JSON (no runtime network fetch; they are part of the precache) split in namespaces `common`, `nav`, `auth`, `errors`, `prefs` (further namespaces are added per phase). A Vitest parity test MUST fail when (a) a key exists in one language and not the other, (b) the `{{placeholders}}` of a key differ between languages, or (c) a plural-suffixed key (`_one`, `_other`, ...) is missing a form required by that language. Keys not referenced by code SHOULD be reported as unused.

#### Scenario: Missing key fails
- GIVEN a key present in `es/auth.json` and absent in `en/auth.json`
- WHEN the parity test runs
- THEN it fails naming the key and the language

#### Scenario: Placeholder mismatch fails
- GIVEN `es: "Quedan {{count}}"` and `en: "Left {{n}}"`
- WHEN the parity test runs
- THEN it fails

#### Scenario: Catalogs in the bundle
- GIVEN the production build
- WHEN the dist is inspected
- THEN both catalogs are inside precached assets and no request for translations is made at runtime

### Requirement: I18N-2 Language resolution [d]

The active language MUST be resolved in this order: stored account preference `lang` (authenticated); `rb_lang` in `localStorage` (anonymous or before the session loads); the first language in `navigator.languages` whose primary subtag is `es` or `en`; finally `es`. Unsupported values MUST be ignored.

#### Scenario: Account pref wins
- GIVEN `prefs.lang:"en"` and browser language `es-ES` [vitest]
- WHEN the app renders
- THEN the UI is English

#### Scenario: Browser detection
- GIVEN no stored language and `navigator.languages = ["fr-FR","en-US"]` [vitest]
- WHEN the app renders
- THEN the UI is English

#### Scenario: Fallback
- GIVEN no stored language and `navigator.languages = ["fr-FR"]` [vitest]
- WHEN the app renders
- THEN the UI is Spanish

### Requirement: I18N-3 Document effects and formatting [d]

Changing language MUST apply without reload and MUST update `<html lang>` and `document.title` (format `<page title> · Rift Manager`, root `Rift Manager`). Numbers, dates and money MUST be formatted with `Intl` using locale `es-ES` for `es` and `en-GB` for `en` (not the browser locale). The product name "Rift Manager" MUST NOT be translated.

#### Scenario: Switch language
- GIVEN the app in Spanish [vitest]
- WHEN the user switches to English
- THEN `document.documentElement.lang == "en"`, visible labels change and the title ends with `Rift Manager`

#### Scenario: Locale formatting
- GIVEN language `es` [vitest]
- WHEN `formatMoney(1234.5)` is called
- THEN the result follows `es-ES` EUR formatting (decimal comma)

### Requirement: I18N-4 Server errors translated by code [d]

For API errors the SPA MUST look up `errors:code.<code>` (field details use `errors:validation.<field>.<code>`, then `errors:validation.<code>`) and interpolate `params` (for example `retry_after`). If the code is absent or has no catalog entry the SPA MUST fall back to the API `message`; if that is absent too, to a generic translated error. Raw English backend prose MUST NOT be shown when a catalog entry exists.

#### Scenario: Known code
- GIVEN an error `{code:"username_taken"}` and language `es` [vitest]
- WHEN it is rendered
- THEN the Spanish catalog text is shown, not the API `message`

#### Scenario: Params
- GIVEN `{code:"locked", params:{retry_after:30}}` [vitest]
- WHEN rendered
- THEN the text includes the interpolated seconds

#### Scenario: Unknown code
- GIVEN `{code:"brand_new_code", message:"Something odd"}` [vitest]
- WHEN rendered
- THEN `Something odd` is shown

### Requirement: I18N-5 No missing keys at runtime [d]

Every key referenced by `t()` in source MUST exist in both catalogs; this MUST be enforced by a test or typed resources. At runtime a missing key MUST fall back to the `es` text and MUST NOT render the raw key in production.

#### Scenario: Typed or scanned keys
- GIVEN source code calling `t("auth.login.title")`
- WHEN the key scan or typecheck runs
- THEN it passes only if the key exists in `es` and `en`
