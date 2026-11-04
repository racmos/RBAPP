import { ESLint } from 'eslint';
import { globSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
// @ts-expect-error ESM config file has no TypeScript declaration.
import config from '../../eslint.config.js';

function lint(code: string, file: string) {
  const eslint = new ESLint({
    overrideConfigFile: true,
    overrideConfig: config,
  });
  return eslint.lintText(code, { filePath: file });
}

const cardFile = (name: string) => join(process.cwd(), 'src/components/card', name);
const catalogFile = (name: string) => join(process.cwd(), 'src/catalog', name);

describe('ESLint boundaries (F2-e S13)', () => {
  it('flags a card component that imports from a feature folder', async () => {
    const result = await lint(
      "import { useAuth } from '@/auth/useAuth';\nexport const A = () => null;\n",
      cardFile('Bad.tsx'),
    );
    expect(result[0].errorCount).toBeGreaterThan(0);
    expect(result[0].messages.some((m) => m.message.includes('folder boundaries'))).toBe(true);
  });

  it('allows a card component with permitted imports', async () => {
    const result = await lint(
      "import { formatMoney } from '@/lib/format';\nimport { useTranslation } from 'react-i18next';\nimport { Badge } from '@/components/ui/Badge';\nimport type { CardSummary } from '@/api/types';\nexport function A({ p }: { p: CardSummary }) {\n  const { t } = useTranslation();\n  return <Badge tone=\"accent\">{formatMoney(1)} {t('ok')} {p.name}</Badge>;\n}\n",
      cardFile('Okay.tsx'),
    );
    expect(result[0].errorCount).toBe(0);
  });

  it('allows type-only imports from @/api in card components', async () => {
    const result = await lint(
      "import type { CardSummary } from '@/api/types';\nexport const A = (p: CardSummary) => p.name;\n",
      cardFile('Good.tsx'),
    );
    expect(result[0].errorCount).toBe(0);
  });

  it('flags a card component that imports values from @/api', async () => {
    const result = await lint(
      "import { CardSummary } from '@/api/types';\nexport const x: CardSummary = {} as CardSummary;\n",
      cardFile('BadApi.tsx'),
    );
    expect(result[0].errorCount).toBeGreaterThan(0);
    expect(result[0].messages.some((m) => m.message.includes('type'))).toBe(true);
  });

  it('flags a catalog component that imports from app', async () => {
    const result = await lint(
      "import { createAppRoutes } from '@/app/routes';\nexport const A = () => null;\n",
      catalogFile('Bad.tsx'),
    );
    expect(result[0].errorCount).toBeGreaterThan(0);
    expect(result[0].messages.some((m) => m.message.includes('folder boundaries'))).toBe(true);
  });

  it('asserts every @/api import under components/card is type-only', () => {
    const files = globSync('src/components/card/**/*.{ts,tsx}', { cwd: process.cwd() });
    const apiImports: string[] = [];
    for (const file of files) {
      const code = readFileSync(file, 'utf8');
      for (const line of code.split('\n')) {
        const match = line.match(/^import\s+(type\s+)?{[^}]+}\s+from\s+['"]@\/api\/[^'"]+['"];?/);
        if (match && !match[1]) {
          apiImports.push(`${file}: ${line.trim()}`);
        }
      }
    }
    expect(apiImports).toEqual([]);
  });

  const locationsFile = (name: string) => join(process.cwd(), 'src/locations', name);

  it('flags a locations component that imports from app (F16-c)', async () => {
    const result = await lint(
      "import { createAppRoutes } from '@/app/routes';\nexport const A = () => null;\n",
      locationsFile('Bad.tsx'),
    );
    expect(result[0].errorCount).toBeGreaterThan(0);
    expect(result[0].messages.some((m) => m.message.includes('folder boundaries'))).toBe(true);
  });

  it('lets locations use the api, the ui primitives and the features below it (F16-c)', async () => {
    const result = await lint(
      "import { listLocations } from '@/api/endpoints';\nimport { useOffline } from '@/auth';\nimport { Button } from '@/components/ui/Button';\nexport const A = () => <Button onClick={() => void listLocations()}>{String(useOffline())}</Button>;\n",
      locationsFile('Okay.tsx'),
    );
    expect(result[0].errorCount).toBe(0);
  });

  it('lets the collection read locations through its index only (F16-c)', async () => {
    const deep = await lint(
      "import { useLocations } from '@/locations/queries';\nexport const A = () => useLocations;\n",
      join(process.cwd(), 'src/collection', 'Deep.tsx'),
    );
    expect(deep[0].errorCount).toBeGreaterThan(0);
    const index = await lint(
      "import { useLocations } from '@/locations';\nexport const A = () => useLocations;\n",
      join(process.cwd(), 'src/collection', 'Index.tsx'),
    );
    expect(index[0].errorCount).toBe(0);
  });

  const rulesFile = (name: string) => join(process.cwd(), 'src/decks/rules', name);
  const folderErrors = (result: ESLint.LintResult[]) =>
    result[0].messages.filter((m) => m.ruleId === 'no-restricted-imports').length;

  it('keeps the deck rules pure: no React, api, lib, node or other package (F5-b)', async () => {
    for (const source of [
      "import { useState } from 'react';",
      "import type { GameMeta } from '@/api/types';",
      "import { formatMoney } from '@/lib/format';",
      "import { readFileSync } from 'node:fs';",
      "import { useTranslation } from 'react-i18next';",
      "import { nameKey } from '../rules/sortNames';",
    ]) {
      const result = await lint(`${source}\nexport const A = 1;\n`, rulesFile('Bad.ts'));
      expect(folderErrors(result), source).toBeGreaterThan(0);
    }
  });

  it('keeps the deck rules off the DOM (F5-b)', async () => {
    const result = await lint(
      'export const A = () => document.title + String(window.innerWidth);\n',
      rulesFile('Dom.ts'),
    );
    expect(result[0].messages.filter((m) => m.ruleId === 'no-restricted-globals')).toHaveLength(2);
  });

  it('lets the deck rules import their siblings, and their tests use node and fixtures (F5-b)', async () => {
    const lib = await lint(
      "import { nameKey } from './sortNames';\nimport type { Card } from './types';\nexport const A = (c: Card) => nameKey(c.name);\n",
      rulesFile('Okay.ts'),
    );
    expect(lib[0].errorCount).toBe(0);
    const test = await lint(
      "import { readFileSync } from 'node:fs';\nimport { it } from 'vitest';\nimport { CASES } from '@/test/deckRulesCases';\nit('x', () => void readFileSync(String(CASES.length)));\n",
      rulesFile('Okay.test.ts'),
    );
    expect(test[0].errorCount).toBe(0);
  });

  it('keeps decks out of the lower folders and away from app (F5-b)', async () => {
    const fromLib = await lint(
      "import { nameKey } from '@/decks/rules';\nexport const A = nameKey;\n",
      join(process.cwd(), 'src/lib', 'Bad.ts'),
    );
    expect(folderErrors(fromLib)).toBeGreaterThan(0);
    const toApp = await lint(
      "import { createAppRoutes } from '@/app/routes';\nexport const A = createAppRoutes;\n",
      join(process.cwd(), 'src/decks', 'Bad.tsx'),
    );
    expect(folderErrors(toApp)).toBeGreaterThan(0);
    const toRules = await lint(
      "import { nameKey } from '@/decks/rules';\nexport const A = nameKey;\n",
      join(process.cwd(), 'src/decks', 'Okay.tsx'),
    );
    expect(toRules[0].errorCount).toBe(0);
  });
});
