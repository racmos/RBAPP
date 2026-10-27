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
      "import { formatMoney } from '@/lib/format';\nimport { useTranslation } from 'react-i18next';\nimport { Badge } from '@/components/ui/Badge';\nimport type { CardSummary } from '@/api/types';\nexport function A({ p }: { p: CardSummary }) {\n  const { t } = useTranslation();\n  return <Badge tone=\"accent\">{formatMoney(1, 'es')} {t('ok')} {p.name}</Badge>;\n}\n",
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
});
