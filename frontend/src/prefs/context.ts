import { createContext } from 'react';
import type { PrefsSync } from './sync';
import type { EffectivePrefs, Prefs } from './types';

export type PrefsApi = {
  /** The stored values, `null` = Auto (the server copy when signed in, else the mirror). */
  prefs: Prefs;
  /** The values in force after Auto is resolved for this viewport. */
  effective: EffectivePrefs;
  phone: boolean;
  signedIn: boolean;
  /** No connection (or an offline boot): saving is off and the settings are read-only (PWA-7). */
  offline: boolean;
  /** Apply now and save (optimistic, PREF-8). Does nothing for an anonymous visitor. */
  set: PrefsSync['set'];
  /** Send pending slider changes now (pointerup, blur). */
  flush: () => void;
};

export const PrefsContext = createContext<PrefsApi | null>(null);
