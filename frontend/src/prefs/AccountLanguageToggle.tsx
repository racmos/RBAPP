import { LanguageToggle } from '@/i18n';
import { usePrefs } from './usePrefs';

/**
 * The ES/EN toggle of the login screen, the topbar and the "Más" sheet (5.20). It always writes
 * the device language; when signed in it also saves the choice to the account (PREF-8).
 */
export function AccountLanguageToggle({ className }: { className?: string }) {
  const { signedIn, set } = usePrefs();
  return (
    <LanguageToggle className={className} onChoose={(lang) => signedIn && set('lang', lang)} />
  );
}
