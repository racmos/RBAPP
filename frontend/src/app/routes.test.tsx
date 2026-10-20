import { QueryClient } from '@tanstack/react-query';
import type { RouteObject } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createAppRoutes } from './routes';

const paths = (routes: RouteObject[]): string[] =>
  routes.flatMap((route) => [...(route.path ? [route.path] : []), ...paths(route.children ?? [])]);

afterEach(() => vi.unstubAllEnvs());

describe('route table (D13)', () => {
  it('has the signed-in pages and the auth screens', () => {
    const found = paths(createAppRoutes(new QueryClient()));
    expect(found).toEqual(
      expect.arrayContaining(['/login', '/register', '/', '/account', '/account/interface', '*']),
    );
  });

  describe('/_kitchen (5.10)', () => {
    it('is part of the development table', () => {
      vi.stubEnv('DEV', true);
      expect(paths(createAppRoutes(new QueryClient()))).toContain('/_kitchen');
    });

    it('is not part of the production table', () => {
      vi.stubEnv('DEV', false);
      expect(paths(createAppRoutes(new QueryClient()))).not.toContain('/_kitchen');
    });
  });
});
