# M-c: Hygiene — no private hosts in tracked files, no exception text to users, one clock

| Field | Value |
|---|---|
| Phase / unit | M (maintenance, outside the phases) / c |
| Branch | `chore/m-c-hygiene` (from up-to-date `main`) |
| Depends on | M-b merged (#30) — done |
| Size forecast | ~300-400 authored lines (error helper + call sites, clock call sites, two catalog entries, tests, docs). |
| Risk | `Risk: item 2 (error responses and what they disclose) + item 3 (legacy JSON error bodies gain fields; existing keys kept)` |
| TDD | Strict for S2-S5 (RED first through the public HTTP interface). S6 re-creates the clock guard as a test. S1 is documentation. |
| Written by | gentle-shell on the owner's instruction (2026-10-24), in place of the planner. |

## Objective

Decisions of 2026-10-22 (`docs/knowledge/decisions-2026-10-22.md`, "Agreed order", item 3): "Hygiene:
remove private IPs and the dev domain from tracked files (no history rewrite); legacy endpoints stop
returning exception text (clear message + error code to the user, full detail logged and visible to the
admin); replace `datetime.utcnow()` with `app/utils/clock.utcnow()`."

## Specs

S1. Private hosts. No tracked file contains a private IPv4 address (`192.168.*`, `10.*`, `172.16-31.*`;
    version strings are not addresses) or the dev domain. `docs/nginx_config` uses the placeholder
    `example.com` (server names and certificate paths), keeping its two `proxy_pass` lines and headers.
    `openspec/changes/archive/2026-10-19-f0-foundation/**` replaces the addresses with `<dev-db-host>` /
    `<prod-host>` and the domain with `<dev-domain>` (only those tokens change). Git history is not rewritten.
    Check: `git grep -nIE "\b(192\.168|10\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01]))\.[0-9]{1,3}\.[0-9]{1,3}\b" -- . ':!frontend/package*.json' ':!*.svg'`
    and `git grep -nI "racmos""dev"` (the token is split so this document does not match itself) print nothing.
S2. One helper builds every "unexpected failure" JSON body of the legacy endpoints:
    `success: false`, a clear human `message` (no exception text), `code` (S4), and `detail`
    (`"<ExceptionClass>: <text>"`) **only when the caller is a signed-in admin**. The full traceback is
    logged with `current_app.logger.exception(...)` every time. Existing keys of each body (`sets`, `steps`,
    `stats`, `errors`) stay with the same types so the legacy pages keep working; `errors` holds the clear
    message, not the exception text.
S3. Call sites: `cards.upload_card_image` (500), `price.refresh_riot_sets`, `price.extract_riot_cards`,
    `price.cardmarket_load`, `price` auto-match endpoint (all 500s), and the generic `except Exception` of
    `@validate_json` (400, `error: "Bad Request"`, message "Invalid request body"). The Pydantic validation
    branch of `@validate_json` is unchanged. The collection import "skipped" reasons (our own `ValueError`
    messages per CSV line) are user feedback and stay.
S4. New error codes in `ErrorCode`: `internal_error` (the 500s of S3) and `bad_request` (the generic 400 of
    `@validate_json`). Both get `code.<value>` in `frontend/src/i18n/locales/{es,en}/errors.json`. The
    backend/frontend catalog test is re-created (test policy): every `ErrorCode` value has `code.<value>` in
    both catalogs.
S5. Tests through the HTTP interface, for each S3 call site: with the failing service mocked to raise an
    exception carrying a secret-looking text, a plain user / admin gets the documented status, `code`,
    clear `message`; the text appears in the body only under `detail` and only for the admin; the log
    records it. For `@validate_json`: a non-admin never gets `detail`.
S6. Clock. No `datetime.utcnow` remains under `app/` (call sites and column defaults). Calls use
    `clock.utcnow()` through the module; column defaults use `lambda: clock.utcnow()` (as `prefs.py`).
    No schema change (`flask db check` clean on SQLite in a test or by command). A guard test fails if
    `datetime.utcnow` appears under `app/`.
S7. Docs: `AGENTS.md` lists the two new codes; `docs/knowledge/state.md` (unit row M-c, follow-ups "Hygiene"
    and "Legacy endpoints leak exception text" removed, next unit F4-a); `docs/requirements/README.md` M-c row.
    Line endings preserved (`AGENTS.md`, `cards.py`, `validation.py`, several models and `docs/nginx_config`
    are CRLF).
S8. Lanes green: `pytest`, frontend lint, typecheck, `vitest run`, build, `check:dist`.

## Tasks

| ID | Specs | Route | Commit |
|---|---|---|---|
| T1 | S2-S5 | worker A | |
| T2 | S6 | worker B | |
| T3 | S1, S7 | parent | |
| T4 | S8 + independent verify (item 2) | parent + gentle-ai-verify | |

## Log

- L1 (owner, 2026-10-24): "continua tu ya con lo que hay planificado"
- L2 (gentle-shell): "visible to the admin" is implemented as a `detail` field returned only to signed-in
  admins, plus the server log; every leaking endpoint except `@validate_json` is admin-only today.
