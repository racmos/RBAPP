export type AbilityToken =
  | { kind: 'text'; text: string }
  | { kind: 'keyword'; text: string }
  | { kind: 'energy'; value: number }
  | { kind: 'exhaust' }
  | { kind: 'might' }
  | { kind: 'rune'; domain: string }
  | { kind: 'reminder'; children: AbilityToken[] };

const DOMAIN_RUNES = new Set(['fury', 'calm', 'mind', 'body', 'chaos', 'order']);

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function parseSymbol(match: string): AbilityToken {
  if (match.startsWith(':rb_') && match.endsWith(':')) {
    const inner = match.slice(4, -1);

    const energy = /^energy_(\d+)$/.exec(inner);
    if (energy) {
      return { kind: 'energy', value: Number(energy[1]) };
    }

    if (inner === 'exhaust') return { kind: 'exhaust' };
    if (inner === 'might') return { kind: 'might' };

    const rune = /^rune_(\w+)$/.exec(inner);
    if (rune) {
      const colour = rune[1];
      if (colour === 'rainbow') return { kind: 'rune', domain: 'rainbow' };
      if (DOMAIN_RUNES.has(colour)) {
        return { kind: 'rune', domain: capitalize(colour) };
      }
    }

    return { kind: 'keyword', text: inner };
  }

  if (match.startsWith('[') && match.endsWith(']')) {
    return { kind: 'keyword', text: match.slice(1, -1) };
  }

  return { kind: 'text', text: match };
}

function step2(text: string): AbilityToken[] {
  const tokens: AbilityToken[] = [];
  const pattern = /(:rb_[a-z0-9_]+:|\[[^\]]+\])/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > last) {
      tokens.push({ kind: 'text', text: text.slice(last, index) });
    }
    tokens.push(parseSymbol(match[0]));
    last = index + match[0].length;
  }
  if (last < text.length) {
    tokens.push({ kind: 'text', text: text.slice(last) });
  }
  return tokens;
}

/**
 * Parse card ability text into renderable tokens (F2-f S9).
 * Parentheses become reminder text; bracketed text and :rb_*: symbols become keywords,
 * energy, exhaust, might or rune tokens.
 */
export function parseAbility(text: string | null | undefined): AbilityToken[] {
  if (!text || text.trim().length === 0) return [];

  const tokens: AbilityToken[] = [];
  const pattern = /(\([^()]*\))/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > last) {
      tokens.push(...step2(text.slice(last, index)));
    }
    const inner = match[0].slice(1, -1);
    tokens.push({ kind: 'reminder', children: step2(inner) });
    last = index + match[0].length;
  }
  if (last < text.length) {
    tokens.push(...step2(text.slice(last)));
  }
  return tokens;
}
