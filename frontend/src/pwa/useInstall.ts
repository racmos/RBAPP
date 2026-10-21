import { useSyncExternalStore } from 'react';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { getSavedPrompt, isIosSafari, promptInstall, subscribe } from './installPrompt';

export type Install = {
  /** The browser offered an install prompt that is still unused. */
  canPrompt: boolean;
  /** iOS Safari without an install event: the item opens the instructions. */
  isIos: boolean;
  /** Running as an installed app already (display mode or the iOS flag). */
  isStandalone: boolean;
  /** Whether the "Install" item should be shown at all. */
  visible: boolean;
  prompt: () => Promise<boolean>;
};

/** State of the install entry (PWA-6): shown when not standalone and there is a way to install. */
export function useInstall(): Install {
  const saved = useSyncExternalStore(subscribe, getSavedPrompt);
  const displayStandalone = useMediaQuery('(display-mode: standalone)');
  const isStandalone =
    displayStandalone || (navigator as Navigator & { standalone?: boolean }).standalone === true;
  const canPrompt = saved !== null;
  const isIos = !isStandalone && isIosSafari(navigator);
  return {
    canPrompt,
    isIos,
    isStandalone,
    visible: !isStandalone && (canPrompt || isIos),
    prompt: promptInstall,
  };
}
