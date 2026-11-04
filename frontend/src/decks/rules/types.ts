import type { ADD_ZONES, HARD_RULES, ISSUE_CODES, MOVE_ZONES, ZONE_ORDER } from './constants';

/** A printing: `{set, id}`. */
export type CardRef = { set: string; id: string };
/** A printing with its copies. */
export type DeckLine = CardRef & { qty: number };

/** Deck content v2 (F5-R6). The functions treat a missing zone as empty. */
export type DeckContent = {
  v: 2;
  legend: CardRef | null;
  champion: CardRef | null;
  main: readonly DeckLine[];
  runes: readonly DeckLine[];
  battlefields: readonly CardRef[];
  sideboard: readonly DeckLine[];
  workbench: readonly DeckLine[];
};

/** The `CardSummary` fields the rules read; extra keys are ignored. */
export type Card = {
  name: string;
  type?: string | null;
  supertype?: string | null;
  domains?: readonly string[] | null;
  tags?: readonly string[] | null;
};

/** The catalog subset a deck references, keyed by `cardKey` (build it with `makeCards`).
 * Iteration order matters only to `autoRunes` (first rune of a colour). */
export type Cards = ReadonlyMap<string, Card>;

/** `{name: [modes]}`; names are matched with `nameKey`. */
export type Bans = Readonly<Record<string, readonly string[]>>;

export type Zone = (typeof ZONE_ORDER)[number];
export type AddZone = (typeof ADD_ZONES)[number];
export type MoveZone = (typeof MOVE_ZONES)[number];
export type IssueCode = (typeof ISSUE_CODES)[number];
export type HardRule = (typeof HARD_RULES)[number];
/** Why a card does not fit its zone (`card_off_identity.reason`). */
export type FitReason = 'type' | 'domain' | 'tag';

/** `size(have, need)` of the sized issues. */
export type SizeParams = { have: number; need: number; missing: number; over: number };
export type SlotParams = { have: number; need: number; missing: number };

export type IssueParams = {
  legend_missing: SlotParams;
  champion_missing: SlotParams;
  champion_tag: { name: string };
  main_size: SizeParams;
  runes_count: SizeParams;
  rune_off_identity: { name: string };
  battlefields_count: SizeParams;
  battlefields_duplicate: { name: string };
  sideboard_size: SizeParams;
  copies_over: { name: string; count: number; max: number };
  workbench_over: { count: number; max: number };
  card_off_identity: { name: string; zone: Zone; reason: FitReason };
  token_in_deck: { name: string; zone: Zone };
  banned: { name: string; mode: string };
};

export type Issue = { [C in IssueCode]: { code: C; params: IssueParams[C] } }[IssueCode];
export type Refusal = {
  [C in IssueCode]: { ok: false; code: C; params: IssueParams[C] };
}[IssueCode];
/** `canAdd` / `canMove`. */
export type CheckResult = { ok: true } | Refusal;
/** `applyLegend` / `applyChampion`: a new deck, or why not. */
export type ApplyResult = { ok: true; deck: DeckContent } | Refusal;

export type Section = 'legend' | 'champion' | 'main' | 'runes' | 'battlefields' | 'sideboard';
export type Completeness = Record<Section, SlotParams>;

export type Validation = { legal: boolean; issues: Issue[]; completeness: Completeness };

/** One broken hard limit, as `deck_limit_exceeded` params (F5-R9). */
export type HardViolation = { rule: HardRule; max: number; name?: string };
