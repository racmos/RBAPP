import type { TFunction } from 'i18next';
import type { DeckIssue } from '@/api/types';
import { HARD_RULES, ISSUE_CODES } from './rules';

/** Issue keys are built from the code at run time, so they cannot be statically typed; the
 *  catalog test (`issues.test.ts`) checks every code of `ISSUE_CODES` has its messages. */
type Loose = (key: string, options?: Record<string, unknown>) => string;
const loose = (t: TFunction<'decks'>) => t as unknown as Loose;

const SIZED = new Set(['main_size', 'runes_count', 'battlefields_count', 'sideboard_size']);
const known = (code: string) => (ISSUE_CODES as readonly string[]).includes(code);

/** The full sentence of one legality issue, with its params (F5-R19). */
export function issueMessage(t: TFunction<'decks'>, { code, params }: DeckIssue): string {
  const tl = loose(t);
  if (!known(code)) return tl('issue.unknown', { code });
  const options: Record<string, unknown> = { ...params };
  if (typeof params.zone === 'string') options.zone = tl(`zoneIn.${params.zone}`);
  if (SIZED.has(code)) options.context = Number(params.over) > 0 ? 'over' : 'missing';
  if (code === 'card_off_identity') options.context = params.reason;
  return tl(`issue.${code}`, options);
}

/** A few words for a code alone: `GET /decks` lists the codes without their params. */
export function issueShort(t: TFunction<'decks'>, code: string): string {
  const tl = loose(t);
  return known(code) ? tl(`issueShort.${code}`) : tl('issue.unknown', { code });
}

/** One `deck_limit_exceeded` violation `{rule, max, name?}` (F5-R9). */
export function hardLimitMessage(
  t: TFunction<'decks'>,
  violation: { rule: string; max: number; name?: string },
): string {
  const tl = loose(t);
  const rule = (HARD_RULES as readonly string[]).includes(violation.rule)
    ? violation.rule
    : 'unknown';
  return tl(`limit.${rule}`, { ...violation });
}
