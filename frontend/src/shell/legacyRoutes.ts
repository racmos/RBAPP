import routes from './legacy-routes.json';

/**
 * The Jinja pages the shell links to (SHELL-5). The JSON is the contract file: a backend test
 * (`tests/test_frontend_contracts.py::TestLegacyRoutes`) resolves every URL against the Flask
 * `url_map`, so a renamed route fails CI instead of becoming a dead link.
 */
export type LegacyKey = keyof typeof routes;

export const LEGACY_ROUTES: Readonly<Record<LegacyKey, string>> = routes;

export const legacyHref = (key: LegacyKey): string => LEGACY_ROUTES[key];
