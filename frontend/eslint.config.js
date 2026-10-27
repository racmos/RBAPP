import js from '@eslint/js';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import { defineConfig, globalIgnores } from 'eslint/config';
import tseslint from 'typescript-eslint';

// D10: one-way dependencies between folders. `lib` and `components/ui` are pure,
// `api` depends only on `lib`, features depend downward, only `app/` wires everything.
const FEATURES = ['auth', 'prefs', 'i18n', 'pwa'];
const FOLDERS = ['api', 'auth', 'prefs', 'i18n', 'pwa', 'shell', 'account', 'app'];

const deep = (name) => [`@/${name}`, `@/${name}/**`];
const parentRelative = {
  group: ['../*', '../**'],
  message: 'Import across folders with the @/ alias, not a parent-relative path.',
};

/** Restrict imports for the files of one folder. */
const boundary = (files, banned, { deepOnly = [] } = {}) => ({
  files,
  rules: {
    'no-restricted-imports': [
      'error',
      {
        patterns: [
          {
            group: banned.flatMap(deep),
            message: 'This import breaks the folder boundaries (D10).',
          },
          {
            group: deepOnly.map((name) => `@/${name}/**`),
            message: 'Import another feature through its index, not its internals (D10).',
          },
          parentRelative,
        ].filter((pattern) => pattern.group.length > 0),
      },
    ],
  },
});

const without = (names) => FOLDERS.filter((name) => !names.includes(name));

export default defineConfig(
  globalIgnores(['dist', 'node_modules', 'coverage']),
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: { globals: globals.browser },
  },
  {
    files: ['**/*.{tsx,jsx}'],
    ...jsxA11y.flatConfigs.recommended,
    languageOptions: {
      ...jsxA11y.flatConfigs.recommended.languageOptions,
      globals: globals.browser,
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    ...reactHooks.configs.flat.recommended,
  },
  {
    files: ['*.{js,mjs,ts}', 'scripts/**/*.{js,mjs,ts}'],
    languageOptions: { globals: globals.node },
  },
  // lib and styles: nothing app-specific.
  boundary(['src/lib/**/*.{ts,tsx}'], [...FOLDERS, 'components']),
  // ui primitives: lib and the i18n hook only.
  boundary(['src/components/ui/**/*.{ts,tsx}'], without(['i18n'])),
  // api: lib only.
  boundary(['src/api/**/*.{ts,tsx}'], [...without(['api']), 'components']),
  // features: api, lib, ui; never the shell, the app or another feature's internals.
  ...FEATURES.map((feature) =>
    boundary([`src/${feature}/**/*.{ts,tsx}`], ['shell', 'account', 'app'], {
      deepOnly: FEATURES.filter((name) => name !== feature),
    }),
  ),
  // shell and account: everything below, never app.
  boundary(['src/shell/**/*.{ts,tsx}', 'src/account/**/*.{ts,tsx}'], ['app']),
  // card and chart atoms: lib, i18n, ui and type-only @/api (F2-e).
  {
    files: ['src/components/card/**/*.{ts,tsx}', 'src/components/charts/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@/api', '@/api/**'],
              message: 'Card and chart components may import only types from @/api (D10).',
              allowTypeImports: true,
            },
            {
              group: [
                '@/auth/**',
                '@/prefs/**',
                '@/pwa/**',
                '@/shell/**',
                '@/account/**',
                '@/app/**',
              ],
              message: 'This import breaks the folder boundaries (D10).',
            },
            parentRelative,
          ],
        },
      ],
    },
  },
);
