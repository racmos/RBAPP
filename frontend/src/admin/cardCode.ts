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
 * Reads `<SET>-<number>`, `<SET> <number>` or `<SET><digits>` when the letters prefix is one
 * of `setIds` (ignoring case). Anything else is `null`: a prefix that is not a set is never
 * guessed.
 */
export function readCardCode(value: string, setIds: readonly string[]): CardCodeRead | null {
  const code = value.trim();
  const match = SEPARATED.exec(code) ?? JOINED.exec(code);
  if (!match) return null;
  const prefix = match[1]!.toUpperCase();
  const setId = setIds.find((id) => id.toUpperCase() === prefix);
  if (setId === undefined) return null;
  return { code, setId, number: match[2]!.toLowerCase() };
}
