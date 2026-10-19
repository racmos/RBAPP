import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { below } from '@/lib/breakpoints';
import postcss, { type AtRule, type Node, type Rule } from 'postcss';

/** CSS is asserted on its source with postcss, not through getComputedStyle (R7, D26). */
export const SRC_DIR = fileURLToPath(new URL('../', import.meta.url));

export type Decl = { prop: string; value: string };
export type CssRule = { selectors: string[]; decls: Decl[]; atRules: string[] };

export const readCss = (file: string): string => readFileSync(file, 'utf8');

/** Every `.css` file below `dir` (default `src/`), recursively, sorted by path. */
export function cssFiles(dir: string = SRC_DIR): string[] {
  return readdirSync(dir, { withFileTypes: true })
    .flatMap((entry) =>
      entry.isDirectory()
        ? cssFiles(join(dir, entry.name))
        : entry.name.endsWith('.css')
          ? [join(dir, entry.name)]
          : [],
    )
    .sort();
}

const atRuleLabel = (node: AtRule) => `${node.name} ${node.params}`.trim();

function enclosingAtRules(node: Rule): string[] {
  const chain: string[] = [];
  for (let parent: Node | undefined = node.parent; parent; parent = parent.parent) {
    if (parent.type === 'atrule') chain.unshift(atRuleLabel(parent as AtRule));
  }
  return chain;
}

/** All style rules, with their selector list, declarations and enclosing at-rules. */
export function rules(css: string): CssRule[] {
  const found: CssRule[] = [];
  postcss.parse(css).walkRules((rule) => {
    const decls: Decl[] = [];
    rule.each((child) => {
      if (child.type === 'decl') decls.push({ prop: child.prop, value: child.value });
    });
    found.push({
      selectors: rule.selectors.map((selector) => selector.trim()),
      decls,
      atRules: enclosingAtRules(rule),
    });
  });
  return found;
}

/** Declarations of every rule whose selector list contains `selector`, in source order. */
export function declsFor(css: string, selector: string): Decl[] {
  return rules(css)
    .filter((rule) => rule.selectors.includes(selector))
    .flatMap((rule) => rule.decls);
}

/** Every `min-width` / `max-width` value used in `@media` rules, in source order. */
export function mediaWidths(css: string): number[] {
  const widths: number[] = [];
  postcss.parse(css).walkAtRules('media', (media) => {
    for (const match of media.params.matchAll(/(?:min|max)-width\s*:\s*([\d.]+)px/g)) {
      widths.push(Number(match[1]));
    }
  });
  return widths;
}

/** Allowed `@media` widths: each breakpoint and the same value minus 0.02 (max-width ranges). */
export function allowedMediaWidths(breakpoints: readonly number[]): Set<number> {
  return new Set(breakpoints.flatMap((px) => [px, below(px)]));
}

/** `@media` widths outside `allowed`, with the file that uses them (DS-4 scan). */
export function scanMediaWidths(
  files: readonly { file: string; css: string }[],
  allowed: ReadonlySet<number>,
): { file: string; value: number }[] {
  return files.flatMap(({ file, css }) =>
    mediaWidths(css)
      .filter((value) => !allowed.has(value))
      .map((value) => ({ file, value })),
  );
}

/** Selectors of rules not enclosed by `@layer <layer>`: unlayered CSS beats every layer (D15). */
export function unlayeredRules(css: string, layer: string): string[] {
  return rules(css)
    .filter((rule) => !rule.atRules.includes(`layer ${layer}`))
    .flatMap((rule) => rule.selectors);
}
