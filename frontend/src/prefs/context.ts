import { createContext } from 'react';
import type { Lang } from '@/i18n';
import type { PrefsSync } from './sync';
import type { EffectivePrefs, Prefs } from './types';

export type PrefsApi = {
  /** The stored values, `null` = Auto (the server copy when signed in, else the mirror). */
  prefs: Prefs;
  /** The values in force after Auto is resolved for this viewport. */
  effective: EffectivePrefs;
  phone: boolean;
  signedIn: boolean;
  /** Apply now and save (optimistic, PREF-8). Does nothing for an anonymous visitor. */
  set: PrefsSync['set'];
  /** Send pending slider changes now (pointerup, blur). */
  flush: () => void;
  /** Change the language everywhere: UI, device choice and, when signed in, the account. `null` = Auto. */
  setLanguage: (lang: Lang | null) => void;
};

export const PrefsContext = createContext<PrefsApi | null>(null);
