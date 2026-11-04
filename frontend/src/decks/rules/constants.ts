// Ordered lists of the deck rules (F5-b), the same tuples as `app/services/deck_rules.py`.
// The rule values themselves come from `GET /meta/game` (`rules.deck`): build a
// `RulesContext` with `rulesFromMeta` and pass it to the functions.

/** Issue codes in report order (F5-R2). */
export const ISSUE_CODES = [
  'legend_missing',
  'champion_missing',
  'champion_tag',
  'main_size',
  'runes_count',
  'rune_off_identity',
  'battlefields_count',
  'battlefields_duplicate',
  'sideboard_size',
  'copies_over',
  'workbench_over',
  'card_off_identity',
  'token_in_deck',
  'banned',
] as const;

/** Hard limit rules in report order (F5-R9): `deck_limit_exceeded` params `{rule, max, name?}`. */
export const HARD_RULES = [
  'copies',
  'sideboard',
  'workbench',
  'battlefields',
  'runes',
  'token',
] as const;

/** Display order of the zones (design-handoff §3.7.1); "first occurrence" follows it. */
export const ZONE_ORDER = [
  'legend',
  'champion',
  'battlefields',
  'main',
  'sideboard',
  'runes',
  'workbench',
] as const;
export const ADD_ZONES = ['main', 'sideboard', 'workbench', 'runes', 'battlefields'] as const;
export const MOVE_ZONES = ['main', 'sideboard', 'workbench'] as const;
/** Zones whose copies count for the copy limit, plus the chosen champion (product.md). */
export const COPY_ZONES = ['main', 'sideboard', 'workbench'] as const;
/** Types that never go in the main deck or the sideboard. */
export const NOT_IN_DECK_TYPES: readonly string[] = ['Legend', 'Battlefield', 'Rune'];
export const COLORLESS = 'Colorless';

/** `rules.deck` of `GET /meta/game` (`DECK_RULES` in `app/schemas/game_domain.py`). */
export type DeckRules = {
  main_size: number;
  total_with_champion: number;
  runes: number;
  battlefields: number;
  sideboard: number;
  copies_max: number;
  workbench_max: number;
};

/** What the functions read from the server: rule values, game modes and the domain order. */
export type RulesContext = {
  deck: DeckRules;
  modes: readonly string[];
  domains: readonly string[];
};

/** The context from a `GET /meta/game` payload; `null` when it has no `rules.deck`. */
export function rulesFromMeta(meta: {
  modes: readonly string[];
  domains: readonly string[];
  rules: { deck?: DeckRules };
}): RulesContext | null {
  const deck = meta.rules.deck;
  return deck ? { deck: { ...deck }, modes: [...meta.modes], domains: [...meta.domains] } : null;
}

/**
 * The backend values (F5-a S1, `GAME_MODES`, `DOMAINS`). Tests only: the app builds its
 * context from `/meta/game` with `rulesFromMeta` and never hardcodes a rule value.
 */
export const DEFAULT_RULES: RulesContext = Object.freeze({
  deck: Object.freeze({
    main_size: 39,
    total_with_champion: 40,
    runes: 12,
    battlefields: 3,
    sideboard: 10,
    copies_max: 3,
    workbench_max: 100,
  }),
  modes: Object.freeze(['1v1', '2v2']),
  domains: Object.freeze(['Fury', 'Calm', 'Mind', 'Body', 'Chaos', 'Order', 'Colorless']),
});
