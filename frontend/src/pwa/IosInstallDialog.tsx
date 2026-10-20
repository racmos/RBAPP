import type { RefObject } from 'react';
import { useTranslation } from 'react-i18next';
import { Modal } from '@/components/ui/Modal';
import styles from './InstallItem.module.css';

type IosInstallDialogProps = {
  open: boolean;
  onClose: () => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
};

/** iOS Safari has no install event: the steps to add the app from the Share menu (PWA-6). */
export function IosInstallDialog({ open, onClose, returnFocusRef }: IosInstallDialogProps) {
  const { t } = useTranslation('common');
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('pwa.install.iosTitle')}
      returnFocusRef={returnFocusRef}
    >
      <p className={styles.intro}>{t('pwa.install.iosIntro')}</p>
      <ol className={styles.steps}>
        <li>{t('pwa.install.iosStep1')}</li>
        <li>{t('pwa.install.iosStep2')}</li>
        <li>{t('pwa.install.iosStep3')}</li>
      </ol>
    </Modal>
  );
}
