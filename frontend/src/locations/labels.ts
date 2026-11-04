import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { StorageLocation } from '@/api/types';

/** Location codes (F16-b S2): 1-32 letters, digits or `-`. */
export const CODE_PATTERN = /^[A-Za-z0-9-]{1,32}$/;
export const CODE_MAX = 32;
export const DESCRIPTION_MAX = 200;

/** What is wrong with a typed code, as a `locations:form` key; null when it can be sent. */
export function codeProblem(code: string): 'codeRequired' | 'codeFormat' | null {
  if (code === '') return 'codeRequired';
  return CODE_PATTERN.test(code) ? null : 'codeFormat';
}

/** A trimmed description; empty is no description. */
export const cleanDescription = (text: string): string | null => text.trim() || null;

/** `CODE — description · Locked`: how a location reads in a select. */
export function useLocationLabel() {
  const { t } = useTranslation('locations');
  return useCallback(
    (location: Pick<StorageLocation, 'code' | 'description' | 'locked'>) =>
      `${location.code}${location.description ? ` — ${location.description}` : ''}${
        location.locked ? ` · ${t('locked')}` : ''
      }`,
    [t],
  );
}

/** `5 copies · 3 cards`. */
export function useLocationCounts() {
  const { t } = useTranslation('locations');
  return useCallback(
    (location: Pick<StorageLocation, 'copies' | 'cards'>) =>
      t('counts', {
        copies: t('copies', { count: location.copies }),
        cards: t('cards', { count: location.cards }),
      }),
    [t],
  );
}

/** The collection list of one location (`GET /collection?location=`, F16-b S11). */
export const cardsHref = (code: string) => `/collection?location=${encodeURIComponent(code)}`;
