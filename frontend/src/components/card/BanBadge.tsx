import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardBans, GameMode } from '@/api/types';
import { Badge } from '@/components/ui/Badge';
import { Icon } from '@/components/ui/Icon';
import styles from './BanBadge.module.css';

type BanBadgeProps = {
  bans: CardBans;
  variant?: 'full' | 'compact';
};

export function BanBadge({ bans, variant = 'full' }: BanBadgeProps) {
  const { t, i18n } = useTranslation('cards');
  const modes = (Object.keys(bans) as GameMode[]).filter((mode) => bans[mode]);

  const label = useMemo(() => {
    if (modes.length === 0) return '';
    return new Intl.ListFormat(i18n.language, { type: 'conjunction' }).format(modes);
  }, [modes, i18n.language]);

  if (modes.length === 0) return null;

  if (variant === 'compact') {
    return (
      <span className={styles.compact}>
        <Icon name="warning" size={14} />
        <span aria-hidden="true">{modes.join(' · ')}</span>
        <span className={styles.srOnly}>{t('ban.full', { modes: label })}</span>
      </span>
    );
  }

  return <Badge tone="danger">{t('ban.full', { modes: label })}</Badge>;
}
