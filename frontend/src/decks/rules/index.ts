// Deck rules library (F5-b, F5-R4): the TypeScript port of `app/services/deck_rules.py`,
// pure functions for instant feedback in the editor; the server stays authoritative.
export {
  ADD_ZONES,
  DEFAULT_RULES,
  HARD_RULES,
  ISSUE_CODES,
  MOVE_ZONES,
  ZONE_ORDER,
  rulesFromMeta,
  type DeckRules,
  type RulesContext,
} from './constants';
export type * from './types';
export {
  UnknownCard,
  cardKey,
  copies,
  identity,
  isChampionUnit,
  isToken,
  makeCards,
} from './cards';
export { compareNames, nameKey, sortNames } from './sortNames';
export { completeness, validate } from './validate';
export { canAdd, canMove } from './canAdd';
export { hardLimitViolations } from './hardLimits';
export { applyLegend } from './applyLegend';
export { applyChampion } from './applyChampion';
export { autoRunes } from './autoRunes';
export { deckDomains } from './deckDomains';
