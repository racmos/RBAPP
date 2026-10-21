import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from '@/components/ui/Icon';
import { IosInstallDialog } from './IosInstallDialog';
import styles from './InstallItem.module.css';
import { useInstall } from './useInstall';

type InstallItemProps = {
  /** Extra class for the button, so the menu that hosts it can style it as one of its own. */
  className?: string;
  /** Class for the visible text, for menus that collapse it to an icon on narrow screens. */
  labelClassName?: string;
};

/**
 * The "Install app" entry of the "Más" sheet and the desktop topbar (PWA-6). With a saved
 * browser prompt it shows it; on iOS Safari it opens the instructions; otherwise (already
 * installed, or no way to install) it renders nothing.
 */
export function InstallItem({ className, labelClassName }: InstallItemProps) {
  const { t } = useTranslation('common');
  const { visible, canPrompt, prompt } = useInstall();
  const [help, setHelp] = useState(false);
  const button = useRef<HTMLButtonElement>(null);

  if (!visible) return null;
  return (
    <>
      <button
        ref={button}
        type="button"
        className={[styles.item, className].filter(Boolean).join(' ')}
        aria-label={t('pwa.install.label')}
        title={t('pwa.install.label')}
        aria-haspopup={canPrompt ? undefined : 'dialog'}
        onClick={() => (canPrompt ? void prompt() : setHelp(true))}
      >
        <Icon name="install" size={18} />
        <span className={labelClassName}>{t('pwa.install.label')}</span>
      </button>
      <IosInstallDialog open={help} onClose={() => setHelp(false)} returnFocusRef={button} />
    </>
  );
}
