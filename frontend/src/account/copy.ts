import { useTranslation } from 'react-i18next';
import { announce } from '@/components/ui/LiveAnnouncer';
import { pushToast } from '@/components/ui/toastStore';

/** Copy to the clipboard and say "Copied." through the live region (F9-j S15). */
export function useCopy() {
  const { t } = useTranslation('account');
  return async (text: string): Promise<void> => {
    try {
      await navigator.clipboard.writeText(text);
      announce(t('mfa.copied'));
    } catch {
      pushToast({ kind: 'error', message: t('copyFailed') });
    }
  };
}
