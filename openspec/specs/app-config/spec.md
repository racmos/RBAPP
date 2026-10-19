# app-config Specification

Source: change f0-foundation (archived 2026-10-19)

> Tags: `[a]`..`[e]` = delivery unit of change f0-foundation. `[PG-CI]` = verify in the PostgreSQL CI job; `[MANUAL]` = manual/ops check; `[GH-CI]` = only observable in GitHub Actions. Untagged scenarios are pytest-testable (SQLite, no network).

## Requirements

### Requirement: CFG-1 No credentials in tracked code [a]

Tracked source files MUST NOT contain a default `SECRET_KEY`, a database password or a database host. `SECRET_KEY` and `DATABASE_URL` MUST be read only from environment variables.

#### Scenario: Legacy literals are gone
- GIVEN the working tree
- WHEN `config.py`, `run.py`, `wsgi.py`, `app/**/*.py` and `.env.example` are scanned for the legacy default `SECRET_KEY` literal, the legacy database password placeholder `<old-db-password>`, and the legacy database host IP address
- THEN there are zero matches

#### Scenario: Values come from the environment
- GIVEN `RB_ENV=production`, a 48-char `SECRET_KEY` and `DATABASE_URL=postgresql+psycopg://u:p@h/db`
- WHEN the app config is built
- THEN `SECRET_KEY` and `SQLALCHEMY_DATABASE_URI` equal those values

### Requirement: CFG-2 Environment selection by RB_ENV [a]

`RB_ENV` MUST select one of `development`, `testing`, `production`. When unset the effective environment MUST be `production`. Any other value MUST raise `RuntimeError` naming the allowed values.

#### Scenario: Unset means production
- GIVEN `RB_ENV` is unset
- WHEN the config class is resolved
- THEN it is the production class

#### Scenario: Unknown value
- GIVEN `RB_ENV=staging`
- WHEN the app is created
- THEN `RuntimeError` is raised and its message lists `development, testing, production`

### Requirement: CFG-3 Fail-fast validation after test overrides [a]

`create_app` MUST validate the config AFTER applying test overrides. When `TESTING` is false and the environment is not `development`, startup MUST raise `RuntimeError` if `SECRET_KEY` is missing, shorter than 32 chars, equals the legacy default, or contains `change-me`/`changeme` (case-insensitive), or if `DATABASE_URL` is missing. The message MUST name the offending variable and MUST NOT echo secret values. In `development`, `DATABASE_URL` is still required; `SECRET_KEY` MAY be omitted (an ephemeral random key is used).

The legacy default is kept in the denylist only as sha256 digests, so that the CFG-1 scan for the literal stays clean (R13). The raised error is `ConfigError`, a subclass of `RuntimeError`.

#### Scenario: Missing key in production
- GIVEN `RB_ENV=production`, no `SECRET_KEY`, `TESTING` not set
- WHEN `create_app()` runs
- THEN `RuntimeError` is raised and its message contains `SECRET_KEY`

#### Scenario: Weak keys rejected
- GIVEN production env and `SECRET_KEY` = the legacy default key, or `change-me-please-change-me-please-xx`, or a 31-char string
- WHEN `create_app()` runs
- THEN `RuntimeError` is raised for each, and the message does not contain the key value

#### Scenario: Missing database URL
- GIVEN production env, a valid 32+ char `SECRET_KEY`, no `DATABASE_URL`
- WHEN `create_app()` runs
- THEN `RuntimeError` is raised and its message contains `DATABASE_URL`

#### Scenario: Test contract unchanged
- GIVEN no `RB_ENV`, `SECRET_KEY` or `DATABASE_URL` in the environment
- WHEN `create_app(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', SECRET_KEY='test-secret-key')` runs
- THEN the app starts and the 93 baseline tests still pass

### Requirement: CFG-4 dotenv only in development [a]

A `.env` file MUST be loaded only when the effective environment is `development`. In `testing` and `production` it MUST NOT be read.

When `RB_ENV` is unset, the file is read once so that it can declare `RB_ENV=development`; an explicit `RB_ENV=production` or `testing` never reads it (R15, D1). Values already in the process environment win (`override=False`).

#### Scenario: Development loads .env
- GIVEN `RB_ENV=development` and a `.env` defining `DATABASE_URL`
- WHEN the app is created
- THEN `DATABASE_URL` from `.env` is used

#### Scenario: Production ignores .env
- GIVEN `RB_ENV=production` and a `.env` defining `SECRET_KEY` (valid)
- WHEN `create_app()` runs
- THEN `RuntimeError` mentioning `SECRET_KEY` is raised (the file was not read)

### Requirement: CFG-5 Engine options follow the effective URI [a]

`SQLALCHEMY_ENGINE_OPTIONS` MUST be computed from the effective URI after overrides: no `client_encoding` for SQLite; `client_encoding=utf8` for PostgreSQL; `pool_pre_ping` always.

#### Scenario: SQLite override
- GIVEN `create_app(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:')`
- WHEN the engine options are read
- THEN they contain `pool_pre_ping=True` and no `connect_args`

#### Scenario: PostgreSQL URI
- GIVEN a `postgresql+psycopg://` URI
- WHEN the engine options are computed
- THEN `connect_args == {'client_encoding': 'utf8'}`

### Requirement: CFG-6 .env.example and deployment docs [a]

`.env.example` MUST list every variable the app reads (`RB_ENV`, `SECRET_KEY`, `DATABASE_URL` with the `postgresql+psycopg://` driver, cookie, proxy, limiter and captcha variables added by later units) with placeholder values only. `docs/riftbound.service` MUST load secrets via `EnvironmentFile=` and MUST NOT embed them. The docs SHOULD recommend rotating the DB password and `SECRET_KEY` and firewalling port 8000 to the Nginx host.

The entry point stays `run:app`, matching the running service; `wsgi.py` keeps `app = application` as an alias (R8).

#### Scenario: Example file is safe
- GIVEN `.env.example`
- WHEN parsed
- THEN `DATABASE_URL` starts with `postgresql+psycopg://`, and no value is a real credential (scan from CFG-1 passes)

#### Scenario: Service unit [MANUAL]
- GIVEN `docs/riftbound.service`
- WHEN reviewed
- THEN it has `EnvironmentFile=`, no `SECRET_KEY=`/`DATABASE_URL=` literals, and starts `run:app`

### Requirement: CFG-7 Configurable proxy trust [a]

The number of trusted `X-Forwarded-For` hops MUST be set by `PROXY_FIX_X_FOR` (default 1).

#### Scenario: Default trusts one hop
- GIVEN default config and header `X-Forwarded-For: 203.0.113.9`
- WHEN a request is handled
- THEN `request.remote_addr == '203.0.113.9'`

#### Scenario: Trust disabled
- GIVEN `PROXY_FIX_X_FOR=0` and the same header
- WHEN a request is handled
- THEN `request.remote_addr` is the socket address, not `203.0.113.9`
