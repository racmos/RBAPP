import type { Prefs } from '@/api/types';

export type { Prefs };
export type PrefKey = keyof Prefs;

/** Effective values after Auto (`null`) is resolved; the language is resolved by `i18n`. */
export type EffectivePrefs = {
  density: NonNullable<Prefs['density']>;
  accent: NonNullable<Prefs['accent']>;
  bgIntensity: number;
  collectionView: NonNullable<Prefs['collection_view']>;
};
