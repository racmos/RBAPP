/** Number, money and date formatting by app language, never by the browser locale (D14). */
export type Lang = 'es' | 'en';

const LOCALES: Record<Lang, string> = { es: 'es-ES', en: 'en-GB' };

export const localeFor = (lang: Lang): string => LOCALES[lang];

export const formatNumber = (value: number, lang: Lang): string =>
  new Intl.NumberFormat(localeFor(lang)).format(value);

export const formatMoney = (value: number, lang: Lang): string =>
  new Intl.NumberFormat(localeFor(lang), { style: 'currency', currency: 'EUR' }).format(value);

/** Medium date (for example "5 oct 2026"). Dates are read in UTC so they do not shift by timezone. */
export const formatDate = (value: Date | string, lang: Lang): string =>
  new Intl.DateTimeFormat(localeFor(lang), { dateStyle: 'medium', timeZone: 'UTC' }).format(
    new Date(value),
  );

/** Medium date and time (for example "5 oct 2026, 8:00"). The value carries its own offset. */
export const formatDateTime = (value: Date | string, lang: Lang): string =>
  new Intl.DateTimeFormat(localeFor(lang), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
