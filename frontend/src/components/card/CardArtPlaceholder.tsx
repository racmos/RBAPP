import type { CardSummary } from '@/api/types';
import { shadeHex } from '@/lib/color';
import { domainColor } from '@/lib/domains';
import { useEnumLabel } from '@/i18n';
import styles from './CardArtPlaceholder.module.css';

type CardArtPlaceholderCard = Pick<
  CardSummary,
  'name' | 'domains' | 'type' | 'supertype' | 'energy' | 'might'
>;

type CardArtPlaceholderProps = {
  card: CardArtPlaceholderCard;
  decorative?: boolean;
  className?: string;
};

export const DOMAIN_GLYPHS: Record<string, string> = {
  Fury: 'M12 3l9 18H3L12 3z',
  Calm: 'M12 2l1.5 5.5L18 6l-4 3 2.5 4.5-5.5-2.5-5.5 2.5L8 9 4 6l4.5.5L12 2z',
  Mind: 'M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0zM12 5a7 7 0 1 0 0 14 7 7 0 0 0 0-14z',
  Body: 'M12 2l2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5L12 2z',
  Chaos: 'M12 2l2 5 5-2-2 5 5 2-5 2 2 5-5-2-2 5-2-5-5 2 2-5-5-2 5-2-2-5 5 2 2-5z',
  Order: 'M12 2l2.5 6.5L21 8l-5 4 2 6.5-6-3.5-6 3.5 2-6.5-5-4 6.5.5L12 2z',
  Colorless: 'M12 3l9 9-9 9-9-9 9-9z',
};

function placeholderBackground(domains: string[]): string {
  const colors = domains.length > 0 ? domains.map(domainColor) : [domainColor('Colorless')];
  if (colors.length >= 2) {
    const [d0, d1] = colors;
    return `linear-gradient(150deg, ${d0} 0%, ${d0} 42%, ${d1} 58%, ${d1} 100%)`;
  }
  const d0 = colors[0];
  return `radial-gradient(120% 130% at 30% 12%, ${shadeHex(d0, 38)}, ${shadeHex(d0, -30)})`;
}

export function CardArtPlaceholder({ card, decorative, className }: CardArtPlaceholderProps) {
  const { typeLabel } = useEnumLabel();
  const domains = card.domains.length > 0 ? card.domains : ['Colorless'];
  const firstDomain = domains[0];
  const glyph = DOMAIN_GLYPHS[firstDomain] ?? DOMAIN_GLYPHS.Colorless;
  const typeText = typeLabel(card.supertype, card.type).toUpperCase();

  const rootProps = decorative
    ? { 'aria-hidden': true as const }
    : { role: 'img' as const, 'aria-label': card.name };

  return (
    <div
      className={[styles.box, className].filter(Boolean).join(' ')}
      style={{ background: placeholderBackground(card.domains) }}
      {...rootProps}
    >
      <div className={styles.gloss} />
      <div className={styles.frame} />
      <svg className={styles.glyph} viewBox="0 0 24 24" aria-hidden="true">
        <path d={glyph} fill="currentColor" />
      </svg>
      <div className={styles.type}>{typeText}</div>
      {card.energy !== null && card.energy !== undefined && (
        <div className={styles.energy} role="img" aria-label={`Energy ${card.energy}`}>
          <span aria-hidden="true">{card.energy}</span>
        </div>
      )}
      {card.might !== null && card.might !== undefined && (
        <div className={styles.might} role="img" aria-label="might" />
      )}
      <div className={styles.name}>{card.name}</div>
    </div>
  );
}
