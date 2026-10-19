// @vitest-environment node
import { readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const SRC = fileURLToPath(new URL('../', import.meta.url));

const sources = (dir: string): string[] =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? sources(join(dir, entry.name))
      : /\.(ts|tsx)$/.test(entry.name) && !/\.test\./.test(entry.name)
        ? [join(dir, entry.name)]
        : [],
  );

describe('altcha is loaded lazily (D22, FAUTH-3)', () => {
  it('is imported by exactly one module, which only the lazy register route reaches', () => {
    const importers = sources(SRC)
      .filter((file) => /(from|import)\s+['"]altcha['"]/.test(readFileSync(file, 'utf8')))
      .map((file) => relative(SRC, file));
    expect(importers).toEqual(['auth/AltchaWidget.tsx']);
  });

  it('is reached only through RegisterPage, which only the router imports dynamically', () => {
    const importing = (module: string) =>
      sources(SRC)
        .filter((file) =>
          new RegExp(`from\\s+['"](@/auth/|\\./)${module}['"]`).test(readFileSync(file, 'utf8')),
        )
        .map((file) => relative(SRC, file));
    expect(importing('AltchaWidget')).toEqual(['auth/RegisterPage.tsx']);
    expect(importing('RegisterPage')).toEqual([]);

    const routes = readFileSync(join(SRC, 'app/routes.tsx'), 'utf8');
    expect(routes).toMatch(/import\('@\/auth\/RegisterPage'\)/);
  });
});
