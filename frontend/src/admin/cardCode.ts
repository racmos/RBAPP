/**
 * The number of a card (CM-j). The API takes the set and the number apart
 * (`AdminCardCreate.card_id`: letters and digits, 1-10 characters, trimmed, lower-cased),
 * but an admin often types the full code a card shows (`OGNX-197`).
 */
export const CARD_NUMBER_PATTERN = /^[A-Za-z0-9]{1,10}$/;

/** True when `value` is a card number the API accepts (it trims, so the form does too). */
export const isCardNumber = (value: string): boolean => CARD_NUMBER_PATTERN.test(value.trim());

/** A full card code read as a set and a number. */
export type CardCodeRead = {
  /** What was typed, trimmed. */
  code: string;
  /** The set id as the list of sets writes it. */
  setId: string;
  /** The number, lower-cased as the API stores it. */
  number: string;
};

/** `OGNX-197`, `OGNX 197`, `OGN - 066a`. */
const SEPARATED = /^([A-Za-z]+)\s*[-\s]\s*([A-Za-z0-9]{1,10})$/;
/** `OGNX197`, `OGN066a`: the number starts with a digit. */
const JOINED = /^([A-Za-z]+)(\d[A-Za-z0-9]{0,9})$/;

/**
 * The set of the plated cards (CM-k, owner decision 2026-11-24): a metal copy of a card of
 * another set, coded `PLAT-<origin set>-<number>` (`PLAT-SFD-189`) and stored as set `PLAT`,
 * number `<origin set><number>` in lower case (`sfd189`), since a number is letters and digits.
 */
export const PLATED_SET_ID = 'PLAT';
/** `PLAT-SFD-189`, `PLAT SFD 189`, `PLAT-sfd189`: the rest starts with a letter. */
const PLATED = /^([A-Za-z]+)\s*[-\s]\s*([A-Za-z].*)$/;

const findSet = (setIds: readonly string[], prefix: string) =>
  setIds.find((id) => id.toUpperCase() === prefix.toUpperCase());

function readSetAndNumber(code: string, setIds: readonly string[]): CardCodeRead | null {
  const match = SEPARATED.exec(code) ?? JOINED.exec(code);
  if (!match) return null;
  const setId = findSet(setIds, match[1]!);
  if (setId === undefined) return null;
  return { code, setId, number: match[2]!.toLowerCase() };
}

/**
 * `PLAT-<origin set>-<number>` (or `PLAT <set> <number>`, `PLAT-<set><number>`) when `PLAT`
 * is one of `setIds`: the origin set must be another of `setIds` and the joined number a card
 * number, else `null` (never guessed). `undefined` when the code is not a plated code.
 */
function readPlatedCode(code: string, setIds: readonly string[]): CardCodeRead | null | undefined {
  const match = PLATED.exec(code);
  if (!match || match[1]!.toUpperCase() !== PLATED_SET_ID) return undefined;
  const plated = findSet(setIds, PLATED_SET_ID);
  if (plated === undefined) return undefined;
  const others = setIds.filter((id) => id.toUpperCase() !== PLATED_SET_ID);
  const origin = readSetAndNumber(match[2]!, others);
  if (!origin) return null;
  const number = `${origin.setId}${origin.number}`.toLowerCase();
  return isCardNumber(number) ? { code, setId: plated, number } : null;
}

/**
 * Reads `<SET>-<number>`, `<SET> <number>` or `<SET><digits>` when the letters prefix is one
 * of `setIds` (ignoring case), and a plated code `PLAT-SFD-189` as set `PLAT`, number
 * `sfd189` (CM-k). Anything else is `null`: a prefix that is not a set is never guessed.
 * With `PLAT` as the chosen set (`selectedSetId`) a card number (`sfd189`) is the plated
 * number itself, never a joined code to read.
 */
export function readCardCode(
  value: string,
  setIds: readonly string[],
  selectedSetId?: string,
): CardCodeRead | null {
  const code = value.trim();
  const plated = readPlatedCode(code, setIds);
  if (plated !== undefined) return plated;
  if (selectedSetId?.toUpperCase() === PLATED_SET_ID && isCardNumber(code)) return null;
  return readSetAndNumber(code, setIds);
}
