/** Number, money and date formatting in English. */

/** The one locale of the app (owner feedback S21): English numbers and dates, euro after the value. */
export const LOCALE = 'en-GB';

export const formatNumber = (value: number): string => new Intl.NumberFormat(LOCALE).format(value);

/** English number style with the euro symbol after the value: "1,061.52 €". */
export const formatMoney = (value: number): string =>
  `${new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)} €`;

/** Medium date in English (for example "5 Oct 2026"). Dates are read in UTC so they do not shift by timezone. */
export const formatDate = (value: Date | string): string =>
  new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(value));

/** Medium date and time in English (for example "5 Oct 2026, 8:00"). The value carries its own offset. */
export const formatDateTime = (value: Date | string): string =>
  new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  );

/** Percentage with one decimal and an explicit sign for non-zero values (DS-2). */
export const formatPct = (value: number): string =>
  new Intl.NumberFormat(LOCALE, {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
    signDisplay: 'exceptZero',
  }).format(value / 100);

const RELATIVE_STEPS: ReadonlyArray<[Intl.RelativeTimeFormatUnit, number]> = [
  ['second', 60],
  ['minute', 60],
  ['hour', 24],
  ['day', 7],
];

/**
 * "5 minutes ago", "yesterday" under 7 days, else the medium date (F9-j S9). A time in the
 * future (a clock a little ahead) is "now".
 */
export function formatRelative(value: Date | string, now: Date = new Date()): string {
  const then = new Date(value);
  let amount = Math.max(0, Math.floor((now.getTime() - then.getTime()) / 1000));
  const format = new Intl.RelativeTimeFormat(LOCALE, { numeric: 'auto' });
  for (const [unit, size] of RELATIVE_STEPS) {
    if (amount < size) return format.format(-amount, unit);
    amount = Math.floor(amount / size);
  }
  return formatDate(then);
}
