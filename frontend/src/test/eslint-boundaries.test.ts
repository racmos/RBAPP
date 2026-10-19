// @vitest-environment node
import { fileURLToPath } from 'node:url';
import { ESLint } from 'eslint';
import { describe, expect, it } from 'vitest';

const root = fileURLToPath(new URL('../../', import.meta.url));
const eslint = new ESLint({ cwd: root });

async function restricted(filePath: string, code: string) {
  const [result] = await eslint.lintText(code, { filePath: root + filePath });
  return result.messages
    .filter((message) => message.ruleId === 'no-restricted-imports')
    .map((message) => message.message);
}

describe('folder boundaries (D10)', () => {
  it('stops lib from importing the api layer', async () => {
    const errors = await restricted('src/lib/x.ts', "import { request } from '@/api';\nrequest;\n");
    expect(errors).toHaveLength(1);
  });

  it('stops ui components from importing auth', async () => {
    const errors = await restricted(
      'src/components/ui/x.tsx',
      "import { useAuth } from '@/auth';\nexport const X = () => useAuth();\n",
    );
    expect(errors).toHaveLength(1);
  });

  it('stops the api layer from importing the shell', async () => {
    const errors = await restricted('src/api/x.ts', "import { Shell } from '@/shell';\nShell;\n");
    expect(errors).toHaveLength(1);
  });

  it('allows the dependencies the table permits', async () => {
    expect(
      await restricted('src/lib/x.ts', "import { up } from '@/lib/breakpoints';\nup;\n"),
    ).toEqual([]);
    expect(
      await restricted(
        'src/components/ui/x.tsx',
        "import { up } from '@/lib/breakpoints';\nimport { useTranslation } from '@/i18n';\nup; useTranslation;\n",
      ),
    ).toEqual([]);
    expect(
      await restricted('src/api/x.ts', "import { up } from '@/lib/breakpoints';\nup;\n"),
    ).toEqual([]);
    expect(await restricted('src/app/x.ts', "import { Shell } from '@/shell';\nShell;\n")).toEqual(
      [],
    );
  });

  it('keeps features on each other index only and below the shell', async () => {
    expect(
      await restricted('src/auth/x.ts', "import { usePrefs } from '@/prefs';\nusePrefs;\n"),
    ).toEqual([]);
    expect(
      await restricted('src/auth/x.ts', "import { read } from '@/prefs/storage';\nread;\n"),
    ).toHaveLength(1);
    expect(
      await restricted('src/auth/x.ts', "import { Shell } from '@/shell';\nShell;\n"),
    ).toHaveLength(1);
    expect(
      await restricted('src/shell/x.ts', "import { router } from '@/app/router';\nrouter;\n"),
    ).toHaveLength(1);
  });

  it('asks for the alias instead of parent-relative imports across folders', async () => {
    expect(
      await restricted('src/auth/x.ts', "import { request } from '../api/client';\nrequest;\n"),
    ).toHaveLength(1);
  });
});
