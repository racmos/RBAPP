import { useTranslation } from 'react-i18next';
import { rarityColor } from '@/lib/domains';
import { useEnumLabel } from '@/i18n';
import styles from './RarityDot.module.css';

type RarityDotProps = {
  rarity: string;
  showLabel?: boolean;
};

export function RarityDot({ rarity, showLabel }: RarityDotProps) {
  const { t } = useTranslation('cards');
  const { label } = useEnumLabel();
  const translated = label('rarity', rarity);
  const color = rarityColor(rarity);

  if (showLabel) {
    return (
      <span className={styles.row}>
        <span className={styles.dot} style={{ background: color }} aria-hidden="true" />
        <span>{translated}</span>
      </span>
    );
  }

  return (
    <span
      className={styles.dot}
      style={{ background: color }}
      role="img"
      aria-label={t('rarityLabel', { rarity: translated })}
    />
  );
}
