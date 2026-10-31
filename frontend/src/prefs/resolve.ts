import { down } from '@/lib/breakpoints';
import type { EffectivePrefs, Prefs } from './types';

export type PrefsEnv = { phone: boolean };

/** Phone range (R1): below 860 px. */
export const PHONE_QUERY = down('md');

export const isPhone = (): boolean => window.matchMedia(PHONE_QUERY).matches;

/** Auto (`null`) to concrete values (PREF-6). */
export function resolvePrefs(raw: Prefs, { phone }: PrefsEnv): EffectivePrefs {
  return {
    density: raw.density ?? (phone ? 'compact' : 'regular'),
    accent: raw.accent ?? 'orange',
    bgIntensity: raw.bg_intensity ?? 100,
    collectionView: raw.collection_view ?? (phone ? 'grid' : 'table'),
  };
}
